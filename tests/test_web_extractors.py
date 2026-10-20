from __future__ import annotations

import unittest
from typing import Any

from core.fetcher import FetchError
from models.schemas import CoverageStatus
from scrapers.musicology_scraper import MusicologyExtractor
from scrapers.press_archive_scraper import PressArchiveExtractor
from scrapers.reddit_stealth import RedditStealthExtractor
from scrapers.wiki_and_arg_scraper import WikiAndArgExtractor


class Node:
    def __init__(
        self,
        text: str = "",
        *,
        attrs: dict[str, str] | None = None,
        selectors: dict[str, list[Node]] | None = None,
    ) -> None:
        self.text = text
        self.attrib = attrs or {}
        self.selectors = selectors or {}

    def css(self, selector: str, **_: object) -> list[Node]:
        return self.selectors.get(selector, [])

    def get(self, name: str, default: str = "") -> str:
        return self.attrib.get(name, default)


class FakeWebFetcher:
    def __init__(self) -> None:
        entry = Node(
            selectors={
                "title": [Node("A theory about Atlantic")],
                "link": [
                    Node(
                        attrs={
                            "href": "https://www.reddit.com/r/SleepToken/comments/example/thread/"
                        }
                    )
                ],
                "content": [Node("Atlantic and ocean descent analysis.")],
            }
        )
        self.feed = Node(selectors={"entry": [entry]})
        paragraph = (
            "The Eden rune alphabet is a cipher whose symbols accompany the "
            "Take Me Back to Eden era."
        )
        self.wiki = Node(
            selectors={
                "article p": [Node(paragraph)],
                "h1": [Node("Sleep Token visual lore")],
            }
        )
        press_paragraph = (
            'Vessel explained, “We are here to serve Sleep and project His message '
            'through these offerings.”'
        )
        self.press = Node(
            selectors={
                "article p": [Node(press_paragraph)],
                "h1": [Node("Sleep Token interview")],
                "time[datetime]": [Node(attrs={"datetime": "2017-05-19"})],
            }
        )
        music = (
            "Euclid mirrors an earlier melody as a recurring callback and leitmotif "
            "that closes the trilogy."
        )
        self.music = Node(
            selectors={
                "article p": [Node(music)],
                "h1": [Node("Sleep Token musical analysis")],
            }
        )

    async def fetch_page(self, url: str, *, mode: str = "async") -> Any:
        if "reddit.com" in url:
            if "/comments/" in url:
                raise FetchError("blocked")
            return self.feed
        if "kerrang.com" in url or (
            "loudersound.com" in url and "who-and-what" in url
        ):
            return self.press
        if "story-behind-every" in url:
            return self.music
        if "web.archive.org" in url:
            return self.press
        return self.wiki


class WebExtractorTests(unittest.IsolatedAsyncioTestCase):
    async def test_reddit_reports_degraded_keyless_coverage(self) -> None:
        records, coverage = await RedditStealthExtractor(
            FakeWebFetcher(),  # type: ignore[arg-type]
            thread_limit=2,
        ).extract()
        self.assertEqual(len(records), 1)
        self.assertEqual(coverage.status, CoverageStatus.PARTIAL)
        self.assertIn("disabled unauthenticated JSON", coverage.reason or "")

    async def test_wiki_extracts_visual_symbol(self) -> None:
        records, coverage = await WikiAndArgExtractor(
            FakeWebFetcher()  # type: ignore[arg-type]
        ).extract()
        self.assertEqual(coverage.status, CoverageStatus.COMPLETE)
        self.assertTrue(any(record.category == "cryptography" for record in records))

    async def test_press_keeps_in_character_quote(self) -> None:
        records, coverage = await PressArchiveExtractor(
            FakeWebFetcher()  # type: ignore[arg-type]
        ).extract()
        self.assertEqual(coverage.status, CoverageStatus.COMPLETE)
        self.assertTrue(any(record.speaker == "Vessel" for record in records))

    async def test_musicology_extracts_callback(self) -> None:
        records, coverage = await MusicologyExtractor(
            FakeWebFetcher()  # type: ignore[arg-type]
        ).extract()
        self.assertEqual(coverage.status, CoverageStatus.COMPLETE)
        self.assertTrue(any(record.topic == "Inter-track callback" for record in records))


if __name__ == "__main__":
    unittest.main()
