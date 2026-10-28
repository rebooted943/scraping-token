from __future__ import annotations

import unittest

from models.schemas import SourceKind
from scrapers.allowlist_crawl import crawl_pages, iter_allowlisted_links
from scrapers.common import source_kind
from tests.test_web_extractors import Node


class GraphFetcher:
    def __init__(self, pages: dict[str, Node], *, fail: set[str] | None = None) -> None:
        self.pages = pages
        self.fail = fail or set()
        self.urls: list[str] = []

    async def fetch_page(self, url: str, *, mode: str = "async") -> Node:
        self.urls.append(url)
        if url in self.fail:
            from core.fetcher import FetchError

            raise FetchError("blocked")
        return self.pages[url]


def _page(*hrefs: str, text: str = "The Eden rune alphabet is a cipher.") -> Node:
    return Node(
        selectors={
            "a[href]": [Node(attrs={"href": href}) for href in hrefs],
            "article p": [Node(text)],
            "h1": [Node("Lore")],
        }
    )


class AllowlistCrawlTests(unittest.IsolatedAsyncioTestCase):
    def test_drops_links_outside_the_allowlist(self) -> None:
        page = _page(
            "https://loreofsleeptoken.com/the-lore",
            "https://en.wikipedia.org/wiki/Sleep_Token",
            "https://www.google.com/search?q=sleep+token",
        )
        links = iter_allowlisted_links(page, "https://loreofsleeptoken.com/")
        self.assertEqual(
            links,
            [
                "https://loreofsleeptoken.com/the-lore",
                "https://en.wikipedia.org/wiki/Sleep_Token",
            ],
        )

    async def test_same_host_pages_run_before_other_allowlisted_hosts(self) -> None:
        home = "https://loreofsleeptoken.com"
        lore = "https://loreofsleeptoken.com/the-lore"
        wiki = "https://en.wikipedia.org/wiki/Sleep_Token"
        fetcher = GraphFetcher(
            {
                home: _page(f"{lore}/", wiki, "https://www.google.com/search?q=x"),
                lore: _page(),
                wiki: _page(),
            }
        )
        pages = await crawl_pages(fetcher, [f"{home}/"], max_pages=10, max_depth=2)
        self.assertEqual([url for url, _page in pages], [home, lore, wiki])
        self.assertNotIn("google.com", " ".join(fetcher.urls))

    async def test_max_pages_stops_discovery(self) -> None:
        home = "https://loreofsleeptoken.com"
        lore = "https://loreofsleeptoken.com/the-lore"
        fetcher = GraphFetcher({home: _page(lore), lore: _page()})
        pages = await crawl_pages(fetcher, [home], max_pages=1, max_depth=2)
        self.assertEqual([url for url, _page in pages], [home])

    def test_source_kind_marks_lore_site_as_community(self) -> None:
        self.assertEqual(
            source_kind("https://loreofsleeptoken.com/the-lore"),
            SourceKind.COMMUNITY,
        )
        self.assertEqual(
            source_kind("https://en.wikipedia.org/wiki/Sleep_Token"),
            SourceKind.EDITORIAL,
        )


if __name__ == "__main__":
    unittest.main()
