from __future__ import annotations

import unittest

from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    LoreThread,
    Song,
    SourceKind,
    SourceReference,
)
from main import _validate_primary_results


def _song() -> Song:
    return Song(
        genius_id=1,
        title="Atlantic",
        full_title="Atlantic by Sleep Token",
        url="https://genius.com/sleep-token-atlantic-lyrics",
        lyrics="[Verse 1]\nCall me when you get the chance",
    )


def _thread() -> LoreThread:
    return LoreThread(
        title="Atlantic ocean lore",
        body="A theory about the album depths.",
        source=SourceReference(
            url="https://www.reddit.com/r/SleepToken/comments/example/thread/",
            title="Atlantic ocean lore",
            kind=SourceKind.COMMUNITY,
        ),
    )


class OrchestratorGateTests(unittest.TestCase):
    def test_empty_genius_stops_the_night_run(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Genius corpus is empty"):
            _validate_primary_results(
                {
                    "genius": (
                        [],
                        ExtractionCoverage(
                            source="genius",
                            status=CoverageStatus.FAILED,
                            attempted=1,
                            succeeded=0,
                            reason="Genius catalog was empty",
                        ),
                    ),
                    "reddit": (
                        [_thread()],
                        ExtractionCoverage(
                            source="reddit",
                            status=CoverageStatus.PARTIAL,
                            attempted=1,
                            succeeded=1,
                            reason="keyless RSS",
                        ),
                    ),
                }
            )

    def test_genius_without_lyrics_stops_the_night_run(self) -> None:
        blank = _song()
        blank.lyrics = ""
        with self.assertRaisesRegex(RuntimeError, "no lyrics"):
            _validate_primary_results(
                {
                    "genius": (
                        [blank],
                        ExtractionCoverage(
                            source="genius",
                            status=CoverageStatus.COMPLETE,
                            attempted=1,
                            succeeded=1,
                        ),
                    ),
                    "reddit": (
                        [_thread()],
                        ExtractionCoverage(
                            source="reddit",
                            status=CoverageStatus.PARTIAL,
                            attempted=1,
                            succeeded=1,
                            reason="keyless RSS",
                        ),
                    ),
                }
            )

    def test_empty_reddit_stops_the_night_run(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Reddit corpus is empty"):
            _validate_primary_results(
                {
                    "genius": (
                        [_song()],
                        ExtractionCoverage(
                            source="genius",
                            status=CoverageStatus.COMPLETE,
                            attempted=1,
                            succeeded=1,
                        ),
                    ),
                    "reddit": (
                        [],
                        ExtractionCoverage(
                            source="reddit",
                            status=CoverageStatus.FAILED,
                            attempted=2,
                            succeeded=0,
                            reason="no Reddit threads were discovered",
                        ),
                    ),
                }
            )

    def test_primary_corpora_allow_google_to_start(self) -> None:
        _validate_primary_results(
            {
                "genius": (
                    [_song()],
                    ExtractionCoverage(
                        source="genius",
                        status=CoverageStatus.COMPLETE,
                        attempted=1,
                        succeeded=1,
                    ),
                ),
                "reddit": (
                    [_thread()],
                    ExtractionCoverage(
                        source="reddit",
                        status=CoverageStatus.PARTIAL,
                        attempted=1,
                        succeeded=1,
                        reason="keyless RSS",
                    ),
                ),
            }
        )


if __name__ == "__main__":
    unittest.main()
