"""Reddit ingestion via Reddrix, mapped onto the Codex lore-thread contract."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

from config.settings import LORE_KEYWORDS, REDDIT_SEARCH_QUERIES, REDDIT_SUBREDDITS
from core.fetcher import FetchError
from core.sanitizer import REDACTION, sanitize_text
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    LoreComment,
    LoreThread,
)
from scrapers.common import keyword_hits, source_reference

_DEFAULT_POSTS = 15
_DEFAULT_INFLIGHT = 1
_MAX_COMMENTS = 15
ReddrixFactory = Callable[..., Any]
ChunkCallback = Callable[[list[LoreThread], ExtractionCoverage], None]


def _text(value: object) -> str:
    return sanitize_text(str(value or ""))


def _score(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


_POST_ID_RE = re.compile(r"/comments/([^/]+)")


def _thread_key(item: dict[str, Any]) -> str:
    if item.get("submissionType") == "post":
        return str(item.get("submissionId") or "")
    return str(item.get("parentPostId") or "").removeprefix("t3_")


def _key_from_url(url: str) -> str:
    match = _POST_ID_RE.search(url)
    return match.group(1) if match else url


class RedditStealthExtractor:
    def __init__(
        self,
        fetcher: object | None = None,
        *,
        thread_limit: int | None = None,
        reddrix_factory: ReddrixFactory | None = None,
        prior_threads: list[LoreThread] | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> None:
        settings = getattr(fetcher, "settings", None)
        self.posts_per_job = (
            thread_limit
            if thread_limit is not None
            else int(getattr(settings, "reddit_posts_per_job", _DEFAULT_POSTS))
        )
        self.inflight = max(
            1,
            int(getattr(settings, "reddit_inflight", _DEFAULT_INFLIGHT)),
        )
        self.thread_limit = thread_limit
        self._reddrix_factory = reddrix_factory
        self._prior = {
            _key_from_url(thread.source.url): thread for thread in (prior_threads or [])
        }
        self._on_chunk = on_chunk

    def _factory(self) -> ReddrixFactory:
        if self._reddrix_factory is not None:
            return self._reddrix_factory
        try:
            from reddrix import Reddrix
        except ImportError as exc:
            raise FetchError(
                "reddrix is not installed; pip install reddrix && reddrix install"
            ) from exc
        return Reddrix

    def _jobs(self) -> list[dict[str, Any]]:
        max_posts = self.posts_per_job
        shared = {
            "stealth": False,
            "include_comments": True,
            "max_posts_per_collection": max_posts,
            "max_comments_per_post": _MAX_COMMENTS,
            "max_top_comments_per_post": _MAX_COMMENTS,
            "max_comments_depth": 0,
            "max_results": max_posts * (_MAX_COMMENTS + 1),
            "verbose": False,
        }
        jobs = [
            {
                **shared,
                "mode": "standard",
                "subreddit_urls": list(REDDIT_SUBREDDITS),
                "sort": "top_all_time",
            }
        ]
        jobs.extend(
            {**shared, "mode": "keyword_search", "query": query}
            for query in REDDIT_SEARCH_QUERIES
        )
        return jobs

    def _take_post(self, threads: dict[str, LoreThread], post_id: str) -> bool:
        if post_id in threads:
            return True
        return self.thread_limit is None or len(threads) < self.thread_limit

    def _comment(self, item: dict[str, Any]) -> LoreComment | None:
        body = _text(item.get("bodyText"))
        permalink = _text(item.get("submissionUrl") or item.get("parentPostUrl"))
        if len(body) < 40 or body == REDACTION or not permalink.startswith("http"):
            return None
        return LoreComment(
            author=_text(item.get("author")) or "[anonymous]",
            body=body,
            score=_score(item.get("score")),
            permalink=permalink,
        )

    def _attach_comment(self, thread: LoreThread, comment: LoreComment) -> None:
        thread.comments = sorted(
            [*thread.comments, comment],
            key=lambda item: item.score,
            reverse=True,
        )[:_MAX_COMMENTS]

    def _ingest(
        self,
        item: dict[str, Any],
        threads: dict[str, LoreThread],
        pending: dict[str, list[LoreComment]],
    ) -> None:
        key = _thread_key(item)
        kind = item.get("submissionType")
        if not key:
            return
        if kind == "comment":
            comment = self._comment(item)
            if comment is None:
                return
            if key in threads:
                self._attach_comment(threads[key], comment)
            else:
                pending.setdefault(key, []).append(comment)
            return
        if kind != "post" or not self._take_post(threads, key):
            return
        title = _text(item.get("title"))
        url = _text(item.get("submissionUrl"))
        if not title or not url.startswith("http"):
            return
        if key in threads:
            current = threads[key]
            body = _text(item.get("bodyText"))
            if body:
                current.body = body
            current.score = _score(item.get("score"))
            current.keywords = keyword_hits(f"{current.title}\n{current.body}", LORE_KEYWORDS)
            for comment in pending.pop(key, []):
                self._attach_comment(current, comment)
            return
        body = _text(item.get("bodyText"))
        comments = pending.pop(key, [])
        thread = LoreThread(
            title=title,
            body=body,
            score=_score(item.get("score")),
            keywords=keyword_hits(f"{title}\n{body}", LORE_KEYWORDS),
            comments=[],
            source=source_reference(url, title),
        )
        for comment in comments:
            self._attach_comment(thread, comment)
        threads[key] = thread

    def _flush(self, threads: dict[str, LoreThread], done: int, total: int) -> None:
        if self._on_chunk is None or not threads:
            return
        self._on_chunk(
            list(threads.values()),
            ExtractionCoverage(
                source="reddit",
                status=CoverageStatus.PARTIAL,
                attempted=total,
                succeeded=done,
                reason=f"reddit chunk {done}/{total}",
            ),
        )

    def _limit(self, client: Any) -> None:
        if hasattr(client, "page_semaphore"):
            client.page_semaphore = asyncio.Semaphore(self.inflight)
        if hasattr(client, "request_semaphore"):
            client.request_semaphore = asyncio.Semaphore(self.inflight)

    async def extract(self) -> tuple[list[LoreThread], ExtractionCoverage]:
        factory = self._factory()
        jobs = self._jobs()
        threads = dict(self._prior)
        pending: dict[str, list[LoreComment]] = {}
        job_failures = 0
        total = len(jobs)
        for index, kwargs in enumerate(jobs, start=1):
            try:
                async with factory(**kwargs) as client:
                    self._limit(client)
                    async for item in client.get_items():
                        if isinstance(item, dict):
                            self._ingest(item, threads, pending)
            except FetchError:
                job_failures += 1
            except Exception:
                job_failures += 1
            self._flush(threads, index, total)
        if not threads:
            raise FetchError("no Reddit threads were discovered")
        reason = f"{job_failures} reddrix jobs failed" if job_failures else None
        return list(threads.values()), ExtractionCoverage(
            source="reddit",
            status=CoverageStatus.PARTIAL if job_failures else CoverageStatus.COMPLETE,
            attempted=total,
            succeeded=max(0, len(jobs) - job_failures),
            reason=reason,
        )
