from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aggregator.codex_builder import CodexBuilder
from config.settings import Settings
from core.sanitizer import REDACTION
from main import _load_checkpoint, _save_checkpoint
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    LoreThread,
    MusicologyInsight,
    Song,
    SourceKind,
    SourceReference,
)


def settings(root: Path) -> Settings:
    return Settings(
        genius_access_token="token",
        user_agent="test-agent",
        data_dir=root / "data",
        output_path=root / "codex.md",
        max_concurrency=2,
        request_timeout=1.0,
        include_full_lyrics=True,
        max_retries=0,
        reddit_min_interval=0.0,
        cross_reference_threshold=3.0,
    )


def source(url: str = "https://genius.com/test") -> SourceReference:
    return SourceReference(
        url=url,
        title="Test source",
        kind=SourceKind.COMMUNITY,
        confidence=0.7,
    )


class BuilderTests(unittest.TestCase):
    def test_links_records_and_renders_required_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = settings(Path(directory))
            song = Song(
                genius_id=1,
                title="Atlantic",
                full_title="Atlantic by Sleep Token",
                url="https://genius.com/test",
                release_name="This Place Will Become Your Tomb",
                track_number=1,
                description="Ocean descent.",
                lyrics="[Verse 1]\nA safe lyric",
                sources=[source()],
            )
            lore = LoreThread(
                title="Atlantic lore",
                body="Atlantic begins a symbolic ocean descent for Vessel.",
                source=source("https://www.reddit.com/r/SleepToken/comments/example"),
            )
            insight = MusicologyInsight(
                topic="Inter-track callback",
                summary="Atlantic mirrors a recurring melody and water motif.",
                source=source("https://www.loudersound.com/features/test"),
            )
            coverage = ExtractionCoverage(
                source="fixture",
                status=CoverageStatus.COMPLETE,
                attempted=1,
                succeeded=1,
            )
            builder = CodexBuilder(config)
            dataset = builder.build_dataset(
                songs=[song],
                lore_threads=[lore],
                visual_symbols=[],
                interview_quotes=[],
                musicology=[insight],
                coverage=[coverage],
            )
            markdown = builder.render(dataset)
        self.assertEqual(dataset.lore_threads[0].matched_song_ids, [1])
        self.assertIn("## 1. CORE MYTHOLOGY & THE PANTHEON", markdown)
        self.assertIn("## 4. COMPLETE DISCOGRAPHY & TRACK-BY-TRACK ENCYCLOPEDIA", markdown)
        self.assertIn("#### Track 1: Atlantic", markdown)
        self.assertIn("[Verse 1]", markdown)

    def test_builder_reapplies_sanitizer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            builder = CodexBuilder(settings(Path(directory)))
            song = Song(
                genius_id=1,
                title="Test",
                full_title="Test by Sleep Token",
                url="https://genius.com/test",
                description="Their real name is Forbidden Example.",
            )
            dataset = builder.build_dataset(
                songs=[song],
                lore_threads=[],
                visual_symbols=[],
                interview_quotes=[],
                musicology=[],
                coverage=[],
            )
        self.assertEqual(dataset.releases[0].songs[0].description, REDACTION)

    def test_checkpoint_round_trip_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = settings(Path(directory))
            coverage = ExtractionCoverage(
                source="genius",
                status=CoverageStatus.COMPLETE,
                attempted=1,
                succeeded=1,
            )
            song = Song(
                genius_id=1,
                title="Test",
                full_title="Test by Sleep Token",
                url="https://genius.com/test",
            )
            _save_checkpoint(config, "genius", [song], coverage)
            loaded = _load_checkpoint(config, "genius")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded[0][0].title, "Test")


if __name__ == "__main__":
    unittest.main()
