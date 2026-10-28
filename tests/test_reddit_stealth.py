from __future__ import annotations

import unittest
from typing import Any

from core.fetcher import FetchError
from models.schemas import CoverageStatus, LoreThread, SourceKind, SourceReference
from scrapers.reddit_stealth import RedditStealthExtractor


class FakeReddrix:
    def __init__(self, items: list[dict[str, Any]], **kwargs: Any) -> None:
        self.items = items
        self.kwargs = kwargs
        self.page_semaphore = None
        self.request_semaphore = None

    async def __aenter__(self) -> FakeReddrix:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_items(self):
        for item in self.items:
            yield item


class SequencedFactory:
    def __init__(self, batches: list[list[dict[str, Any]]]) -> None:
        self.batches = list(batches)
        self.calls: list[dict[str, Any]] = []
        self.clients: list[FakeReddrix] = []

    def __call__(self, **kwargs: Any) -> FakeReddrix:
        self.calls.append(kwargs)
        items = self.batches.pop(0) if self.batches else []
        client = FakeReddrix(items, **kwargs)
        self.clients.append(client)
        return client


def _post(
    submission_id: str,
    title: str,
    body: str,
    *,
    score: int = 10,
    num_comments: int = 1,
) -> dict[str, Any]:
    return {
        "submissionId": submission_id,
        "submissionIdPrefixed": f"t3_{submission_id}",
        "submissionType": "post",
        "submissionUrl": (
            f"https://www.reddit.com/r/SleepToken/comments/{submission_id}/thread/"
        ),
        "title": title,
        "bodyText": body,
        "author": "lorefan",
        "score": score,
        "numComments": num_comments,
        "parentPostId": None,
    }


def _comment(
    submission_id: str,
    post_id: str,
    body: str,
    *,
    score: int = 5,
) -> dict[str, Any]:
    return {
        "submissionId": submission_id,
        "submissionIdPrefixed": f"t1_{submission_id}",
        "submissionType": "comment",
        "submissionUrl": (
            f"https://www.reddit.com/r/SleepToken/comments/{post_id}/thread/"
            f"{submission_id}/"
        ),
        "title": None,
        "bodyText": body,
        "author": "commenter",
        "score": score,
        "parentPostId": f"t3_{post_id}",
        "parentPostUrl": f"https://www.reddit.com/r/SleepToken/comments/{post_id}",
    }


class RedditReddrixTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_posts_and_comments_from_reddrix(self) -> None:
        factory = SequencedFactory(
            [
                [
                    _post(
                        "abc",
                        "A theory about Atlantic",
                        "Atlantic and ocean descent analysis.",
                    ),
                    _comment(
                        "c1",
                        "abc",
                        "The Eden rune alphabet is a cipher in this era.",
                        score=12,
                    ),
                ]
            ]
        )
        records, coverage = await RedditStealthExtractor(
            object(),
            reddrix_factory=factory,
        ).extract()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].title, "A theory about Atlantic")
        self.assertEqual(len(records[0].comments), 1)
        self.assertEqual(records[0].comments[0].score, 12)
        self.assertEqual(records[0].comments[0].author, "commenter")
        self.assertEqual(coverage.status, CoverageStatus.COMPLETE)
        self.assertTrue(
            any(call.get("sort") == "top_all_time" for call in factory.calls)
        )
        self.assertTrue(
            any(call.get("mode") == "keyword_search" for call in factory.calls)
        )
        self.assertTrue(all(call.get("stealth") is False for call in factory.calls))
        self.assertIsNotNone(factory.clients[0].page_semaphore)
        self.assertIsNotNone(factory.clients[0].request_semaphore)

    async def test_chunks_keep_prior_threads(self) -> None:
        flushed: list[str] = []

        def on_chunk(records: list[LoreThread], coverage: Any) -> None:
            flushed.append(coverage.reason or "")
            self.assertGreaterEqual(len(records), 1)

        prior = LoreThread(
            title="Already saved lore",
            body="A theory kept from the previous chunk.",
            source=SourceReference(
                url="https://www.reddit.com/r/SleepToken/comments/saved/thread/",
                title="Already saved lore",
                kind=SourceKind.COMMUNITY,
            ),
        )
        records, _coverage = await RedditStealthExtractor(
            object(),
            reddrix_factory=SequencedFactory(
                [
                    [
                        _post(
                            "abc",
                            "A theory about Atlantic",
                            "Atlantic and ocean descent analysis.",
                        )
                    ]
                ]
            ),
            prior_threads=[prior],
            on_chunk=on_chunk,
        ).extract()
        titles = {record.title for record in records}
        self.assertIn("Already saved lore", titles)
        self.assertIn("A theory about Atlantic", titles)
        self.assertTrue(flushed)
        self.assertTrue(flushed[0].startswith("reddit chunk"))

    async def test_default_does_not_truncate_discovered_threads(self) -> None:
        posts = [
            _post(
                str(index),
                f"Sleep Token lore theory {index}",
                "A detailed lore interpretation from Reddit.",
            )
            for index in range(30)
        ]
        records, _coverage = await RedditStealthExtractor(
            object(),
            reddrix_factory=SequencedFactory([posts]),
        ).extract()
        self.assertEqual(len(records), 30)

    async def test_empty_discovery_is_a_hard_failure(self) -> None:
        with self.assertRaisesRegex(FetchError, "no Reddit threads"):
            await RedditStealthExtractor(
                object(),
                reddrix_factory=SequencedFactory([[]]),
            ).extract()

    async def test_job_failure_is_partial_when_threads_exist(self) -> None:
        class Boom(FakeReddrix):
            async def get_items(self):
                raise RuntimeError("blocked")
                yield {}  # pragma: no cover

        calls: list[dict[str, Any]] = []

        def factory(**kwargs: Any) -> FakeReddrix:
            calls.append(kwargs)
            if kwargs.get("mode") == "standard":
                return Boom([])
            return FakeReddrix(
                [
                    _post(
                        "xyz",
                        "Sleep Token lore search hit",
                        "A detailed lore interpretation from Reddit.",
                    )
                ]
            )

        records, coverage = await RedditStealthExtractor(
            object(),
            reddrix_factory=factory,
        ).extract()
        self.assertEqual(len(records), 1)
        self.assertEqual(coverage.status, CoverageStatus.PARTIAL)
        self.assertIn("reddrix jobs failed", coverage.reason or "")
        self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
