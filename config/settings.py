"""Central, environment-aware configuration with a closed source allowlist."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
GENIUS_API_BASE = "https://api.genius.com"
GENIUS_ARTIST_NAME = "Sleep Token"
GENIUS_PAGE_SIZE = 50

LORE_KEYWORDS = (
    "lore",
    "theory",
    "meaning",
    "alchemical",
    "runes",
    "eden",
    "atlantic",
    "sleep",
    "trilogy",
    "chemistry",
    "biology",
    "teeth",
    "callbacks",
)

MOTIF_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chemistry_biology_physics": (
        "acid",
        "alkaline",
        "aqua regia",
        "biology",
        "chemistry",
        "molecule",
        "osmosis",
        "oxytocin",
        "physics",
        "surface tension",
        "synapse",
        "telomere",
    ),
    "visceral_anatomical": (
        "bite",
        "blood",
        "bone",
        "flesh",
        "jaw",
        "limb",
        "teeth",
        "vore",
    ),
    "elemental": (
        "brimstone",
        "daylight",
        "drown",
        "eden",
        "fire",
        "granite",
        "night",
        "ocean",
        "water",
    ),
}

RELEASE_ERAS: dict[str, str] = {
    "one": "The Primordial Era",
    "two": "The Primordial Era",
    "sundowning": "Era I: Sundowning",
    "this place will become your tomb": "Era II: This Place Will Become Your Tomb",
    "take me back to eden": "Era III: Take Me Back to Eden",
}

CANONICAL_RELEASE_ORDER = (
    "One",
    "Two",
    "Jaws",
    "The Way That You Were",
    "Sundowning",
    "This Place Will Become Your Tomb",
    "Is It Really You?",
    "Take Me Back to Eden",
)

ALLOWED_CREDITS = frozenset(
    {
        "Vessel",
        "II",
        "Sleep Token",
        "George Lever",
        "Carl Bown",
    }
)

DOXXING_PATTERNS = (
    r"\b(?:real|legal|birth|government)\s+name\b",
    r"\b(?:born|birth(?:day|date))\s+(?:on|in|is)\b",
    r"\b(?:unmasked|without (?:a|the) mask|face reveal)\b",
    r"\b(?:formerly|previously)\s+(?:played|performed|known)\b",
    r"\b(?:former|previous)\s+(?:band|project|stage name)\b",
    r"\b(?:identity|identities)\s+(?:is|are|revealed|confirmed|leaked)\b",
    r"\b(?:doxx|doxxed|doxxing|tabloid leak)\b",
    r"\b(?:Vessel|II|III|IV|Espera)\s+(?:is|was|aka|a\.k\.a\.|born as)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+",
    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*\((?:Vessel|II|III|IV|Espera)\)",
)

RISKY_MEDIA_PATTERNS = (
    r"\bunmasked\b",
    r"\bface[- ]?reveal\b",
    r"\bleaked?\s+(?:photo|image|picture)\b",
)

ALLOWED_SOURCE_DOMAINS = frozenset(
    {
        "api.genius.com",
        "genius.com",
        "www.genius.com",
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "sleep-token-collective.fandom.com",
        "www.omniglot.com",
        "boolintunes.com",
        "www.loudersound.com",
        "www.kerrang.com",
        "web.archive.org",
    }
)

WIKI_ARG_SEEDS = (
    "https://sleep-token-collective.fandom.com/wiki/Fanlore_%26_Theories:_General",
    "https://www.omniglot.com/conscripts/sleeptokenalphabet.htm",
    "https://boolintunes.com/featured/the-lore-of-sleep-token/",
    "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/3",
)

PRESS_SEEDS = (
    "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
    "https://www.loudersound.com/features/sleep-token-goofy-gimmick-or-serious-art",
    "https://www.kerrang.com/sleep-token-formation-interview-vocalist-frontman-vessel-2018-drummer-ii-bassist-iii-guitarist-iv-debut-album-sundowning",
    "https://www.kerrang.com/sleep-token-vessel-cover-story-take-me-back-to-eden-sundowning-servant-rituals-corey-taylor-sold-out-wembley-arena",
)

MUSICOLOGY_SEEDS = (
    "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
    "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/2",
    "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/3",
    "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/4",
    "https://boolintunes.com/featured/the-lore-of-sleep-token/",
)

REDDIT_FEEDS = (
    "https://www.reddit.com/r/SleepToken/top/.rss?t=all",
    "https://www.reddit.com/r/SleepToken/search.rss?q=lore%20OR%20theory%20OR%20runes%20OR%20trilogy&restrict_sr=1&sort=top&t=all",
)


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    genius_access_token: str
    user_agent: str
    data_dir: Path
    output_path: Path
    max_concurrency: int
    request_timeout: float
    include_full_lyrics: bool
    max_retries: int = 4
    backoff_base: float = 1.0
    reddit_min_interval: float = 65.0
    cross_reference_threshold: float = 3.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.getenv("CODEX_DATA_DIR", "data"))
    output = Path(os.getenv("CODEX_OUTPUT", "SLEEP_TOKEN_ULTIMATE_CODEX.md"))
    return Settings(
        genius_access_token=os.getenv("GENIUS_ACCESS_TOKEN", "").strip(),
        user_agent=os.getenv(
            "CODEX_USER_AGENT",
            "sleep-token-codex/1.0 (private lore research)",
        ).strip(),
        data_dir=data_dir if data_dir.is_absolute() else ROOT_DIR / data_dir,
        output_path=output if output.is_absolute() else ROOT_DIR / output,
        max_concurrency=max(1, int(os.getenv("CODEX_MAX_CONCURRENCY", "4"))),
        request_timeout=max(1.0, float(os.getenv("CODEX_REQUEST_TIMEOUT", "30"))),
        include_full_lyrics=_as_bool("CODEX_INCLUDE_FULL_LYRICS", True),
    )
