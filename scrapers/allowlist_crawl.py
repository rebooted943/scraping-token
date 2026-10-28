"""BFS over allowlisted URLs: same-host pages first, then other allowlisted hosts."""

from __future__ import annotations

from collections import deque
from urllib.parse import urlparse

from config.settings import ALLOWED_SOURCE_DOMAINS
from core.fetcher import FetchError, select_adaptive
from scrapers.common import absolute_href, article_paragraphs


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold()


def normalize_url(url: str) -> str:
    cleaned = url.strip().split("#", 1)[0]
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.hostname.casefold()}{path}{query}"


def iter_allowlisted_links(page: object, base_url: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for node in select_adaptive(page, ("a[href]",)):
        href = normalize_url(absolute_href(node, base_url))
        if not href or href in seen or _host(href) not in ALLOWED_SOURCE_DOMAINS:
            continue
        seen.add(href)
        links.append(href)
    return links


async def _load_page(fetcher: object, url: str) -> object:
    page = await fetcher.fetch_page(url, mode="stealth")  # type: ignore[attr-defined]
    if article_paragraphs(page):
        return page
    return await fetcher.fetch_page(url, mode="dynamic")  # type: ignore[attr-defined]


async def crawl_pages(
    fetcher: object,
    seeds: tuple[str, ...] | list[str],
    *,
    max_pages: int,
    max_depth: int,
) -> list[tuple[str, object | None]]:
    """Fetch seeds, then same-host links, then other allowlisted hosts."""
    seed_hosts = {_host(url) for url in seeds}
    primary: deque[tuple[str, int]] = deque()
    secondary: deque[tuple[str, int]] = deque()
    queued: set[str] = set()
    visited: set[str] = set()
    pages: list[tuple[str, object | None]] = []

    def enqueue(url: str, depth: int) -> None:
        normalized = normalize_url(url)
        if (
            not normalized
            or depth > max_depth
            or normalized in visited
            or normalized in queued
            or _host(normalized) not in ALLOWED_SOURCE_DOMAINS
        ):
            return
        queued.add(normalized)
        target = primary if _host(normalized) in seed_hosts else secondary
        target.append((normalized, depth))

    for seed in seeds:
        enqueue(seed, 0)

    while (primary or secondary) and len(pages) < max_pages:
        url, depth = primary.popleft() if primary else secondary.popleft()
        queued.discard(url)
        if url in visited:
            continue
        visited.add(url)
        try:
            page = await _load_page(fetcher, url)
        except FetchError:
            pages.append((url, None))
            continue
        pages.append((url, page))
        for link in iter_allowlisted_links(page, url):
            enqueue(link, depth + 1)
    return pages
