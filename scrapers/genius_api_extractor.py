"""Genius catalog, page lyrics, and fully paginated referent extraction."""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from typing import Any

from config.settings import (
    GENIUS_API_BASE,
    GENIUS_ARTIST_NAME,
    GENIUS_PAGE_SIZE,
    Settings,
    get_settings,
)
from core.fetcher import FetchError, ResilientFetcher
from core.sanitizer import REDACTION, sanitize_credit_name, sanitize_text
from models.schemas import (
    Credit,
    ExtractionCoverage,
    CoverageStatus,
    LyricAnnotation,
    Song,
    SourceKind,
    SourceReference,
)

_TITLE_SUFFIX = re.compile(r"\s+(?:lyrics|by sleep token)\s*$", re.IGNORECASE)
_LYRICS_HEADER = re.compile(r"^.*?\blyrics\s*\n", re.IGNORECASE)
_EMBED_FOOTER = re.compile(r"\s*\d*Embed\s*$", re.IGNORECASE)

TPWBYT_DEPTHS = {
    "atlantic": "914 m / 500 fathoms",
    "hypnosis": "1,824 m / 998 fathoms",
    "mine": "2,734 m / 1,495 fathoms",
    "like that": "3,644 m / 1,992 fathoms",
    "the love you want": "4,554 m / 2,490 fathoms",
    "fall for me": "5,464 m / 2,988 fathoms",
    "alkaline": "6,374 m / 3,485 fathoms",
    "distraction": "7,284 m / 3,983 fathoms",
    "descending": "8,194 m / 4,480 fathoms",
    "telomeres": "9,104 m / 4,978 fathoms",
    "high water": "10,014 m / 5,475 fathoms",
    "missing limbs": "10,924 m / 5,973 fathoms",
}


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        for key in ("plain", "markdown", "html"):
            if isinstance(value.get(key), str):
                return sanitize_text(value[key])
    return ""


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        for pattern in ("%B %d, %Y", "%B %Y", "%Y"):
            try:
                return datetime.strptime(value, pattern).date()
            except ValueError:
                continue
        return None


def _song_date(detail: dict[str, Any]) -> date | None:
    parsed = _parse_date(detail.get("release_date"))
    if parsed:
        return parsed
    components = detail.get("release_date_components")
    if isinstance(components, dict) and isinstance(components.get("year"), int):
        try:
            return date(
                int(components["year"]),
                int(components.get("month") or 1),
                int(components.get("day") or 1),
            )
        except ValueError:
            pass
    return _parse_date(detail.get("release_date_for_display"))


def _parse_duration(value: Any) -> int | None:
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str):
        parts = value.split(":")
        if all(part.isdigit() for part in parts):
            total = 0
            for part in parts:
                total = total * 60 + int(part)
            return total
    return None


def _clean_lyrics(value: str) -> str:
    lyrics = value.replace("\r\n", "\n").strip()
    lyrics = _LYRICS_HEADER.sub("", lyrics, count=1)
    lyrics = _EMBED_FOOTER.sub("", lyrics)
    return sanitize_text(lyrics)


class GeniusAPIExtractor:
    def __init__(
        self,
        fetcher: ResilientFetcher,
        settings: Settings | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.settings = settings or get_settings()
        self._lyrics_semaphore = asyncio.Semaphore(min(2, self.settings.max_concurrency))
        self._album_track_tasks: dict[int, asyncio.Task[dict[int, int]]] = {}

    @property
    def _headers(self) -> dict[str, str]:
        if not self.settings.genius_access_token:
            raise RuntimeError("GENIUS_ACCESS_TOKEN is required for Genius extraction")
        return {"Authorization": f"Bearer {self.settings.genius_access_token}"}

    async def _api(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = await self.fetcher.get_json(
            f"{GENIUS_API_BASE}{path}",
            params=params,
            headers=self._headers,
        )
        response = payload.get("response")
        if not isinstance(response, dict):
            raise FetchError(f"Genius response contract missing for {path}")
        return response

    async def resolve_artist_id(self) -> int:
        response = await self._api("/search", params={"q": GENIUS_ARTIST_NAME})
        hits = response.get("hits", [])
        for hit in hits if isinstance(hits, list) else []:
            result = hit.get("result", {}) if isinstance(hit, dict) else {}
            artist = result.get("primary_artist", {}) if isinstance(result, dict) else {}
            if str(artist.get("name", "")).casefold() == GENIUS_ARTIST_NAME.casefold():
                return int(artist["id"])
        raise FetchError("exact Sleep Token artist was not found by Genius")

    async def catalog(self, artist_id: int) -> list[dict[str, Any]]:
        page = 1
        candidates: list[dict[str, Any]] = []
        while page:
            response = await self._api(
                f"/artists/{artist_id}/songs",
                params={
                    "page": page,
                    "per_page": GENIUS_PAGE_SIZE,
                    "sort": "release_date",
                },
            )
            songs = response.get("songs", [])
            if isinstance(songs, list):
                candidates.extend(song for song in songs if isinstance(song, dict))
            next_page = response.get("next_page")
            page = int(next_page) if next_page else 0

        unique: dict[str, dict[str, Any]] = {}
        for song in candidates:
            title = _TITLE_SUFFIX.sub("", str(song.get("title", ""))).strip().casefold()
            if not title:
                continue
            existing = unique.get(title)
            if existing is None or int(song.get("id", 0)) < int(existing.get("id", 0)):
                unique[title] = song
        return list(unique.values())

    async def _referents(self, song_id: int, song_url: str) -> list[LyricAnnotation]:
        page = 1
        annotations: list[LyricAnnotation] = []
        seen_referents: set[int] = set()
        while page:
            response = await self._api(
                "/referents",
                params={
                    "song_id": song_id,
                    "page": page,
                    "per_page": GENIUS_PAGE_SIZE,
                    "text_format": "plain",
                },
            )
            referents = response.get("referents", [])
            if not isinstance(referents, list) or not referents:
                break
            new_count = 0
            for referent in referents:
                if not isinstance(referent, dict):
                    continue
                referent_id = int(referent.get("id", 0))
                if referent_id in seen_referents:
                    continue
                seen_referents.add(referent_id)
                new_count += 1
                fragment = sanitize_text(str(referent.get("fragment", "")))
                attached = referent.get("annotations", [])
                for annotation in attached if isinstance(attached, list) else []:
                    if not isinstance(annotation, dict):
                        continue
                    annotation_id = int(annotation.get("id", 0))
                    body = _plain_text(annotation.get("body"))
                    if not fragment or not body or not annotation_id:
                        continue
                    annotation_url = str(
                        annotation.get("url") or f"{song_url}#note-{annotation_id}"
                    )
                    annotations.append(
                        LyricAnnotation(
                            genius_id=annotation_id,
                            fragment=fragment,
                            body=body,
                            verified=bool(annotation.get("verified", False)),
                            votes_total=(
                                int(annotation["votes_total"])
                                if isinstance(annotation.get("votes_total"), int)
                                else None
                            ),
                            source=SourceReference(
                                url=annotation_url,
                                title=f"Genius annotation {annotation_id}",
                                kind=SourceKind.COMMUNITY,
                                confidence=0.9 if annotation.get("verified") else 0.65,
                            ),
                        )
                    )
            if len(referents) < GENIUS_PAGE_SIZE or new_count == 0:
                break
            page += 1
        return annotations

    async def _lyrics(self, _song_id: int, song_url: str) -> str:
        if not self.settings.include_full_lyrics:
            return ""

        def load() -> str:
            import lyricsgenius

            genius = lyricsgenius.Genius(
                self.settings.genius_access_token,
                timeout=int(self.settings.request_timeout),
                sleep_time=0.5,
                remove_section_headers=False,
                skip_non_songs=True,
                retries=self.settings.max_retries,
                user_agent=self.settings.user_agent,
            )
            return str(genius.lyrics(song_url=song_url) or "")

        async with self._lyrics_semaphore:
            return _clean_lyrics(await asyncio.to_thread(load))

    async def _load_album_tracks(self, album_id: int) -> dict[int, int]:
        tracks_by_song: dict[int, int] = {}
        page = 1
        while page:
            response = await self._api(
                f"/albums/{album_id}/tracks",
                params={"page": page, "per_page": GENIUS_PAGE_SIZE},
            )
            tracks = response.get("tracks", [])
            for track in tracks if isinstance(tracks, list) else []:
                if not isinstance(track, dict):
                    continue
                song = track.get("song")
                number = track.get("number")
                if isinstance(song, dict) and isinstance(number, int):
                    tracks_by_song[int(song["id"])] = number
            next_page = response.get("next_page")
            page = int(next_page) if next_page else 0
        return tracks_by_song

    async def _track_number(self, detail: dict[str, Any], song_id: int) -> int | None:
        direct = detail.get("track_number")
        if isinstance(direct, int) and direct > 0:
            return direct
        album = detail.get("album")
        if not isinstance(album, dict) or not isinstance(album.get("id"), int):
            return None
        album_id = int(album["id"])
        task = self._album_track_tasks.get(album_id)
        if task is None:
            task = asyncio.create_task(self._load_album_tracks(album_id))
            self._album_track_tasks[album_id] = task
        return (await task).get(song_id)

    @staticmethod
    def _credits(items: Any, role: str) -> list[Credit]:
        names: list[str] = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict):
                name = sanitize_credit_name(str(item.get("name", "")))
                if name not in names:
                    names.append(name)
        return [Credit(name=name, role=role) for name in names]

    async def extract_song(self, summary: dict[str, Any]) -> Song:
        song_id = int(summary["id"])
        response = await self._api(f"/songs/{song_id}", params={"text_format": "plain"})
        detail = response.get("song", {})
        if not isinstance(detail, dict):
            raise FetchError(f"Genius song payload missing for ID {song_id}")
        title = sanitize_text(str(detail.get("title") or summary.get("title") or "Unknown"))
        url = str(detail.get("url") or summary.get("url") or "")
        album = detail.get("album")
        release_name = (
            sanitize_text(str(album.get("name", "")))
            if isinstance(album, dict)
            else "Standalone Singles"
        ) or "Standalone Singles"
        errors: list[str] = []

        lyrics_task = asyncio.create_task(self._lyrics(song_id, url))
        referents_task = asyncio.create_task(self._referents(song_id, url))
        lyrics_result, referents_result = await asyncio.gather(
            lyrics_task,
            referents_task,
            return_exceptions=True,
        )
        if isinstance(lyrics_result, BaseException):
            lyrics = ""
            errors.append("lyrics unavailable")
        else:
            lyrics = lyrics_result
        if isinstance(referents_result, BaseException):
            annotations: list[LyricAnnotation] = []
            errors.append("annotations unavailable")
        else:
            annotations = referents_result

        symbols: list[str] = []
        depth = TPWBYT_DEPTHS.get(title.casefold())
        if depth and release_name.casefold() == "this place will become your tomb":
            symbols.append(depth)
        try:
            track_number = await self._track_number(detail, song_id)
        except FetchError:
            track_number = None
            errors.append("track number unavailable")
        return Song(
            genius_id=song_id,
            title=title,
            full_title=sanitize_text(str(detail.get("full_title") or title)),
            url=url,
            release_name=release_name,
            release_date=_song_date(detail),
            track_number=track_number,
            duration_seconds=_parse_duration(detail.get("duration")),
            producers=self._credits(detail.get("producer_artists"), "producer"),
            writers=self._credits(detail.get("writer_artists"), "writer"),
            associated_symbols=symbols,
            description=_plain_text(detail.get("description")),
            lyrics=lyrics,
            annotations=annotations,
            sources=[
                SourceReference(
                    url=url,
                    title=f"{title} Lyrics and Annotations",
                    kind=SourceKind.COMMUNITY,
                    confidence=0.85,
                )
            ],
            extraction_errors=errors,
        )

    async def extract(self) -> tuple[list[Song], ExtractionCoverage]:
        artist_id = await self.resolve_artist_id()
        summaries = await self.catalog(artist_id)
        results = await asyncio.gather(
            *(self.extract_song(summary) for summary in summaries),
            return_exceptions=True,
        )
        songs = [result for result in results if isinstance(result, Song)]
        failures = len(results) - len(songs)
        status = CoverageStatus.COMPLETE if failures == 0 else CoverageStatus.PARTIAL
        return songs, ExtractionCoverage(
            source="genius",
            status=status,
            attempted=len(results),
            succeeded=len(songs),
            reason=f"{failures} songs failed extraction" if failures else None,
        )
