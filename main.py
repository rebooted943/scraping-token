"""CLI orchestrator for extraction, sanitized checkpoints, and Codex builds."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from aggregator.codex_builder import CodexBuilder
from config.settings import Settings, get_settings
from core.fetcher import ResilientFetcher
from core.sanitizer import sanitize_payload
from models.schemas import (
    CoverageStatus,
    ExtractionCoverage,
    InterviewQuote,
    LoreThread,
    MusicologyInsight,
    Song,
    VisualSymbol,
)
from scrapers.genius_api_extractor import GeniusAPIExtractor
from scrapers.musicology_scraper import MusicologyExtractor
from scrapers.press_archive_scraper import PressArchiveExtractor
from scrapers.reddit_stealth import RedditStealthExtractor
from scrapers.wiki_and_arg_scraper import WikiAndArgExtractor

console = Console()
SOURCE_NAMES = ("genius", "reddit", "wiki", "press", "musicology")
MODEL_BY_SOURCE = {
    "genius": Song,
    "reddit": LoreThread,
    "wiki": VisualSymbol,
    "press": InterviewQuote,
    "musicology": MusicologyInsight,
}


def _checkpoint_path(settings: Settings, source: str) -> Path:
    return settings.data_dir / f"{source}.json"


def _save_checkpoint(
    settings: Settings,
    source: str,
    records: list[Any],
    coverage: ExtractionCoverage,
) -> None:
    destination = _checkpoint_path(settings, source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_payload(
        {
            "source": source,
            "coverage": coverage.model_dump(mode="json"),
            "records": [record.model_dump(mode="json") for record in records],
        }
    )
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)


def _load_checkpoint(
    settings: Settings,
    source: str,
) -> tuple[list[Any], ExtractionCoverage] | None:
    path = _checkpoint_path(settings, source)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = MODEL_BY_SOURCE[source]
    records = [model.model_validate(item, strict=False) for item in payload["records"]]
    coverage = ExtractionCoverage.model_validate(payload["coverage"], strict=False)
    return records, coverage


async def _extract_source(
    source: str,
    fetcher: ResilientFetcher,
    settings: Settings,
) -> tuple[list[Any], ExtractionCoverage]:
    extractor = {
        "genius": GeniusAPIExtractor,
        "reddit": RedditStealthExtractor,
        "wiki": WikiAndArgExtractor,
        "press": PressArchiveExtractor,
        "musicology": MusicologyExtractor,
    }[source](fetcher)
    try:
        return await extractor.extract()
    except Exception:
        return [], ExtractionCoverage(
            source=source,
            status=CoverageStatus.FAILED,
            attempted=1,
            succeeded=0,
            reason="extractor failed; raw exception suppressed to protect source content",
        )


async def extract_sources(
    settings: Settings,
    sources: tuple[str, ...],
    *,
    resume: bool,
) -> dict[str, tuple[list[Any], ExtractionCoverage]]:
    results: dict[str, tuple[list[Any], ExtractionCoverage]] = {}
    pending: list[str] = []
    for source in sources:
        checkpoint = _load_checkpoint(settings, source) if resume else None
        if checkpoint:
            results[source] = checkpoint
        else:
            pending.append(source)

    async with ResilientFetcher(settings) as fetcher:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=console,
        ) as progress:
            task_by_source = {
                source: asyncio.create_task(_extract_source(source, fetcher, settings))
                for source in pending
            }
            progress_ids = {
                source: progress.add_task(f"Extracting {source}", total=None)
                for source in pending
            }
            for source, task in task_by_source.items():
                records, coverage = await task
                _save_checkpoint(settings, source, records, coverage)
                results[source] = (records, coverage)
                progress.update(
                    progress_ids[source],
                    description=f"{source}: {coverage.status.value}",
                    completed=1,
                )
    return results


def build_from_checkpoints(settings: Settings, output: Path | None = None) -> tuple[Path, int]:
    loaded: dict[str, tuple[list[Any], ExtractionCoverage]] = {}
    for source in SOURCE_NAMES:
        checkpoint = _load_checkpoint(settings, source)
        if checkpoint:
            loaded[source] = checkpoint
        else:
            loaded[source] = (
                [],
                ExtractionCoverage(
                    source=source,
                    status=CoverageStatus.SKIPPED,
                    attempted=0,
                    succeeded=0,
                    reason="no sanitized checkpoint found",
                ),
            )
    dataset = CodexBuilder(settings).build_dataset(
        songs=loaded["genius"][0],
        lore_threads=loaded["reddit"][0],
        visual_symbols=loaded["wiki"][0],
        interview_quotes=loaded["press"][0],
        musicology=loaded["musicology"][0],
        coverage=[value[1] for value in loaded.values()],
    )
    destination = CodexBuilder(settings).write(dataset, output)
    statuses = [coverage.status for _, coverage in loaded.values()]
    exit_code = 2 if CoverageStatus.FAILED in statuses else int(
        CoverageStatus.PARTIAL in statuses or CoverageStatus.SKIPPED in statuses
    )
    return destination, exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a sanitized, provenance-rich Sleep Token lore Codex."
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        help="Override bounded concurrent requests.",
    )
    parser.add_argument("--output", type=Path, help="Override Codex Markdown path.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser("extract", help="Write sanitized source checkpoints.")
    extract.add_argument("source", choices=(*SOURCE_NAMES, "all"), nargs="?", default="all")
    extract.add_argument("--resume", action="store_true", help="Reuse existing checkpoints.")
    build = subparsers.add_parser("build", help="Build from sanitized checkpoints.")
    build.set_defaults(source=None, resume=False)
    run = subparsers.add_parser("run", help="Extract all sources and build the Codex.")
    run.add_argument("--resume", action="store_true", help="Reuse existing checkpoints.")
    run.set_defaults(source="all")
    return parser


async def _async_main(args: argparse.Namespace, settings: Settings) -> int:
    if args.command in {"extract", "run"}:
        sources = SOURCE_NAMES if args.source == "all" else (args.source,)
        results = await extract_sources(settings, sources, resume=args.resume)
        statuses = [coverage.status for _, coverage in results.values()]
        if args.command == "extract":
            return 2 if CoverageStatus.FAILED in statuses else int(
                CoverageStatus.PARTIAL in statuses
            )
    destination, exit_code = build_from_checkpoints(settings, args.output)
    console.print(f"Codex written to [bold]{destination}[/bold]")
    return exit_code


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    if args.max_concurrency is not None:
        settings = replace(settings, max_concurrency=max(1, args.max_concurrency))
    return asyncio.run(_async_main(args, settings))


if __name__ == "__main__":
    raise SystemExit(main())
