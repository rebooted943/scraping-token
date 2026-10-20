"""Shared deterministic extraction helpers for allowlisted articles."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlparse

from core.fetcher import node_attr, node_text, select_adaptive
from core.sanitizer import REDACTION, sanitize_text
from models.schemas import SourceKind, SourceReference

ARTICLE_SELECTORS = (
    "article p, article li, article figcaption, article td",
    ".article-body p, .article-body li, .article-body figcaption",
    ".content p, .content li, .content figcaption, .content td",
    ".mw-parser-output > p, .mw-parser-output > ul li, .mw-parser-output > ol li, .mw-parser-output table td, .mw-parser-output figcaption",
    "main p, main li, main figcaption, main td",
    "article p",
)
TITLE_SELECTORS = ("h1", "article h1", ".page-header__title", "title")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{20,1200})[”\"]")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def page_title(page: object, fallback: str) -> str:
    nodes = select_adaptive(page, TITLE_SELECTORS)
    return sanitize_text(node_text(nodes[0])) if nodes else fallback


def article_paragraphs(
    page: object,
    selectors: Iterable[str] = ARTICLE_SELECTORS,
    *,
    minimum_length: int = 30,
) -> list[str]:
    seen: set[str] = set()
    paragraphs: list[str] = []
    for node in select_adaptive(page, selectors):
        text = sanitize_text(node_text(node))
        if len(text) < minimum_length or text == REDACTION or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    return paragraphs


def source_kind(url: str) -> SourceKind:
    host = (urlparse(url).hostname or "").casefold()
    if host.endswith("reddit.com") or host.endswith("fandom.com"):
        return SourceKind.COMMUNITY
    if host in {"sleep-token.com", "www.sleep-token.com"}:
        return SourceKind.CANONICAL
    return SourceKind.EDITORIAL


def source_reference(url: str, title: str, confidence: float | None = None) -> SourceReference:
    kind = source_kind(url)
    default_confidence = {
        SourceKind.CANONICAL: 0.95,
        SourceKind.EDITORIAL: 0.75,
        SourceKind.COMMUNITY: 0.5,
    }[kind]
    return SourceReference(
        url=url,
        title=title,
        kind=kind,
        confidence=default_confidence if confidence is None else confidence,
    )


def extract_quotes(page: object, paragraphs: Iterable[str]) -> list[str]:
    quotes: list[str] = []
    for node in select_adaptive(page, ("blockquote", "q", ".pull-quote")):
        text = sanitize_text(node_text(node))
        if len(text) >= 20 and text != REDACTION:
            quotes.append(text.strip("“”\" "))
    for paragraph in paragraphs:
        quotes.extend(
            sanitize_text(match).strip()
            for match in QUOTE_RE.findall(paragraph)
            if sanitize_text(match) != REDACTION
        )
    return list(dict.fromkeys(quote for quote in quotes if len(quote) >= 20))


def keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in lowered]


def analytical_sentences(text: str, keywords: Iterable[str]) -> list[str]:
    return [
        sentence.strip()
        for sentence in SENTENCE_RE.split(text)
        if len(sentence.strip()) >= 40 and keyword_hits(sentence, keywords)
    ]


def absolute_href(node: object, base_url: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base_url, node_attr(node, "href"))
