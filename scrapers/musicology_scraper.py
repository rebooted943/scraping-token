"""Extractive musical-analysis and lyrical-callback collector."""

from __future__ import annotations

from config.settings import MOTIF_KEYWORDS, MUSICOLOGY_SEEDS
from core.fetcher import FetchError, ResilientFetcher
from models.schemas import CoverageStatus, ExtractionCoverage, MusicologyInsight
from scrapers.common import article_paragraphs, keyword_hits, page_title, source_reference

_CALLBACK_TERMS = (
    "callback",
    "echoes",
    "leitmotif",
    "mirrors",
    "recurring",
    "reference",
    "reprise",
)
_TECHNICAL_TERMS = (
    "breakdown",
    "chord",
    "downtuned",
    "genre",
    "key change",
    "melody",
    "meter",
    "polyrhythm",
    "rhythm",
    "riff",
    "syncopation",
    "tempo",
    "time signature",
    "tuning",
)
_ALL_TERMS = tuple(
    dict.fromkeys(
        (*_CALLBACK_TERMS, *_TECHNICAL_TERMS, *(term for terms in MOTIF_KEYWORDS.values() for term in terms))
    )
)


def _topic(text: str) -> str:
    if keyword_hits(text, _CALLBACK_TERMS):
        return "Inter-track callback"
    if keyword_hits(text, _TECHNICAL_TERMS):
        return "Musical technique"
    for category, terms in MOTIF_KEYWORDS.items():
        if keyword_hits(text, terms):
            return category.replace("_", " ").title()
    return "Lyrical motif"


class MusicologyExtractor:
    def __init__(self, fetcher: ResilientFetcher) -> None:
        self.fetcher = fetcher

    async def extract(self) -> tuple[list[MusicologyInsight], ExtractionCoverage]:
        insights: list[MusicologyInsight] = []
        failures = 0
        seen: set[str] = set()
        for url in MUSICOLOGY_SEEDS:
            try:
                page = await self.fetcher.fetch_page(url, mode="stealth")
                paragraphs = article_paragraphs(page)
                if not paragraphs:
                    page = await self.fetcher.fetch_page(url, mode="dynamic")
                    paragraphs = article_paragraphs(page)
            except FetchError:
                failures += 1
                continue
            title = page_title(page, "Sleep Token musical analysis")
            source = source_reference(url, title)
            for paragraph in paragraphs:
                hits = keyword_hits(paragraph, _ALL_TERMS)
                normalized = paragraph.casefold()
                if not hits or normalized in seen:
                    continue
                seen.add(normalized)
                insights.append(
                    MusicologyInsight(
                        topic=_topic(paragraph),
                        summary=paragraph,
                        technical_terms=hits,
                        source=source,
                    )
                )
        status = CoverageStatus.COMPLETE if failures == 0 else CoverageStatus.PARTIAL
        return insights, ExtractionCoverage(
            source="musicology",
            status=status,
            attempted=len(MUSICOLOGY_SEEDS),
            succeeded=len(MUSICOLOGY_SEEDS) - failures,
            reason=f"{failures} allowlisted sources unavailable" if failures else None,
        )
