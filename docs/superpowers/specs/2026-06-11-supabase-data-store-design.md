# Supabase Data Store — Design Spec

**Date:** 2026-06-11
**Status:** Approved
**Decisions (user):** DB-only (no more committed data files; daily data commits to the contribution graph end — accepted with eyes open) · JSONB mirror schema.

## Problem

All site data lives in committed files (`content/digests/*.json`, `content/index.json`, `content/synthesis/*.mdx`) plus committed caches (`data/summaries/cache.json`, `data/embeddings/cache.json`). Move it to Supabase: the DB becomes the single source of truth for pipeline writes and frontend reads.

## Schema (Supabase migration; RLS enabled, NO policies — service-role only, same posture as `feedback`)

```sql
create table digests (
  date date primary key,
  generated_at timestamptz not null,
  payload jsonb not null            -- the exact digest doc: {date, generated_at, items, topics}
);

create table syntheses (
  week text primary key,            -- "2026-24"
  title text not null,
  date date not null,
  body text not null                -- markdown
);

create table kv_cache (
  scope text not null,              -- 'summaries' | 'embeddings'
  key text not null,                -- item key "source:id"
  value jsonb not null,
  primary key (scope, key)
);
alter table digests enable row level security;
alter table syntheses enable row level security;
alter table kv_cache enable row level security;
```

Caches matter: without committed `data/` files, every 3-hour run would re-pay Claude for every summary and re-embed everything. `kv_cache` rows are per-item (fetch only the keys you need).

## Pipeline (`pipeline/store.py`, PostgREST via httpx — same pattern as `rank.fetch_feedback`)

```python
class StoreError(RuntimeError): ...
def _env() -> tuple[str, str]            # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY; raises StoreError if missing
def fetch_digest(date: str) -> dict | None
def upsert_digest(date: str, payload: dict) -> None        # on_conflict=date, Prefer: resolution=merge-duplicates
def fetch_index() -> list[dict]          # [{date, item_count, has_synthesis}] derived: digests dates + jsonb_array_length + syntheses weeks
def upsert_synthesis(week: str, title: str, date: str, body: str) -> None
def synthesis_exists(week: str) -> bool
def cache_get(scope: str, keys: list[str]) -> dict[str, dict]   # chunked in= queries
def cache_put(scope: str, entries: dict[str, dict]) -> None     # chunked upserts
```

**Loud failure:** storage is the critical path now. `_env()` raises; `run.py`/`backfill.py` let that propagate (no silent skip). Network errors on writes: retry ×3 then raise.

### Integration swaps

- `run.py`: `load_existing_digest` → `store.fetch_digest(args.date)`; `write_digest(...)` call → build the digest dict via existing `digest.build_digest` then `store.upsert_digest`. Synthesis guard `week_file.exists()` → `store.synthesis_exists(iso_week(...))`; `write_synthesis` → `store.upsert_synthesis`.
- `summarize.py`: file cache (`_load_cache`/write_text) → `store.cache_get("summaries", keys)` / `cache_put`. Injectable for tests (cache fns as params with file-free defaults).
- `embed.py`: same swap with scope `"embeddings"`.
- `synthesize.py`: `recent_summaries` reads last-7 digests from store instead of files; `write_synthesis` replaced by store upsert (keep a pure `render` if needed for tests).
- `backfill.py`: per-day `fetch_digest` → merge (existing helpers unchanged) → `upsert_digest`; index step disappears (derived).
- `digest.py`: `build_digest` stays (pure); `write_digest`/`_update_index` deleted once nothing references them.

## Frontend

- `src/lib/content.ts`: rewrite loaders over Supabase (`getServiceClient`): `getIndex` ← `store`-equivalent select (`date, jsonb_array_length(payload->'items')`, syntheses weeks for has_synthesis), `getDigest` ← payload select, `getLatestDigest`/`getRecentDigests`/`getDigestsBefore`/`getAllDigests` keep signatures (callers untouched); `getAllDigests` in-memory cache stays. Add `import "server-only"`. Null-safe: client missing or query error → same empty fallbacks as today (frontend degrades to empty board rather than crashing).
- `src/lib/synthesis.ts`: `getSyntheses`/`getSynthesis` ← `syntheses` table.
- No page/component changes (loader signatures preserved).

## Workflow & repo cleanup

- `daily-digest.yml` + `backfill.yml`: SUPABASE_URL/SERVICE_ROLE_KEY already in the env blocks; delete the commit steps entirely (nothing to commit). The HF model cache step stays — that's an Actions build cache, unrelated to data.
- Delete `content/` and `data/` from the repo (git rm) after migration verified.
- `.env.example`: SUPABASE vars marked required.

## Migration (one-off, run locally — .env has creds)

`pipeline/migrate_to_db.py`: read every `content/digests/*.json` → `upsert_digest`; every `content/synthesis/*.mdx` (reuse frontmatter parse) → `upsert_synthesis`; `data/summaries/cache.json` → `cache_put("summaries", ...)`; `data/embeddings/cache.json` → `cache_put("embeddings", ...)` (chunked). Prints counts; idempotent (upserts).

## Rollout order (load-bearing)

1. Apply schema (Supabase MCP migration).
2. Implement + tests green locally.
3. Run migration locally; verify row counts (161 digests, 1 synthesis, cache rows).
4. **USER GATE: confirm `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` added to GitHub Actions secrets AND Vercel env.**
5. Push (single deploy flips reads+writes). Verify prod board + a manual workflow_dispatch run.

## Error handling

Pipeline: raise on store failures (run fails visibly in Actions). Frontend: null-safe empty fallbacks (matches today's behavior when files were missing). Migration: per-file try/log/continue, exit non-zero if any failed.

## Testing

- **pytest**: store request-shaping pure helpers (index derivation from rows, chunking), run/backfill integration via injectable store fns (monkeypatch store.fetch_digest/upsert_digest — no network in tests), summarize/embed cache swap with injected cache fns. Existing 67 adapted where they touched files (test_digest write paths → build_digest only; test_run_merge load_existing_digest test replaced by store-injected variant).
- **vitest**: unchanged (26→33 already; loaders aren't unit-tested, same as before).
- **Live**: migration counts; local `python -m pipeline.run` writes a digest row; site reads it; prod verification post-deploy.

## Out of scope

Normalized item tables, anon-key public reads, pgvector embeddings, realtime, removing the Supabase `read_state` table.
