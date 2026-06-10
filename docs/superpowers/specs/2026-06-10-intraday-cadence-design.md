# Intraday Cadence + Same-Day Merge — Design Spec (P2)

**Date:** 2026-06-10
**Status:** Approved
**Builds on:** `2026-06-10-deep-archive-and-search-v2-design.md` (P1)
**Series:** P2 of 4 (P3 mobile polish, P4 public hardening pending)

## Problem

The pipeline runs once daily (12:00 UTC). HN/news/blog items land hours late. Rerunning `pipeline.run` for the same date **overwrites** that date's digest: items fetched by an earlier run that have since left the sources' windows would vanish, and their summaries with them.

## Changes

### 1. Cron: every 3 hours

`.github/workflows/daily-digest.yml` schedule: `0 12 * * *` → `0 */3 * * *` (8 runs/day UTC). Everything else in the workflow unchanged — the shared `daily-digest` concurrency group already serializes against the backfill workflow; commit-if-changed step already no-ops on empty runs.

### 2. Same-day merge in `pipeline/run.py`

New pure helpers (in `pipeline/run.py`, pytest-covered):

```python
def load_existing_digest(date: str, content_dir: Path) -> dict | None
    # json.loads content/digests/{date}.json, None if absent/invalid

def merge_run_items(existing: dict | None, fetched: list[Item]) -> tuple[list[Item], dict[str, dict]]
    # returns (pool, carried_summaries)
    # pool: existing digest items (Item.from_dict — tolerates extra keys) first,
    #       newly fetched appended, dedupe by source:id with existing winning
    # carried_summaries: {key: {summary, repro_difficulty}} for every existing
    #       item dict that has a non-empty "summary"
```

`main()` write path becomes:

1. `fetched = collect()`
2. `existing = load_existing_digest(args.date, DEFAULT_CONTENT_DIR)`; `items, carried = merge_run_items(existing, fetched)`
3. ML steps run over the merged `items` (embed cache is keyed by `source:id` → incremental; clustering over ~100-200 items is cheap; `label_topics` = one Claude call per run; ranking cheap).
4. `summaries = {**carried, **summarize_items(selected)}` — this run's results layer on top; carried entries survive even when their item isn't selected this run. (`summarize_items` already returns cache hits for free.)
5. `write_digest(...)` as today, with merged items + layered summaries.

`--dry-run` unchanged (prints fetched only, no merge needed).

### 3. Synthesis once per week

Sunday now has 8 runs. Guard in `main()` before the synthesis step: skip when `content/synthesis/{iso_week(args.date)}.mdx` already exists (reuse `pipeline/synthesize.iso_week`). `--synthesize` flag forces regardless (explicit manual override).

## Non-changes

- Frontend untouched (ISR revalidate 3600 picks up new digests).
- Backfill, sources, Vercel config untouched.
- More commits/day — all real fetches at real timestamps; honest-commit rule intact.

## Costs

8×/day: Actions ~5 min/run; Claude = 1 label call/run + summaries for new items only (cache-deduped); embeddings incremental via cache. Bounded and acceptable (user-approved 3h cadence).

## Error handling

Existing fault-tolerance preserved: bad existing digest JSON → treated as None (fresh build, same as today); ML failures still write the digest with whatever succeeded.

## Testing

- **pytest** (`tests/test_run_merge.py`): `merge_run_items` — existing wins on duplicate key, new appended, summary carry-forward only for non-empty summaries, None existing → (fetched, {}); `load_existing_digest` absent/corrupt → None; synthesis guard logic (pure check, tmp_path).
- Existing 63 stay green. Live: dispatch the workflow once after merge lands, verify same-day digest grows without losing summaries.

## Out of scope

Per-run partial clustering, summary re-selection strategies, frontend freshness indicators.
