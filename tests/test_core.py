from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx
from pydantic import ValidationError

from config.settings import Settings
from scrapling.parser import Selector

from core.fetcher import (
    PermanentFetchError,
    ResilientFetcher,
    SourceNotAllowedError,
    node_text,
    select_adaptive,
)
from core.sanitizer import REDACTION, sanitize_credit_names, sanitize_payload, sanitize_text
from models.schemas import CoverageStatus, ExtractionCoverage


def settings(root: Path) -> Settings:
    return Settings(
        genius_access_token="test",
        user_agent="test-agent",
        data_dir=root,
        output_path=root / "codex.md",
        max_concurrency=2,
        request_timeout=1.0,
        include_full_lyrics=True,
        max_retries=1,
        backoff_base=0.0,
        reddit_min_interval=0.0,
    )


class SanitizerTests(unittest.TestCase):
    def test_redacts_entire_identity_paragraph_and_preserves_lore(self) -> None:
        text = "Sleep appears in a dream.\n\nTheir real name is Forbidden Example.\n\nWorship."
        self.assertEqual(
            sanitize_text(text),
            f"Sleep appears in a dream.\n\n{REDACTION}\n\nWorship.",
        )

    def test_recursive_sensitive_keys_and_credits_fail_closed(self) -> None:
        payload = {
            "nested": {"birth_name": "Forbidden Example"},
            "body": "A lore-only observation.",
        }
        self.assertEqual(sanitize_payload(payload)["nested"]["birth_name"], REDACTION)
        self.assertEqual(
            sanitize_credit_names(["Vessel", "Unknown Person", "vessel"]),
            ["Vessel", REDACTION],
        )

    def test_redacts_alias_to_person_claim_without_stored_name_blocklist(self) -> None:
        self.assertEqual(
            sanitize_text("Vessel is Forbidden Example according to a leak."),
            REDACTION,
        )


class SchemaTests(unittest.TestCase):
    def test_partial_coverage_requires_reason(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractionCoverage(
                source="reddit",
                status=CoverageStatus.PARTIAL,
                attempted=1,
                succeeded=0,
            )


class FetcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_429_and_sanitizes_json(self) -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
            return httpx.Response(
                200,
                json={"body": "A real name is Forbidden Example."},
                request=request,
            )

        with tempfile.TemporaryDirectory() as directory:
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            fetcher = ResilientFetcher(settings(Path(directory)), client=client)
            async with fetcher:
                payload = await fetcher.get_json("https://api.genius.com/test")
            await client.aclose()
        self.assertEqual(calls, 2)
        self.assertEqual(payload["body"], REDACTION)

    async def test_does_not_retry_access_denial(self) -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(403, request=request)

        with tempfile.TemporaryDirectory() as directory:
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            fetcher = ResilientFetcher(settings(Path(directory)), client=client)
            async with fetcher:
                with self.assertRaises(PermanentFetchError):
                    await fetcher.get_json("https://api.genius.com/test")
            await client.aclose()
        self.assertEqual(calls, 1)

    async def test_public_fetch_rejects_localhost(self) -> None:
        with self.assertRaises(SourceNotAllowedError):
            await ResilientFetcher.ensure_public("http://localhost/secret")
        with self.assertRaises(SourceNotAllowedError):
            await ResilientFetcher.ensure_public("http://127.0.0.1/secret")

    def test_node_text_keeps_text_inside_inline_tags(self) -> None:
        page = Selector(
            "<article><p>Hiding their identities, <strong>Sleep Token</strong> are enigmatic.</p></article>"
        )
        paragraph = page.css("p")[0]
        self.assertEqual(
            node_text(paragraph),
            "Hiding their identities, Sleep Token are enigmatic.",
        )

    def test_adaptive_selector_falls_back_to_save(self) -> None:
        class Page:
            def css(self, selector: str, **kwargs: object) -> list[str]:
                if selector == ".fallback" and kwargs.get("auto_save"):
                    return ["match"]
                return []

        self.assertEqual(
            select_adaptive(Page(), (".primary", ".fallback")),
            ["match"],
        )


if __name__ == "__main__":
    unittest.main()
