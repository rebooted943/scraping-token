"""Bounded mythology, cipher, bathymetry, and visual-symbol extraction."""

from __future__ import annotations

from config.settings import WIKI_ARG_SEEDS
from core.fetcher import ResilientFetcher, node_attr, select_adaptive
from core.sanitizer import REDACTION, sanitize_text
from models.schemas import CoverageStatus, ExtractionCoverage, VisualSymbol
from scrapers.allowlist_crawl import crawl_pages
from scrapers.common import article_paragraphs, keyword_hits, page_title, source_reference

_VISUAL_TERMS = (
    "alchemical",
    "alphabet",
    "bathymetry",
    "character",
    "cipher",
    "costume",
    "depth",
    "entity",
    "fathom",
    "mask",
    "ocean",
    "rune",
    "sigil",
    "symbol",
)


def _classify(text: str) -> tuple[str, str, str | None]:
    lowered = text.casefold()
    if any(term in lowered for term in ("rune", "cipher", "alphabet")):
        return "cryptography", "The Eden Runic Alphabet", "Era III: Take Me Back to Eden"
    if any(term in lowered for term in ("alchemical", "sigil")):
        return "sigils", "The Twelve Sundowning Sigils", "Era I: Sundowning"
    if any(term in lowered for term in ("depth", "fathom", "bathym", "ocean")):
        return (
            "bathymetry",
            "This Place Will Become Your Tomb Depths",
            "Era II: This Place Will Become Your Tomb",
        )
    if any(term in lowered for term in ("mask", "costume", "attire")):
        return "visual identity", "Mask and Ritual Attire Evolution", None
    if any(term in lowered for term in ("character", "entity")):
        return "entities", "Take Me Back to Eden Entities", "Era III: Take Me Back to Eden"
    return "mythology", "Sleep Token Visual Lore", None


class WikiAndArgExtractor:
    def __init__(self, fetcher: ResilientFetcher) -> None:
        self.fetcher = fetcher

    async def extract(self) -> tuple[list[VisualSymbol], ExtractionCoverage]:
        records: list[VisualSymbol] = []
        seen: set[tuple[str, str]] = set()
        settings = getattr(self.fetcher, "settings", None)
        pages = await crawl_pages(
            self.fetcher,
            WIKI_ARG_SEEDS,
            max_pages=getattr(settings, "crawl_max_pages", 40),
            max_depth=getattr(settings, "crawl_max_depth", 2),
        )
        failures = 0
        for url, page in pages:
            if page is None:
                failures += 1
                continue
            paragraphs = article_paragraphs(page)
            title = page_title(page, "Sleep Token lore source")
            source = source_reference(url, title)
            image_descriptions = [
                sanitize_text(node_attr(node, "alt"))
                for node in select_adaptive(
                    page,
                    (
                        "article img[alt]",
                        ".mw-parser-output img[alt]",
                        "main img[alt]",
                    ),
                )
            ]
            paragraphs.extend(
                description
                for description in image_descriptions
                if description and description != REDACTION
            )
            for paragraph in paragraphs:
                if not keyword_hits(paragraph, _VISUAL_TERMS):
                    continue
                category, name, era = _classify(paragraph)
                key = (name, paragraph.casefold())
                if key in seen:
                    continue
                seen.add(key)
                records.append(
                    VisualSymbol(
                        category=category,
                        name=name,
                        description=paragraph,
                        era=era,
                        source=source,
                    )
                )
        status = CoverageStatus.COMPLETE if failures == 0 else CoverageStatus.PARTIAL
        return records, ExtractionCoverage(
            source="wiki_and_arg",
            status=status,
            attempted=len(pages),
            succeeded=len(pages) - failures,
            reason=f"{failures} allowlisted sources unavailable" if failures else None,
        )
