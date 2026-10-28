from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scrapling.parser import Selector

from config.settings import Settings
from core.fetcher import FetchError
from models.schemas import Song
from scrapers.google_lore import GoogleLoreExtractor


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


class GoogleFetcher:
    async def fetch_public_page(self, url: str, *, mode: str = "async") -> Selector:
        if "google.com/search" in url:
            if "start=10" in url:
                return Selector("<html><body>No results</body></html>", url=url)
            return Selector(
                """
                <html><body>
                  <a href="/url?q=https%3A%2F%2Fexample.com%2Fatlantis&amp;sa=U">
                    <h3>Atlantic meaning</h3>
                  </a>
                </body></html>
                """,
                url=url,
            )
        return Selector(
            """
            <html><body><article>
              <h1>Atlantic meaning</h1>
              <p>The song <strong>Atlantic</strong> uses ocean imagery to describe
              isolation, grief, and an emotional descent.</p>
            </article></body></html>
            """,
            url=url,
        )


class GoogleLoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_saves_full_paragraphs_to_separate_incremental_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            song = Song(
                genius_id=1,
                title="Atlantic",
                full_title="Atlantic by Sleep Token",
                url="https://genius.com/test",
            )
            records, coverage = await GoogleLoreExtractor(
                GoogleFetcher(),  # type: ignore[arg-type]
                settings(root),
                queries=('"Sleep Token" "Atlantic" meaning',),
            ).extract([song], resume=False)
            payload = json.loads((root / "google.json").read_text(encoding="utf-8"))

        self.assertEqual(coverage.status.value, "complete")
        self.assertEqual(len(records), 1)
        self.assertIn(
            "Atlantic uses ocean imagery to describe isolation",
            records[0].paragraphs[0],
        )
        self.assertEqual(payload["source"], "google")
        self.assertEqual(payload["records"][0]["url"], "https://example.com/atlantis")
        self.assertEqual(payload["completed_queries"], ['"Sleep Token" "Atlantic" meaning'])

    async def test_stops_on_google_block_without_following_result_links(self) -> None:
        fetched: list[str] = []

        class BlockedFetcher:
            async def fetch_public_page(self, url: str, *, mode: str = "async") -> Selector:
                fetched.append(url)
                return Selector(
                    "<html><body>Our systems have detected unusual traffic "
                    "from your computer network</body></html>",
                    url=url,
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, coverage = await GoogleLoreExtractor(
                BlockedFetcher(),  # type: ignore[arg-type]
                settings(root),
                queries=('"Sleep Token" lore',),
            ).extract([], resume=False)
            payload = json.loads((root / "google.json").read_text(encoding="utf-8"))

        self.assertEqual(records, [])
        self.assertEqual(coverage.status.value, "failed")
        self.assertIn("CAPTCHA", coverage.reason or "")
        self.assertEqual(len(fetched), 1)
        self.assertIn("google.com/search", fetched[0])
        self.assertEqual(payload["source"], "google")

    async def test_skips_youtube_and_keeps_editorial_pages(self) -> None:
        fetched: list[str] = []

        class MixedFetcher:
            async def fetch_public_page(self, url: str, *, mode: str = "async") -> Selector:
                fetched.append(url)
                if "google.com/search" in url:
                    if "start=10" in url:
                        return Selector("<html><body>No results</body></html>", url=url)
                    return Selector(
                        """
                        <html><body>
                          <a href="/url?q=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dabc">Video</a>
                          <a href="/url?q=https%3A%2F%2Fboolintunes.com%2Flore">Lore article</a>
                        </body></html>
                        """,
                        url=url,
                    )
                if "youtube.com" in url:
                    raise FetchError("social pages should not be fetched")
                return Selector(
                    """
                    <html><body><article>
                      <h1>Sleep Token lore</h1>
                      <p>Sleep Token lyrics meaning and the Atlantic descent lore.</p>
                    </article></body></html>
                    """,
                    url=url,
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, _coverage = await GoogleLoreExtractor(
                MixedFetcher(),  # type: ignore[arg-type]
                settings(root),
                queries=('"Sleep Token" lore',),
            ).extract([], resume=False)

        self.assertEqual([record.url for record in records], ["https://boolintunes.com/lore"])
        self.assertFalse(any("youtube.com" in url for url in fetched))


if __name__ == "__main__":
    unittest.main()
