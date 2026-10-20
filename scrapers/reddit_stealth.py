"""Compliant keyless Reddit ingestion with explicit degraded coverage."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from config.settings import LORE_KEYWORDS, REDDIT_FEEDS
from core.fetcher import FetchError, ResilientFetcher, node_attr, node_text, select_adaptive
from core.sanitizer import REDACTION, sanitize_text
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    LoreComment,
    LoreThread,
    SourceKind,
    SourceReference,
)
from scrapers.common import keyword_hits

_SCORE_RE = re.compile(r"-?\d[\d,]*")


def _score(value: str) -> int:
    match = _SCORE_RE.search(value.replace("points", ""))
    return int(match.group(0).replace(",", "")) if match else 0


class RedditStealthExtractor:
    def __init__(self, fetcher: ResilientFetcher, *, thread_limit: int = 25) -> None:
        self.fetcher = fetcher
        self.thread_limit = thread_limit

    def _feed_entries(self, page: object) -> list[tuple[str, str, str]]:
        entries: list[tuple[str, str, str]] = []
        for entry in select_adaptive(page, ("entry", "item")):
            title_nodes = select_adaptive(entry, ("title",))
            link_nodes = select_adaptive(entry, ("link",))
            content_nodes = select_adaptive(entry, ("content", "description", "summary"))
            title = sanitize_text(node_text(title_nodes[0])) if title_nodes else ""
            link = node_attr(link_nodes[0], "href") if link_nodes else ""
            if not link and link_nodes:
                link = node_text(link_nodes[0])
            body = sanitize_text(node_text(content_nodes[0])) if content_nodes else ""
            if title and link:
                entries.append((title, link, body))
        return entries

    def _comments(self, page: object, thread_url: str) -> list[LoreComment]:
        comments: list[LoreComment] = []
        nodes = select_adaptive(
            page,
            (
                "shreddit-comment",
                ".comment",
                "[data-testid='comment']",
            ),
        )
        for node in nodes:
            body_nodes = select_adaptive(
                node,
                ("[slot='comment']", ".md", "[data-testid='comment-body']"),
            )
            body = sanitize_text(node_text(body_nodes[0]) if body_nodes else node_text(node))
            if len(body) < 40 or body == REDACTION:
                continue
            score = _score(
                node_attr(node, "score")
                or node_attr(node, "data-score")
                or node_text(node)
            )
            permalink = urljoin(
                thread_url,
                node_attr(node, "permalink") or node_attr(node, "data-permalink"),
            )
            comments.append(
                LoreComment(
                    body=body,
                    score=score,
                    permalink=permalink or thread_url,
                )
            )
        return sorted(comments, key=lambda item: item.score, reverse=True)[:15]

    async def _thread(
        self,
        title: str,
        url: str,
        feed_body: str,
    ) -> tuple[LoreThread, bool]:
        body = feed_body
        score = 0
        comments: list[LoreComment] = []
        degraded = False
        try:
            page = await self.fetcher.fetch_page(url, mode="stealth")
            body_nodes = select_adaptive(
                page,
                (
                    "[slot='text-body']",
                    ".usertext-body .md",
                    "[data-testid='post-content']",
                ),
            )
            if body_nodes:
                body = sanitize_text(node_text(body_nodes[0]))
            score_nodes = select_adaptive(page, ("[slot='vote-count']", ".score"))
            if score_nodes:
                score = _score(node_text(score_nodes[0]))
            comments = self._comments(page, url)
            if len(comments) < 15:
                degraded = True
        except FetchError:
            degraded = True
        combined = f"{title}\n{body}"
        return (
            LoreThread(
                title=title,
                body=body,
                score=score,
                keywords=keyword_hits(combined, LORE_KEYWORDS),
                comments=comments,
                source=SourceReference(
                    url=url,
                    title=title,
                    kind=SourceKind.COMMUNITY,
                    confidence=0.45,
                ),
            ),
            degraded,
        )

    async def extract(self) -> tuple[list[LoreThread], ExtractionCoverage]:
        candidates: dict[str, tuple[str, str]] = {}
        feed_failures = 0
        for feed_url in REDDIT_FEEDS:
            try:
                page = await self.fetcher.fetch_page(feed_url, mode="async")
            except FetchError:
                feed_failures += 1
                continue
            for title, url, body in self._feed_entries(page):
                candidates.setdefault(url, (title, body))

        selected = list(candidates.items())[: self.thread_limit]
        threads: list[LoreThread] = []
        degraded_threads = 0
        for url, (title, body) in selected:
            thread, degraded = await self._thread(title, url, body)
            threads.append(thread)
            degraded_threads += int(degraded)

        attempted = len(REDDIT_FEEDS) + len(selected)
        succeeded = attempted - feed_failures
        reason_parts = [
            "Reddit disabled unauthenticated JSON; RSS/HTML cannot guarantee "
            "all-time ranking or 15 visible comments"
        ]
        if feed_failures:
            reason_parts.append(f"{feed_failures} feeds unavailable")
        if degraded_threads:
            reason_parts.append(f"{degraded_threads} threads had limited comments")
        return threads, ExtractionCoverage(
            source="reddit",
            status=CoverageStatus.PARTIAL,
            attempted=attempted,
            succeeded=max(0, succeeded),
            reason="; ".join(reason_parts),
        )
