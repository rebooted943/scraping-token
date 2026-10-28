"""Bounded, allowlisted HTTP and Scrapling transport primitives."""

from __future__ import annotations

import asyncio
import ipaddress
import random
import socket
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from config.settings import ALLOWED_SOURCE_DOMAINS, Settings, get_settings
from core.sanitizer import sanitize_payload

FetchMode = Literal["async", "stealth", "dynamic"]


class FetchError(RuntimeError):
    """Base transport failure without response-body leakage."""


class PermanentFetchError(FetchError):
    """A response that retries must not attempt to bypass."""


class SourceNotAllowedError(PermanentFetchError):
    """A URL outside the configured research boundary."""


class ResilientFetcher:
    """Shared async transport with retry, pacing, and browser fallbacks."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None
        self._semaphores: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.settings.max_concurrency)
        )
        self._rate_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}

    async def __aenter__(self) -> ResilientFetcher:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.request_timeout,
                follow_redirects=True,
                headers={"User-Agent": self.settings.user_agent},
            )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def ensure_allowed(url: str) -> str:
        hostname = (urlparse(url).hostname or "").casefold()
        if hostname not in ALLOWED_SOURCE_DOMAINS:
            raise SourceNotAllowedError(f"source domain is not allowlisted: {hostname}")
        return hostname

    async def _pace(self, hostname: str) -> None:
        if hostname.endswith("reddit.com"):
            interval = self.settings.reddit_min_interval
        elif hostname.endswith("google.com"):
            interval = self.settings.google_min_interval
        else:
            interval = 0.0
        if interval <= 0:
            return
        async with self._rate_locks[hostname]:
            remaining = interval - (time.monotonic() - self._last_request.get(hostname, 0.0))
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request[hostname] = time.monotonic()

    def _retry_delay(self, attempt: int, headers: Mapping[str, str] | None = None) -> float:
        headers = headers or {}
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(retry_after)
                    return max(0.0, parsed.timestamp() - time.time())
                except (TypeError, ValueError):
                    pass
        reset = headers.get("x-ratelimit-reset")
        if reset:
            try:
                return max(0.0, float(reset))
            except ValueError:
                pass
        return self.settings.backoff_base * (2**attempt) + random.uniform(0.0, 0.25)

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        hostname = self.ensure_allowed(url)
        if self._client is None:
            raise RuntimeError("ResilientFetcher must be used as an async context manager")
        async with self._semaphores[hostname]:
            for attempt in range(self.settings.max_retries + 1):
                await self._pace(hostname)
                try:
                    response = await self._client.get(url, params=params, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.settings.max_retries:
                        raise FetchError(f"network failure for {hostname}") from exc
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                if response.status_code in {401, 403}:
                    raise PermanentFetchError(
                        f"access denied by {hostname} ({response.status_code})"
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt >= self.settings.max_retries:
                        raise FetchError(
                            f"retry budget exhausted for {hostname} ({response.status_code})"
                        )
                    await asyncio.sleep(self._retry_delay(attempt, response.headers))
                    continue
                try:
                    response.raise_for_status()
                    payload = response.json()
                except (httpx.HTTPStatusError, ValueError) as exc:
                    raise PermanentFetchError(
                        f"invalid response from {hostname} ({response.status_code})"
                    ) from exc
                if not isinstance(payload, dict):
                    raise PermanentFetchError(f"expected JSON object from {hostname}")
                return sanitize_payload(payload)
        raise FetchError(f"unreachable retry state for {hostname}")

    async def fetch_text(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        """Fetch allowlisted text (RSS/Atom) with the configured client, not Scrapling."""
        hostname = self.ensure_allowed(url)
        if self._client is None:
            raise RuntimeError("ResilientFetcher must be used as an async context manager")
        request_headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "application/atom+xml,application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            request_headers.update(headers)
        async with self._semaphores[hostname]:
            for attempt in range(self.settings.max_retries + 1):
                await self._pace(hostname)
                try:
                    response = await self._client.get(url, headers=request_headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.settings.max_retries:
                        raise FetchError(f"network failure for {hostname}") from exc
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                if response.status_code in {401, 403}:
                    raise PermanentFetchError(
                        f"access denied by {hostname} ({response.status_code})"
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt >= self.settings.max_retries:
                        raise FetchError(
                            f"retry budget exhausted for {hostname} ({response.status_code})"
                        )
                    await asyncio.sleep(self._retry_delay(attempt, response.headers))
                    continue
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise PermanentFetchError(
                        f"invalid response from {hostname} ({response.status_code})"
                    ) from exc
                return response.text
        raise FetchError(f"unreachable retry state for {hostname}")

    async def fetch_page(self, url: str, *, mode: FetchMode = "async") -> Any:
        hostname = self.ensure_allowed(url)
        return await self._fetch_page(url, hostname, mode)

    async def fetch_public_page(self, url: str, *, mode: FetchMode = "async") -> Any:
        """Fetch a public HTTP(S) page discovered by the research crawler."""
        hostname = await self.ensure_public(url)
        return await self._fetch_page(url, hostname, mode)

    @staticmethod
    async def ensure_public(url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold()
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise SourceNotAllowedError("external source must use HTTP(S)")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise SourceNotAllowedError("local sources are not allowed")
        try:
            addresses = {ipaddress.ip_address(hostname)}
        except ValueError:
            try:
                info = await asyncio.to_thread(
                    socket.getaddrinfo,
                    hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as exc:
                raise FetchError(f"DNS lookup failed for {hostname}") from exc
            addresses = {ipaddress.ip_address(item[4][0]) for item in info}
        if not addresses or any(not address.is_global for address in addresses):
            raise SourceNotAllowedError(f"non-public source is not allowed: {hostname}")
        return hostname

    async def _fetch_page(self, url: str, hostname: str, mode: FetchMode) -> Any:
        async with self._semaphores[hostname]:
            for attempt in range(self.settings.max_retries + 1):
                await self._pace(hostname)
                try:
                    page = await self._scrapling_fetch(url, mode)
                    status = int(getattr(page, "status", 200) or 200)
                    if status in {401, 403}:
                        raise PermanentFetchError(f"access denied by {hostname} ({status})")
                    if status == 429 or status >= 500:
                        raise FetchError(f"transient response from {hostname} ({status})")
                    if status >= 400:
                        raise PermanentFetchError(f"HTTP {status} from {hostname}")
                    return page
                except PermanentFetchError:
                    raise
                except Exception as exc:
                    if attempt >= self.settings.max_retries:
                        raise FetchError(f"page fetch failed for {hostname}") from exc
                    await asyncio.sleep(self._retry_delay(attempt))
        raise FetchError(f"unreachable retry state for {hostname}")

    async def _scrapling_fetch(self, url: str, mode: FetchMode) -> Any:
        try:
            from scrapling.fetchers import (
                AsyncDynamicSession,
                AsyncFetcher,
                AsyncStealthySession,
            )
        except ImportError as exc:
            raise FetchError(
                "Scrapling fetchers are unavailable; install requirements and run "
                "`scrapling install`"
            ) from exc

        headers = {"User-Agent": self.settings.user_agent}
        if mode == "async":
            return await AsyncFetcher.get(
                url,
                headers=headers,
                timeout=self.settings.request_timeout,
                retries=0,
            )
        session_type = AsyncStealthySession if mode == "stealth" else AsyncDynamicSession
        async with session_type(max_pages=1) as session:
            return await session.fetch(url, extra_headers=headers)


def select_adaptive(page: Any, selectors: Iterable[str]) -> list[Any]:
    """Try saved adaptive selectors and deterministic fallbacks."""
    for selector in selectors:
        try:
            matches = list(page.css(selector, adaptive=True))
        except (TypeError, ValueError):
            matches = []
        if matches:
            return matches
        try:
            matches = list(page.css(selector, auto_save=True))
        except (TypeError, ValueError):
            matches = list(page.css(selector))
        if matches:
            return matches
    return []


def node_text(node: Any) -> str:
    """Read the full text of a node, including text inside inline children."""
    get_all_text = getattr(node, "get_all_text", None)
    if callable(get_all_text):
        value = get_all_text(separator=" ", strip=True)
    else:
        value = getattr(node, "text", "")
        if callable(value):
            value = value()
    return " ".join(str(value or "").split())


def node_attr(node: Any, name: str, default: str = "") -> str:
    """Read an attribute from Scrapling selector nodes."""
    attrib = getattr(node, "attrib", None)
    if isinstance(attrib, Mapping):
        return str(attrib.get(name, default) or default)
    getter = getattr(node, "get", None)
    if callable(getter):
        return str(getter(name, default) or default)
    return default
