"""Fail-closed anonymity protection for every persisted or rendered value."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from config.settings import ALLOWED_CREDITS, DOXXING_PATTERNS, RISKY_MEDIA_PATTERNS

REDACTION = "[REDACTED - LORE ONLY]"
_PARAGRAPH_SPLIT = re.compile(r"(\r?\n[ \t]*\r?\n)")
_DOXXING_RE = re.compile("|".join(DOXXING_PATTERNS), re.IGNORECASE)
_RISKY_MEDIA_RE = re.compile("|".join(RISKY_MEDIA_PATTERNS), re.IGNORECASE)
_SENSITIVE_KEYS = frozenset(
    {
        "birth_date",
        "birth_name",
        "birthday",
        "government_name",
        "identity",
        "legal_name",
        "previous_band",
        "previous_project",
        "real_name",
        "unmasked_photo",
    }
)
_ALLOWED_CREDIT_LOOKUP = {name.casefold(): name for name in ALLOWED_CREDITS}


def contains_doxxing(text: str) -> bool:
    """Return True for explicit identity-leak language, never inferred identity."""
    return bool(_DOXXING_RE.search(text) or _RISKY_MEDIA_RE.search(text))


def sanitize_text(value: str | None) -> str:
    """Redact complete paragraphs containing prohibited identity material."""
    if not value:
        return ""
    pieces = _PARAGRAPH_SPLIT.split(value.replace("\x00", ""))
    for index in range(0, len(pieces), 2):
        paragraph = pieces[index]
        if contains_doxxing(paragraph):
            pieces[index] = REDACTION
    sanitized = "".join(pieces)
    repeated = re.compile(
        rf"{re.escape(REDACTION)}(?:\r?\n[ \t]*\r?\n{re.escape(REDACTION)})+",
        re.IGNORECASE,
    )
    return repeated.sub(REDACTION, sanitized).strip()


def sanitize_credit_name(name: str | None) -> str:
    """Keep explicitly approved credits and redact every unknown identity."""
    if not name:
        return REDACTION
    canonical = _ALLOWED_CREDIT_LOOKUP.get(name.strip().casefold())
    return canonical or REDACTION


def sanitize_credit_names(names: Sequence[str]) -> list[str]:
    """Sanitize and de-duplicate credit names while preserving order."""
    result: list[str] = []
    for name in names:
        sanitized = sanitize_credit_name(name)
        if sanitized not in result:
            result.append(sanitized)
    return result


def sanitize_payload(value: Any, *, key: str | None = None) -> Any:
    """Recursively sanitize API/scraper data before it crosses persistence."""
    normalized_key = key.casefold() if key else ""
    if normalized_key in _SENSITIVE_KEYS:
        return REDACTION
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_payload(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(sanitize_payload(item) for item in value)
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, set):
        return {sanitize_payload(item) for item in value}
    return value


def sanitize_url(url: str, context: str = "") -> str:
    """Suppress media URLs whose surrounding text identifies them as leaks."""
    if contains_doxxing(f"{context}\n{url}"):
        return REDACTION
    return url
