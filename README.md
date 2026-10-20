# Sleep Token Codex Pipeline

Python 3.11+ pipeline that combines Genius metadata/referents, LyricsGenius page extraction, and an allowlisted Scrapling crawl to produce a local, provenance-rich `SLEEP_TOKEN_ULTIMATE_CODEX.md`.

## Privacy boundary

The pipeline is lore-only. Before any checkpoint or Markdown write, it:

- redacts paragraphs about legal identities, birth details, unmasked imagery, leaks, or previous projects;
- suppresses raw exception bodies;
- retains only approved credits (`Vessel`, `II`, `Sleep Token`, `George Lever`, `Carl Bown`);
- replaces every other writer/producer identity with `[REDACTED - LORE ONLY]`.

This is deliberately fail-closed. It does not attempt to infer whether an unknown credit belongs to Vessel or II.

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
scrapling install
Copy-Item .env.example .env
```

Set `GENIUS_ACCESS_TOKEN` in `.env`. Do not commit `.env`.

The official Genius API supplies catalog metadata, song details, and annotation referents. It does **not** supply lyrics; LyricsGenius reads lyrics from public Genius song pages. Full-text ingestion is intended for authorized private use and generated artifacts are gitignored.

## Commands

```powershell
python main.py extract genius
python main.py extract all --resume
python main.py build
python main.py run --resume
python main.py --output .\private\codex.md run
```

Exit status is `0` for complete coverage, `1` for partial/skipped coverage, and `2` when an extractor failed. Successful source checkpoints remain usable after another source fails.

Sanitized checkpoints are written atomically to `data/<source>.json`. `--resume` reuses them. Delete a checkpoint to force only that source to refresh.

## Current source constraints

- Crawling is restricted to the domains and seed URLs in `config/settings.py`.
- Reddit disabled unauthenticated `.json` access in 2026. The keyless extractor uses public RSS/HTML only, never disguises its identity, and always marks Reddit coverage partial because all-time ranking and 15 comments cannot be guaranteed.
- `DynamicFetcher` is the current Scrapling browser fetcher; it replaces the older `PlayWrightFetcher` naming.
- Community theories remain labeled as community material. Verified Genius annotations are not treated as band-authored canon.

## Offline verification

The default suite uses mocks/fixtures and makes no live requests:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' ./scripts/ai-test-runner.sh python -m unittest discover -v
& 'C:\Program Files\Git\bin\bash.exe' ./scripts/ai-test-runner.sh python -m compileall -q config core models scrapers aggregator main.py
```
