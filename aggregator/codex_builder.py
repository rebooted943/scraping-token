"""Deterministic cross-referencing and Markdown rendering for the Codex."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from config.settings import (
    CANONICAL_RELEASE_ORDER,
    MOTIF_KEYWORDS,
    RELEASE_ERAS,
    Settings,
    get_settings,
)
from core.sanitizer import REDACTION, sanitize_payload, sanitize_text
from models.schemas import (
    CodexDataset,
    Era,
    ExtractionCoverage,
    InterviewQuote,
    LoreThread,
    MusicologyInsight,
    Release,
    Song,
    VisualSymbol,
)

_WORD_RE = re.compile(r"[a-z0-9']+")
_MARKDOWN_META = re.compile(r"([\\`*_[\]<>])")
_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "for", "from", "in", "is", "it", "of", "on", "the", "to", "with"}
)

ERA_SUMMARIES = {
    "The Primordial Era": "The foundational EPs and standalone offerings establish Sleep, Vessel, devotion, and the central imbalance of worship.",
    "Era I: Sundowning": "The initiation cycle frames nightly communion through celestial, runic, and alchemical imagery.",
    "Era II: This Place Will Become Your Tomb": "The descent cycle pairs isolation and drowning imagery with increasing bathymetric depth.",
    "Era III: Take Me Back to Eden": "The trilogy's closing cycle uses a proprietary cipher and creature imagery while revisiting earlier musical and lyrical ideas.",
    "Post-Trilogy Era": "Material released after Take Me Back to Eden is catalogued separately so later canon is not forced into the completed trilogy.",
}


def _words(value: str) -> set[str]:
    return {word for word in _WORD_RE.findall(value.casefold()) if word not in _STOPWORDS}


def _inline(value: object) -> str:
    return _MARKDOWN_META.sub(r"\\\1", sanitize_text(str(value))).replace("\n", " ")


def _cite(url: str, title: str = "source") -> str:
    return f"[{_inline(title)}]({url})"


def _quoted(value: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in sanitize_text(value).splitlines())


def _release_era(name: str, year: int | None) -> str:
    mapped = RELEASE_ERAS.get(name.casefold())
    if mapped:
        return mapped
    return "Post-Trilogy Era" if year and year >= 2024 else "The Primordial Era"


class CodexBuilder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _match_score(self, song: Song, text: str) -> float:
        lowered = text.casefold()
        title = song.title.casefold()
        score = 0.0
        if re.search(rf"(?<!\w){re.escape(title)}(?!\w)", lowered):
            score += 5.0 if len(title) >= 5 else 3.0
        title_words = _words(title)
        score += min(2.0, float(len(title_words & _words(lowered))))
        if song.release_name.casefold() in lowered:
            score += 1.5
        for annotation in song.annotations:
            fragment = annotation.fragment.casefold()
            if len(fragment.split()) >= 4 and fragment in lowered:
                score += 3.0
                break
        return score

    def _match_song_ids(self, songs: list[Song], text: str) -> list[int]:
        scored = [
            (self._match_score(song, text), song.genius_id)
            for song in songs
        ]
        return [
            song_id
            for score, song_id in sorted(scored, reverse=True)
            if score >= self.settings.cross_reference_threshold
        ]

    def _cross_reference(
        self,
        songs: list[Song],
        lore: list[LoreThread],
        visuals: list[VisualSymbol],
        musicology: list[MusicologyInsight],
    ) -> tuple[list[LoreThread], list[VisualSymbol], list[MusicologyInsight]]:
        linked_lore: list[LoreThread] = []
        for thread in lore:
            copy = thread.model_copy(deep=True)
            discussion = "\n".join([copy.title, copy.body, *(item.body for item in copy.comments)])
            copy.matched_song_ids = self._match_song_ids(songs, discussion)
            linked_lore.append(copy)

        linked_visuals: list[VisualSymbol] = []
        linked_musicology: list[MusicologyInsight] = []
        songs_by_id = {song.genius_id: song.title for song in songs}
        for collection, target in (
            (visuals, linked_visuals),
            (musicology, linked_musicology),
        ):
            for record in collection:
                copy = record.model_copy(deep=True)
                text = copy.description if isinstance(copy, VisualSymbol) else copy.summary
                copy.related_songs = [
                    songs_by_id[song_id]
                    for song_id in self._match_song_ids(songs, text)
                    if song_id in songs_by_id
                ]
                target.append(copy)
        return linked_lore, linked_visuals, linked_musicology

    @staticmethod
    def _releases(songs: list[Song]) -> list[Release]:
        grouped: defaultdict[str, list[Song]] = defaultdict(list)
        for song in songs:
            grouped[song.release_name].append(song)
        order = {name.casefold(): index for index, name in enumerate(CANONICAL_RELEASE_ORDER)}
        releases: list[Release] = []
        for name, release_songs in grouped.items():
            dates = [song.release_date for song in release_songs if song.release_date]
            year = min(dates).year if dates else None
            release_songs.sort(
                key=lambda song: (
                    song.track_number is None,
                    song.track_number or 10_000,
                    song.release_date or __import__("datetime").date.max,
                    song.title.casefold(),
                )
            )
            releases.append(
                Release(
                    name=name,
                    year=year,
                    era=_release_era(name, year),
                    songs=release_songs,
                )
            )
        releases.sort(
            key=lambda release: (
                order.get(release.name.casefold(), 10_000),
                release.year or 10_000,
                release.name.casefold(),
            )
        )
        return releases

    @staticmethod
    def _eras(releases: list[Release]) -> list[Era]:
        names = (
            "The Primordial Era",
            "Era I: Sundowning",
            "Era II: This Place Will Become Your Tomb",
            "Era III: Take Me Back to Eden",
            "Post-Trilogy Era",
        )
        return [
            Era(
                name=name,
                order=index,
                summary=ERA_SUMMARIES[name],
                releases=[release.name for release in releases if release.era == name],
            )
            for index, name in enumerate(names)
            if any(release.era == name for release in releases)
        ]

    def build_dataset(
        self,
        *,
        songs: list[Song],
        lore_threads: list[LoreThread],
        visual_symbols: list[VisualSymbol],
        interview_quotes: list[InterviewQuote],
        musicology: list[MusicologyInsight],
        coverage: list[ExtractionCoverage],
    ) -> CodexDataset:
        lore, visuals, insights = self._cross_reference(
            songs,
            lore_threads,
            visual_symbols,
            musicology,
        )
        releases = self._releases(songs)
        dataset = CodexDataset(
            eras=self._eras(releases),
            releases=releases,
            lore_threads=lore,
            visual_symbols=visuals,
            interview_quotes=interview_quotes,
            musicology=insights,
            coverage=coverage,
        )
        return CodexDataset.model_validate(
            sanitize_payload(dataset.model_dump(mode="json")),
            strict=False,
        )

    @staticmethod
    def _evidence(
        records: Iterable[tuple[str, str, str]],
        *,
        limit: int = 12,
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for text, url, title in records:
            normalized = text.casefold()
            if not text or text == REDACTION or normalized in seen:
                continue
            seen.add(normalized)
            result.append(f"- {text} — {_cite(url, title)}")
            if len(result) >= limit:
                break
        return result or ["- No qualifying evidence was recovered from the allowlisted sources."]

    def _render_mythology(self, dataset: CodexDataset) -> list[str]:
        lore_records = [
            (thread.body, thread.source.url, thread.source.title)
            for thread in dataset.lore_threads
        ]
        quote_records = [
            (f'“{quote.quote}”', quote.source.url, quote.publication)
            for quote in dataset.interview_quotes
        ]
        collective = [
            record
            for record in lore_records
            if any(token in record[0].casefold() for token in (" ii", " iii", " iv", "espera", "collective"))
        ]
        return [
            "## 1. CORE MYTHOLOGY & THE PANTHEON",
            "### 1.1 The Deity \"Sleep\": Nature, Promises, and Dynamic with Vessel",
            *self._evidence(
                [record for record in (*quote_records, *lore_records) if "sleep" in record[0].casefold()]
            ),
            "### 1.2 The Protagonist \"Vessel\": Psychological & Spiritual Arc Across Eras",
            *self._evidence(
                [record for record in lore_records if "vessel" in record[0].casefold()]
            ),
            "### 1.3 The Anonymous Collective (II, III, IV, Espera): Roles in the \"Rituals\"",
            *self._evidence(collective),
            "### 1.4 Canonical Interviews & Early Decrees (In-Character Quotes)",
            *self._evidence(quote_records, limit=30),
        ]

    @staticmethod
    def _render_eras(dataset: CodexDataset) -> list[str]:
        labels = {
            "The Primordial Era": "2.1 The Primordial Era (*One*, *Two*, Standalone Singles)",
            "Era I: Sundowning": "2.2 Era I: *Sundowning* (The Initiation, Celestial & Alchemical Symbolism, The 12 Sigils)",
            "Era II: This Place Will Become Your Tomb": "2.3 Era II: *This Place Will Become Your Tomb* (The Descent, Ocean Depth Metrics, Bathymetry & Isolation)",
            "Era III: Take Me Back to Eden": "2.4 Era III: *Take Me Back to Eden* (The Ascension/Regression, The 6 Characters, The Runic Cipher)",
            "Post-Trilogy Era": "2.5 Post-Trilogy Era (Current Releases)",
        }
        lines = ["## 2. CHRONOLOGICAL ERAS & NARRATIVE ARC"]
        for era in dataset.eras:
            lines.extend(
                [
                    f"### {labels[era.name]}",
                    era.summary,
                    f"- **Releases:** {', '.join(f'*{_inline(name)}*' for name in era.releases)}",
                ]
            )
        return lines

    def _render_lexicon(self, dataset: CodexDataset) -> list[str]:
        labels = (
            ("3.1 Chemistry, Biology & Physics (Alkaline, Acid, Surface Tension, Synapse, Telomeres, Aqua Regia)", "chemistry_biology_physics"),
            ("3.2 Visceral & Anatomical Motifs (Teeth, Jaws, Bite, Blood, Flesh, Bone)", "visceral_anatomical"),
            ("3.3 Elemental Motifs (Water/Drowning, Fire/Brimstone, Night/Daylight, Eden/Granite)", "elemental"),
        )
        lines = ["## 3. THE LEXICON OF SLEEP (RECURRING MOTIFS & METAPHORS)"]
        records = [
            (insight.summary, insight.source.url, insight.source.title)
            for insight in dataset.musicology
        ]
        for label, category in labels:
            terms = MOTIF_KEYWORDS[category]
            lines.append(f"### {label}")
            lines.extend(
                self._evidence(
                    [
                        record
                        for record in records
                        if any(term in record[0].casefold() for term in terms)
                    ]
                )
            )
        return lines

    def _render_track(
        self,
        song: Song,
        lore: list[LoreThread],
        insights: list[MusicologyInsight],
    ) -> list[str]:
        metadata = [
            f"Release: {_inline(song.release_name)}",
            f"Track Number: {song.track_number or 'unknown'}",
            f"Duration: {song.duration_seconds or 'unknown'} seconds",
        ]
        if song.associated_symbols:
            metadata.append(f"Associated Symbol/Entity/Depth: {', '.join(song.associated_symbols)}")
        producer_names = ", ".join(credit.name for credit in song.producers) or "not recovered"
        metadata.append(f"Producers: {producer_names}")
        linked_lore = [thread for thread in lore if song.genius_id in thread.matched_song_ids]
        linked_insights = [
            insight for insight in insights if song.title in insight.related_songs
        ]
        lines = [
            f"#### Track {song.track_number or '—'}: {_inline(song.title)}",
            f"- **Metadata:** {'; '.join(metadata)}",
            f"- **Official Genius \"About\" Summary:** {song.description or 'Not supplied by Genius.'}",
            "- **Full Lyrical Text:**",
            song.lyrics or "_Unavailable or disabled for this local run._",
            "- **Line-by-Line Genius Annotations:**",
        ]
        if song.annotations:
            for annotation in song.annotations:
                verification = "verified" if annotation.verified else "community"
                lines.extend(
                    [
                        _quoted(f'"{annotation.fragment}"'),
                        f"  **Meaning ({verification}):** {annotation.body} "
                        f"({_cite(annotation.source.url)})",
                    ]
                )
        else:
            lines.append("  - No Genius referents were recovered.")
        lines.extend(
            [
                "- **Narrative Placement:**",
                *self._evidence(
                    [
                        (thread.body, thread.source.url, thread.source.title)
                        for thread in linked_lore
                    ],
                    limit=5,
                ),
                "- **Inter-Track Callbacks (Leitmotifs):**",
                *self._evidence(
                    [
                        (insight.summary, insight.source.url, insight.source.title)
                        for insight in linked_insights
                    ],
                    limit=8,
                ),
                "- **Community Consensus & Deep Theories:**",
            ]
        )
        for thread in linked_lore[:8]:
            lines.append(
                f"  - **{_inline(thread.title)}**: {thread.body or 'Discussion thread'} "
                f"({_cite(thread.source.url)})"
            )
            for comment in thread.comments[:3]:
                lines.append(f"    - {comment.body} ({comment.score} visible score)")
        if not linked_lore:
            lines.append("  - No qualifying allowlisted community theory matched this track.")
        return lines

    def _render_discography(self, dataset: CodexDataset) -> list[str]:
        lines = ["## 4. COMPLETE DISCOGRAPHY & TRACK-BY-TRACK ENCYCLOPEDIA"]
        for release in dataset.releases:
            lines.append(f"### {_inline(release.name)} ({release.year or 'year unknown'})")
            for song in release.songs:
                lines.extend(
                    self._render_track(song, dataset.lore_threads, dataset.musicology)
                )
        return lines

    def _render_visuals(self, dataset: CodexDataset) -> list[str]:
        records = dataset.visual_symbols
        runes = [
            record
            for record in records
            if record.category in {"cryptography", "sigils", "bathymetry", "entities"}
        ]
        masks = [record for record in records if record.category == "visual identity"]
        return [
            "## 5. VISUAL SYMBOLISM, CRYPTOGRAPHY & ARG ARCHIVE",
            "### 5.1 The Runic Alphabet & Known Translations",
            *self._evidence(
                [
                    (record.description, record.source.url, record.source.title)
                    for record in runes
                ],
                limit=40,
            ),
            "### 5.2 Mask & Costume Evolution Across Eras",
            *self._evidence(
                [
                    (record.description, record.source.url, record.source.title)
                    for record in masks
                ],
                limit=30,
            ),
        ]

    def render(self, dataset: CodexDataset) -> str:
        coverage = [
            f"> **Coverage warning — {_inline(item.source)}:** {_inline(item.reason)}"
            for item in dataset.coverage
            if item.reason
        ]
        sections = [
            "# THE SLEEP TOKEN CODEX: COMPLETE LORE & MUSICAL KNOWLEDGE BASE",
            f"_Generated {dataset.generated_at.isoformat()}. Claims retain source class and provenance; community interpretations are not presented as canon._",
            *coverage,
            *self._render_mythology(dataset),
            *self._render_eras(dataset),
            *self._render_lexicon(dataset),
            *self._render_discography(dataset),
            *self._render_visuals(dataset),
        ]
        return "\n\n".join(section for section in sections if section).rstrip() + "\n"

    def write(self, dataset: CodexDataset, path: Path | None = None) -> Path:
        destination = path or self.settings.output_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(self.render(dataset), encoding="utf-8")
        temporary.replace(destination)
        return destination
