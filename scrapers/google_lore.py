"""Open-web lore research discovered through paginated Google result pages."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from config.settings import GOOGLE_SEARCH_BASE, RESEARCH_KEYWORDS, Settings, get_settings
from core.fetcher import FetchError, ResilientFetcher, node_attr, node_text, select_adaptive
from core.sanitizer import sanitize_payload
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    GoogleResearchPage,
    Song,
)
from scrapers.common import article_paragraphs, keyword_hits, page_title, source_reference

_BLOCK_MARKERS = (
    "our systems have detected unusual traffic",
    "unusual traffic from your computer network",
    "not a robot",
    "recaptcha",
)
_GOOGLE_HOSTS = ("google.com", "googleusercontent.com", "gstatic.com")
_SKIP_HOSTS = (
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "threads.net",
)


def research_queries(songs: list[Song]) -> tuple[str, ...]:
    general = (
        '"Sleep Token" lore mythology',
        '"Sleep Token" lyrics meaning interpretation',
        '"Sleep Token" song meanings',
        '"Sleep Token" album lore analysis',
        'site:reddit.com/r/ "Sleep Token" lore theory',
    )
    per_song = (
        query
        for song in songs
        for query in (
            f'"Sleep Token" "{song.title}" lyrics meaning',
            f'"Sleep Token" "{song.title}" lore interpretation',
        )
    )
    return tuple(dict.fromkeys((*general, *per_song)))


def skip_discovered_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    path_parts = {part for part in parsed.path.casefold().split("/") if part}
    if any(host == item or host.endswith(f".{item}") for item in _SKIP_HOSTS):
        return True
    return bool(path_parts & {"login", "signin", "signup", "account"})


def google_results(page: object) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in select_adaptive(page, ("a[href]",)):
        href = node_attr(anchor, "href")
        if href.startswith("/url?"):
            href = parse_qs(urlparse(href).query).get("q", [""])[0]
        parsed = urlparse(href)
        host = (parsed.hostname or "").casefold()
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or any(host == item or host.endswith(f".{item}") for item in _GOOGLE_HOSTS)
            or href in seen
        ):
            continue
        seen.add(href)
        results.append((href, node_text(anchor) or host))
    return results


def _blocked(page: object) -> bool:
    text = node_text(page).casefold()
    return any(marker in text for marker in _BLOCK_MARKERS)


class GoogleLoreExtractor:
    def __init__(
        self,
        fetcher: ResilientFetcher,
        settings: Settings | None = None,
        *,
        queries: tuple[str, ...] | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.settings = settings or get_settings()
        self.queries = queries
        self.checkpoint = self.settings.data_dir / "google.json"

    def _load(self, resume: bool) -> tuple[list[GoogleResearchPage], set[str]]:
        if not resume or not self.checkpoint.exists():
            return [], set()
        payload = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        records = [
            GoogleResearchPage.model_validate(item, strict=False)
            for item in payload.get("records", [])
        ]
        return records, set(payload.get("completed_queries", []))

    def _save(
        self,
        records: list[GoogleResearchPage],
        completed_queries: set[str],
        coverage: ExtractionCoverage,
    ) -> None:
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        payload = sanitize_payload(
            {
                "source": "google",
                "coverage": coverage.model_dump(mode="json"),
                "completed_queries": sorted(completed_queries),
                "records": [record.model_dump(mode="json") for record in records],
            }
        )
        temporary = self.checkpoint.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.checkpoint)

    async def extract(
        self,
        songs: list[Song],
        *,
        resume: bool,
    ) -> tuple[list[GoogleResearchPage], ExtractionCoverage]:
        records, completed_queries = self._load(resume)
        seen_urls = {record.url for record in records}
        queries = self.queries or research_queries(songs)
        attempted = 0
        succeeded = 0
        failures = 0

        for query in queries:
            if query in completed_queries:
                continue
            start = 0
            while True:
                search_url = f"{GOOGLE_SEARCH_BASE}?{urlencode({'q': query, 'start': start, 'filter': 0})}"
                attempted += 1
                try:
                    page = await self.fetcher.fetch_public_page(search_url, mode="async")
                except FetchError:
                    return self._finish(
                        records,
                        completed_queries,
                        attempted,
                        succeeded,
                        "Google blocked or rejected the search request",
                    )
                if _blocked(page):
                    return self._finish(
                        records,
                        completed_queries,
                        attempted,
                        succeeded,
                        "Google returned a traffic or CAPTCHA block",
                    )

                results = google_results(page)
                new_results = [(url, title) for url, title in results if url not in seen_urls]
                if not results or not new_results:
                    completed_queries.add(query)
                    self._save(
                        records,
                        completed_queries,
                        ExtractionCoverage(
                            source="google",
                            status=CoverageStatus.PARTIAL,
                            attempted=attempted,
                            succeeded=succeeded,
                            reason="crawl in progress",
                        ),
                    )
                    break

                for url, result_title in new_results:
                    seen_urls.add(url)
                    if skip_discovered_url(url):
                        continue
                    attempted += 1
                    try:
                        article = await self.fetcher.fetch_public_page(url, mode="async")
                        paragraphs = article_paragraphs(article)
                    except FetchError:
                        failures += 1
                        continue
                    terms = (*RESEARCH_KEYWORDS, *(song.title for song in songs))
                    if not any(keyword_hits(paragraph, terms) for paragraph in paragraphs):
                        continue
                    records.append(
                        GoogleResearchPage(
                            query=query,
                            title=page_title(article, result_title),
                            url=url,
                            paragraphs=paragraphs,
                            keywords=keyword_hits(" ".join(paragraphs), terms),
                            source=source_reference(url, result_title, confidence=0.55),
                        )
                    )
                    succeeded += 1

                self._save(
                    records,
                    completed_queries,
                    ExtractionCoverage(
                        source="google",
                        status=CoverageStatus.PARTIAL,
                        attempted=attempted,
                        succeeded=succeeded,
                        reason="crawl in progress",
                    ),
                )
                start += 10

        status = CoverageStatus.COMPLETE if records else CoverageStatus.FAILED
        reason = None if records else "Google search completed without relevant pages"
        if failures and records:
            status = CoverageStatus.PARTIAL
            reason = f"{failures} discovered pages were unavailable"
        coverage = ExtractionCoverage(
            source="google",
            status=status,
            attempted=attempted,
            succeeded=succeeded,
            reason=reason,
        )
        self._save(records, completed_queries, coverage)
        return records, coverage

    def _finish(
        self,
        records: list[GoogleResearchPage],
        completed_queries: set[str],
        attempted: int,
        succeeded: int,
        reason: str,
    ) -> tuple[list[GoogleResearchPage], ExtractionCoverage]:
        coverage = ExtractionCoverage(
            source="google",
            status=CoverageStatus.PARTIAL if records else CoverageStatus.FAILED,
            attempted=attempted,
            succeeded=succeeded,
            reason=reason,
        )
        self._save(records, completed_queries, coverage)
        return records, coverage
