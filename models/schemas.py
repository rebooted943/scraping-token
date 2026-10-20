"""Strict normalized schemas shared by every extractor and the Codex builder."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceKind(StrEnum):
    CANONICAL = "canonical"
    EDITORIAL = "editorial"
    COMMUNITY = "community"


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class CodexModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class SourceReference(CodexModel):
    url: str
    title: str
    kind: SourceKind
    retrieved_at: datetime = Field(default_factory=utc_now)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("source URL must use HTTP(S)")
        return value


class ExtractionCoverage(CodexModel):
    source: str
    status: CoverageStatus
    attempted: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.succeeded > self.attempted:
            raise ValueError("succeeded cannot exceed attempted")
        if self.status != CoverageStatus.COMPLETE and not self.reason:
            raise ValueError("non-complete coverage requires a reason")
        return self


class Credit(CodexModel):
    name: str
    role: str


class LyricAnnotation(CodexModel):
    genius_id: int
    fragment: str
    body: str
    verified: bool = False
    votes_total: int | None = None
    source: SourceReference

    @model_validator(mode="after")
    def require_content(self) -> Self:
        if not self.fragment or not self.body:
            raise ValueError("annotation fragment and body are required")
        return self


class Song(CodexModel):
    genius_id: int
    title: str
    full_title: str
    url: str
    release_name: str = "Standalone Singles"
    release_date: date | None = None
    track_number: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=0)
    producers: list[Credit] = Field(default_factory=list)
    writers: list[Credit] = Field(default_factory=list)
    associated_symbols: list[str] = Field(default_factory=list)
    description: str = ""
    lyrics: str = ""
    annotations: list[LyricAnnotation] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    extraction_errors: list[str] = Field(default_factory=list)


class Release(CodexModel):
    name: str
    year: int | None = Field(default=None, ge=2016, le=2100)
    era: str
    songs: list[Song] = Field(default_factory=list)


class LoreComment(CodexModel):
    author: str = "[anonymous]"
    body: str
    score: int = 0
    permalink: str


class LoreThread(CodexModel):
    title: str
    body: str = ""
    score: int = 0
    keywords: list[str] = Field(default_factory=list)
    comments: list[LoreComment] = Field(default_factory=list)
    matched_song_ids: list[int] = Field(default_factory=list)
    source: SourceReference


class VisualSymbol(CodexModel):
    category: str
    name: str
    description: str
    era: str | None = None
    related_songs: list[str] = Field(default_factory=list)
    source: SourceReference


class InterviewQuote(CodexModel):
    speaker: str
    quote: str
    context: str = ""
    publication: str
    published_at: date | None = None
    source: SourceReference


class MusicologyInsight(CodexModel):
    topic: str
    summary: str
    related_songs: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list)
    source: SourceReference


class Era(CodexModel):
    name: str
    order: int = Field(ge=0)
    summary: str = ""
    releases: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)


class CodexDataset(CodexModel):
    generated_at: datetime = Field(default_factory=utc_now)
    artist: str = "Sleep Token"
    eras: list[Era] = Field(default_factory=list)
    releases: list[Release] = Field(default_factory=list)
    lore_threads: list[LoreThread] = Field(default_factory=list)
    visual_symbols: list[VisualSymbol] = Field(default_factory=list)
    interview_quotes: list[InterviewQuote] = Field(default_factory=list)
    musicology: list[MusicologyInsight] = Field(default_factory=list)
    coverage: list[ExtractionCoverage] = Field(default_factory=list)
