from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from config.settings import Settings
from core.fetcher import FetchError
from core.sanitizer import REDACTION
from models.schemas import Song
from scrapers.genius_api_extractor import GeniusAPIExtractor


def settings(root: Path) -> Settings:
    return Settings(
        genius_access_token="token",
        user_agent="test-agent",
        data_dir=root,
        output_path=root / "codex.md",
        max_concurrency=2,
        request_timeout=1.0,
        include_full_lyrics=True,
        max_retries=0,
        reddit_min_interval=0.0,
    )


class FakeGeniusFetcher:
    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        if url.endswith("/search"):
            return {
                "response": {
                    "hits": [
                        {
                            "result": {
                                "primary_artist": {"id": 42, "name": "Sleep Token"}
                            }
                        }
                    ]
                }
            }
        if url.endswith("/artists/42/songs"):
            if params.get("page") == 1:
                return {
                    "response": {
                        "songs": [
                            {"id": 2, "title": "Atlantic"},
                            {"id": 1, "title": "Atlantic Lyrics"},
                        ],
                        "next_page": 2,
                    }
                }
            return {
                "response": {
                    "songs": [{"id": 3, "title": "Alkaline"}],
                    "next_page": None,
                }
            }
        if url.endswith("/songs/1"):
            return {
                "response": {
                    "song": {
                        "id": 1,
                        "title": "Atlantic",
                        "full_title": "Atlantic by Sleep Token",
                        "url": "https://genius.com/Sleep-token-atlantic-lyrics",
                        "album": {
                            "id": 100,
                            "name": "This Place Will Become Your Tomb",
                        },
                        "release_date": "2021-09-24",
                        "duration": "4:53",
                        "description": {"plain": "A descent into the ocean."},
                        "producer_artists": [{"name": "George Lever"}],
                        "writer_artists": [{"name": "Unknown Identity"}],
                    }
                }
            }
        if url.endswith("/albums/100/tracks"):
            return {
                "response": {
                    "tracks": [{"number": 1, "song": {"id": 1}}],
                    "next_page": None,
                }
            }
        if url.endswith("/referents"):
            return {
                "response": {
                    "referents": [
                        {
                            "id": 10,
                            "fragment": "Call me when you get the chance",
                            "annotations": [
                                {
                                    "id": 11,
                                    "body": {"plain": "A community interpretation."},
                                    "verified": True,
                                    "votes_total": 8,
                                }
                            ],
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected URL {url}")


class GeniusExtractorTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_catalog_is_a_hard_failure(self) -> None:
        extractor = GeniusAPIExtractor(
            AsyncMock(),  # type: ignore[arg-type]
            settings(Path(".")),
        )
        extractor.resolve_artist_id = AsyncMock(return_value=42)  # type: ignore[method-assign]
        extractor.catalog = AsyncMock(return_value=[])  # type: ignore[method-assign]
        with self.assertRaisesRegex(FetchError, "catalog"):
            await extractor.extract()

    async def test_songs_without_lyrics_or_annotations_fail(self) -> None:
        extractor = GeniusAPIExtractor(
            AsyncMock(),  # type: ignore[arg-type]
            settings(Path(".")),
        )
        extractor.resolve_artist_id = AsyncMock(return_value=42)  # type: ignore[method-assign]
        extractor.catalog = AsyncMock(return_value=[{"id": 1, "title": "Atlantic"}])  # type: ignore[method-assign]
        extractor.extract_song = AsyncMock(  # type: ignore[method-assign]
            return_value=Song(
                genius_id=1,
                title="Atlantic",
                full_title="Atlantic by Sleep Token",
                url="https://genius.com/sleep-token-atlantic-lyrics",
            )
        )
        with self.assertRaisesRegex(FetchError, "lyrics"):
            await extractor.extract()

    async def test_catalog_paginates_and_deduplicates_titles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extractor = GeniusAPIExtractor(
                FakeGeniusFetcher(),  # type: ignore[arg-type]
                settings(Path(directory)),
            )
            artist_id = await extractor.resolve_artist_id()
            songs = await extractor.catalog(artist_id)
        self.assertEqual(artist_id, 42)
        self.assertEqual([(song["id"], song["title"]) for song in songs], [(1, "Atlantic Lyrics"), (3, "Alkaline")])

    async def test_song_normalization_redacts_unknown_credit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extractor = GeniusAPIExtractor(
                FakeGeniusFetcher(),  # type: ignore[arg-type]
                settings(Path(directory)),
            )
            extractor._lyrics = AsyncMock(return_value="[Verse 1]\nSafe lyric")  # type: ignore[method-assign]
            song = await extractor.extract_song({"id": 1, "title": "Atlantic"})
        self.assertEqual(song.duration_seconds, 293)
        self.assertEqual(song.writers[0].name, REDACTION)
        self.assertEqual(song.associated_symbols, ["914 m / 500 fathoms"])
        self.assertTrue(song.annotations[0].verified)


if __name__ == "__main__":
    unittest.main()
