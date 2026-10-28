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
reddrix install
Copy-Item .env.example .env
```

Set `GENIUS_ACCESS_TOKEN` in `.env`. Do not commit `.env`.

The official Genius API supplies catalog metadata, song details, and annotation referents. It does **not** supply lyrics; LyricsGenius reads lyrics from public Genius song pages. Full-text ingestion is intended for authorized private use and generated artifacts are gitignored.

## Commands

The overnight command is a single process:

```powershell
python main.py run
```

It writes the five primary corpora to `data/genius.json`, `data/reddit.json`, `data/wiki.json`, `data/press.json`, and `data/musicology.json` as each source finishes. If Genius returns no songs, lyrics, or annotations, or Reddit returns no threads, the process stops before Google. After those gates pass, it paginates Google for lyrics, meanings, and lore until the SERP is exhausted or Google blocks the client. Those pages are stored separately in `data/google.json`. Then it builds `SLEEP_TOKEN_ULTIMATE_CODEX.md`.

```powershell
python main.py extract genius
python main.py extract all --resume
python main.py build
python main.py run --resume
python main.py --output .\private\codex.md run
```

Exit status is `0` for complete coverage, `1` for partial/skipped coverage, and `2` when an extractor failed. Successful source checkpoints remain usable after another source fails.

Sanitized checkpoints are written atomically. `--resume` reuses existing primary checkpoints and completed Google queries. Delete a checkpoint to force only that source to refresh. Paragraph extraction now keeps inline markup (`<strong>`, links), so truncated `wiki.json` / `press.json` / `musicology.json` files should be deleted before `--resume`.

## Current source constraints

- Primary wiki/press/musicology crawls stay inside the domains and seed URLs in `config/settings.py`. Wiki/ARG seeds (including [loreofsleeptoken.com](https://loreofsleeptoken.com/) and the English Wikipedia article) are expanded same-host first, then to other allowlisted hosts only. `CODEX_CRAWL_MAX_PAGES` (40) and `CODEX_CRAWL_MAX_DEPTH` (2) cap that discovery.
- After the primary corpora succeed, `run` follows public Google results for lyrics, meanings, and lore. YouTube and major social hosts are skipped. Local/private addresses are rejected. The crawl stops at the first traffic/CAPTCHA block; it does not rotate identity or bypass Google.
- Reddit ingestion uses [Reddrix](https://pypi.org/project/reddrix/) (no API key) with `stealth=False`: Camoufox only harvests cookies, then closes. Subreddit and keyword searches run one at a time, with one in-flight request (`CODEX_REDDIT_INFLIGHT`, default 1) and 15 posts per job (`CODEX_REDDIT_POSTS_PER_JOB`). Each finished job is written to `data/reddit.json`, so a crash keeps the chunks already saved. `--resume` continues a checkpoint whose reason starts with `reddit chunk`. Zero discovered threads is a hard failure. After `pip install`, run `reddrix install` once.
- `DynamicFetcher` is the current Scrapling browser fetcher; it replaces the older `PlayWrightFetcher` naming.
- Community theories remain labeled as community material. Verified Genius annotations are not treated as band-authored canon.

## Offline verification

The default suite uses mocks/fixtures and makes no live requests:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' ./scripts/ai-test-runner.sh python -m unittest discover -v
& 'C:\Program Files\Git\bin\bash.exe' ./scripts/ai-test-runner.sh python -m compileall -q config core models scrapers aggregator main.py
```
