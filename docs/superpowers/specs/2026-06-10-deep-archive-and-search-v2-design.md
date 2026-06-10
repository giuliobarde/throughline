# Deep Archive + Search v2 — Design Spec (P1)

**Date:** 2026-06-10
**Status:** Approved
**Builds on:** `2026-06-09-social-board-design.md`, `2026-06-10-search-and-blog-source-design.md`
**Series:** P1 of 4 (P2 intraday cadence, P3 mobile polish, P4 public hardening — separate specs)

## Problem

The board only holds the last ~7 daily digests. Past events ("fable", older releases) are unfindable. Search relevance is literal substring only — "claude" misses Anthropic items, domains aren't queryable. Search requires a full page load.

## Summary

1. **Historical backfill** from 2026-01-01: a one-off pipeline CLI (run via GitHub Action) that fetches arXiv/HN/GitHub/blog history, buckets items into per-day digest files, and summarizes only Claude-selected weekly milestones (1–5/week).
2. **Search v2**: search the entire archive via a cached all-digests loader; alias-aware + domain-aware scoring.
3. **Dynamic search**: debounced nav dropdown backed by `GET /api/search`.

## Part 1 — Backfill pipeline

### CLI

`python -m pipeline.backfill --from 2026-01-01 --to YYYY-MM-DD [--dry-run] [--no-summaries]`
New file `pipeline/backfill.py`. Iterates ISO-week chunks from→to.

### Historical fetchers (per week chunk, each fault-tolerant try/skip)

- **arXiv** (`pipeline/sources/arxiv.py` gains `fetch_range(start, end)`): existing query + `submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]`, paginated, 3s sleep between calls (API politeness).
- **HN** (`hackernews.py` gains `fetch_range(start, end)`): Algolia `search_by_date` with `numericFilters=created_at_i>=X,created_at_i<Y` + `points>=100`, `hitsPerPage=1000`, paginate; existing AI/ML keyword title filter.
- **GitHub** (`github.py` gains `fetch_range(start, end)`): repo search `machine learning created:START..END`, sort stars, top 10 per week; optional `GITHUB_TOKEN`.
- **Blogs**: `BlogSource`-style RSS fetch once (not per week), `filter_window` bypassed — keep everything with `published_at >= from` (feeds carry whatever history they carry; best effort). Tavily: **skipped** — no reliable historical mode.

### Bucketing & merge

- Items grouped by `published_at[:10]` (UTC date). Items outside [from, to] dropped.
- For each date: load existing `content/digests/<date>.json` if present; **merge** — keep all existing items/topics/summaries, append only new keys (`source:id`); never clobber. New backfill-only days get `topics: []`, no `for_you_score`.
- `index.json` rebuilt: all digest files, sorted date desc, with `item_count`/`has_synthesis`.

### Milestone summaries (1–5/week)

- Per week: build a compact listing of that week's collected items — title, source, signal (HN points / GitHub stars parsed where available, vendor name for blogs).
- One Claude call (existing `claude-haiku-4-5` via env `ANTHROPIC_MODEL`, json-schema output `{item_ids: string[]}` max 5): "select only landmark events — major model announcements, breakout repos, landmark papers; fewer is better, zero is fine."
- Selected items summarized through the existing `summarize_items` (cache reused: `data/summaries/cache.json`), written into their day's digest.
- Injectable `llm` callable for tests; no `ANTHROPIC_API_KEY` or `--no-summaries` → selection skipped, backfill still completes.

### Execution

- New workflow `.github/workflows/backfill.yml`: `workflow_dispatch` with `from`/`to` inputs; same env/secrets/commit pattern as daily-digest.yml; commits authored `Giulio <giuliobarde@users.noreply.github.com>` (honest-commit rule; the data fetch genuinely happens at commit time).
- Run from CI, not locally — arXiv rate-limits the local dev IP.
- Estimated repo growth: ~160 daily JSONs, single-digit MB total. Acceptable.

### Side effect (intended)

`index.json` grows past 7 entries → home feed's `initialBefore` gate opens → infinite scroll pages back through the entire archive with zero frontend changes.

## Part 2 — Search v2 (web)

### Archive-wide pool

- `src/lib/content.ts` gains `getAllDigests(): Promise<Digest[]>` — reads every index entry, **module-level in-memory cache** (`let cache: {key: string, digests: Digest[]} | null`, keyed by `index[0]?.date + index.length`; stale key → reload). ~160 small files ≈ 100ms cold, ~0 warm.
- `/search` page and the new search API use `getAllDigests()` (merged + deduped via existing `mergeDigests`). Home board stays on `getRecentDigests(7)`.
- Topics for matching remain the latest digest's topics (backfilled days have none).

### Relevance v2 (`src/lib/search.ts`)

- **Alias map** (module const): bidirectional groups — `[claude, anthropic]`, `[gpt, openai, chatgpt]`, `[gemini, deepmind]`, `[llama, meta]`, `[huggingface, hf]`. Each query term expands to its full group before scoring. (Model names like "fable" need no alias — they become discoverable via titles/abstracts once the archive exists.)
- **New scored fields:** URL hostname (via `new URL` try/catch, www-stripped) and `authors` (publisher for blog items) — both ×3 (identity-strength signals).
- **Domain queries:** a term containing `.` is matched against hostname only (substring), ×3.
- Existing: title ×3, topic tag/label ×2, summary/abstract ×1, score-0 drop, recency tie-break, limit param. All preserved.

### `GET /api/search` (`src/app/api/search/route.ts`)

- `?q=` (trimmed, max 100 chars — longer → 400), returns `{items: SearchHit[]}` top 8 where `SearchHit = {key, title, url, source, date}` (lean payload, no abstracts).
- Uses `getAllDigests()` + `searchItems`. Empty q → `{items: []}`.

## Part 3 — Dynamic search (nav)

- New client component `src/components/SearchBox.tsx` replaces the nav form's input: still an actual `<form action="/search">` (no-JS fallback + Enter submits), plus debounced (250ms) fetch to `/api/search` on input ≥2 chars.
- Dropdown: absolute-positioned panel under the input, top 8 hits — title (truncated), `SourceBadge`-style label, date; click → item URL (new tab); footer row "all results for 'q' →" links `/search?q=`.
- Esc or outside-click closes; results cleared on empty input. `aria-expanded`/`role="listbox"` basics; arrow-key navigation **out of scope** (P3 may revisit).
- In-flight fetch aborted on new keystroke (`AbortController`).

## Error handling

- Backfill: per-week, per-source try/except log+skip; Claude selection failure → week stays unsummarized; merge never deletes existing data; `--dry-run` prints counts only.
- `getAllDigests` cache: any read error → fall back to fresh read; missing files filtered (existing pattern).
- `/api/search`: q over 100 chars → 400; downstream errors → 500 with `{error}`; SearchBox treats non-200/abort as empty (silent).

## Testing

- **pytest** (`tests/test_backfill.py`): bucket-by-date, [from,to] bounds, merge-no-clobber (existing digest keeps items/summaries), week chunk iteration, milestone selection with injectable llm (selects ≤5, bad ids ignored, no-key → {}), index rebuild sorted.
- **vitest** (extend `tests/web/search.test.ts`): alias expansion (claude→anthropic items via authors/hostname), domain query (`anthropic.com` matches hostname), hostname ×3 ordering, existing tests stay green.
- **Live:** Action dry-run first (`--dry-run` log inspection), then real backfill run; spot-check `/search?q=fable`, `/search?q=claude`, `/search?q=openai.com`; infinite scroll reaches January.

## Out of scope (→ P2/P3/P4 or later)

Intraday cadence, mobile polish, rate limiting/headers/SEO, embeddings-based semantic search, arrow-key dropdown navigation, Tavily historical backfill, re-clustering backfilled days.
