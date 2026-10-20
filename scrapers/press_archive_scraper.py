"""Canonical in-character interview quote extraction from allowlisted press."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from config.settings import PRESS_SEEDS
from core.fetcher import FetchError, ResilientFetcher, node_attr, select_adaptive
from core.sanitizer import REDACTION, sanitize_text
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    InterviewQuote,
    SourceKind,
    SourceReference,
)
from scrapers.common import article_paragraphs, extract_quotes, page_title


def _publication(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold()
    if "kerrang" in host:
        return "Kerrang!"
    if "loudersound" in host:
        return "Metal Hammer / Louder"
    return host


def _published_date(page: object) -> date | None:
    nodes = select_adaptive(page, ("time[datetime]", "meta[property='article:published_time']"))
    if not nodes:
        return None
    value = node_attr(nodes[0], "datetime") or node_attr(nodes[0], "content")
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


class PressArchiveExtractor:
    def __init__(self, fetcher: ResilientFetcher) -> None:
        self.fetcher = fetcher

    async def _fetch_with_archive(self, url: str) -> tuple[object, str]:
        try:
            return await self.fetcher.fetch_page(url, mode="stealth"), url
        except FetchError:
            archive_url = f"https://web.archive.org/web/2/{url}"
            return await self.fetcher.fetch_page(archive_url, mode="dynamic"), archive_url

    async def extract(self) -> tuple[list[InterviewQuote], ExtractionCoverage]:
        quotes: list[InterviewQuote] = []
        failures = 0
        seen: set[str] = set()
        for url in PRESS_SEEDS:
            try:
                page, resolved_url = await self._fetch_with_archive(url)
                paragraphs = article_paragraphs(page)
            except FetchError:
                failures += 1
                continue
            title = page_title(page, "Sleep Token interview")
            published = _published_date(page)
            for quote in extract_quotes(page, paragraphs):
                if quote == REDACTION or quote.casefold() in seen:
                    continue
                contexts = [paragraph for paragraph in paragraphs if quote in paragraph]
                context = contexts[0] if contexts else title
                if "vessel" not in context.casefold() and "sleep token" not in title.casefold():
                    continue
                seen.add(quote.casefold())
                quotes.append(
                    InterviewQuote(
                        speaker="Vessel",
                        quote=sanitize_text(quote),
                        context=sanitize_text(context),
                        publication=_publication(url),
                        published_at=published,
                        source=SourceReference(
                            url=resolved_url,
                            title=title,
                            kind=SourceKind.CANONICAL,
                            confidence=0.95,
                        ),
                    )
                )
        status = CoverageStatus.COMPLETE if failures == 0 else CoverageStatus.PARTIAL
        return quotes, ExtractionCoverage(
            source="press",
            status=status,
            attempted=len(PRESS_SEEDS),
            succeeded=len(PRESS_SEEDS) - failures,
            reason=f"{failures} live and archive sources unavailable" if failures else None,
        )
