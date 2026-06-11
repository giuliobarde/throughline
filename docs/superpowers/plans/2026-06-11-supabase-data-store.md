# Supabase Data Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supabase becomes the single data store: pipeline writes digests/syntheses/caches to Postgres (JSONB mirror), frontend reads from it, committed `content/`+`data/` files and workflow commit steps go away.

**Architecture:** New `pipeline/store.py` (PostgREST over httpx, loud `StoreError` on missing env/failed writes, retry ×3) replaces every file write/read in the pipeline; `embed`/`summarize` caches become injectable `cache_get`/`cache_put` callables defaulting to store-backed; `synthesize` gains a pure `synthesis_record`. Frontend: only `getIndex`/`getDigest` semantics move to Supabase — but loaders are rewritten DB-native (single queries, no N+1) with unchanged signatures so no page/component changes. A `digest_index` view gives item counts without shipping payloads. One-off `migrate_to_db.py` loads the 161 existing digests + synthesis + caches.

**Tech Stack:** Supabase Postgres (JSONB) · PostgREST · httpx · @supabase/supabase-js · pytest/vitest.

**Spec:** `docs/superpowers/specs/2026-06-11-supabase-data-store-design.md`

**Commit rules (repo non-negotiable):** plain `git commit`, exact messages, NO Co-Authored-By/Claude trailer.

**Baselines:** pytest 67, vitest 33, lint 0, tsc clean. Local `.env` has `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (note: shell doesn't auto-load `.env`; pipeline commands that need it use `set -a; source .env; set +a;` prefix. Next.js dev/build loads `.env` automatically).

**Controller pre-step (already done before Task 1 dispatch): schema applied via Supabase MCP:**

```sql
create table digests (
  date date primary key,
  generated_at timestamptz not null,
  payload jsonb not null
);
create table syntheses (
  week text primary key,
  title text not null,
  date date not null,
  body text not null
);
create table kv_cache (
  scope text not null,
  key text not null,
  value jsonb not null,
  primary key (scope, key)
);
alter table digests enable row level security;
alter table syntheses enable row level security;
alter table kv_cache enable row level security;
create view digest_index with (security_invoker = off) as
  select date, jsonb_array_length(payload->'items') as item_count
  from digests;
```

---

### Task 1: `pipeline/store.py` (TDD on pure helpers)

**Files:**
- Create: `pipeline/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write failing tests** — `tests/test_store.py`:

```python
from __future__ import annotations

import pytest

from pipeline.store import StoreError, _chunks, _env, _in_param, derive_index


def test_in_param_quotes_keys():
    assert _in_param(["arxiv:1", "github:gh:o/r"]) == 'in.("arxiv:1","github:gh:o/r")'


def test_chunks_splits_evenly():
    assert list(_chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_derive_index_marks_synthesis_weeks():
    rows = [
        {"date": "2026-06-08", "item_count": 77},
        {"date": "2026-06-14", "item_count": 5},
    ]
    # 2026-06-14 is Sunday of ISO week 2026-24
    out = derive_index(rows, {"2026-24"})
    assert out == [
        {"date": "2026-06-14", "item_count": 5, "has_synthesis": True},
        {"date": "2026-06-08", "item_count": 77, "has_synthesis": False},
    ]


def test_env_raises_without_creds(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(StoreError):
        _env()
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_store.py -q` — FAIL (no module).

- [ ] **Step 3: Implement `pipeline/store.py`:**

```python
from __future__ import annotations

import logging
import os
import time
from typing import Iterator, Optional

import httpx

from pipeline.synthesize import iso_week

log = logging.getLogger("throughline")

RETRIES = 3
CHUNK = 200
TIMEOUT = 30.0


class StoreError(RuntimeError):
    """The data store is the critical path: failures must be loud."""


def _env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise StoreError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return url.rstrip("/"), key


def _headers(key: str, upsert: bool = False) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates"
    return h


def _request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[object] = None,
    upsert: bool = False,
) -> httpx.Response:
    url, key = _env()
    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        try:
            resp = httpx.request(
                method,
                f"{url}/rest/v1/{path}",
                params=params,
                json=json_body,
                headers=_headers(key, upsert=upsert),
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001 — uniform retry then loud fail
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    raise StoreError(f"supabase {method} {path} failed after {RETRIES} attempts") from last


def _in_param(keys: list[str]) -> str:
    quoted = ",".join(f'"{k}"' for k in keys)
    return f"in.({quoted})"


def _chunks(seq: list, size: int = CHUNK) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def derive_index(rows: list[dict], synthesis_weeks: set[str]) -> list[dict]:
    """digest_index rows + synthesis weeks -> index entries, newest first."""
    out = [
        {
            "date": r["date"],
            "item_count": r.get("item_count") or 0,
            "has_synthesis": iso_week(r["date"]) in synthesis_weeks,
        }
        for r in rows
    ]
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def fetch_digest(date: str) -> Optional[dict]:
    resp = _request("GET", "digests", params={"date": f"eq.{date}", "select": "payload"})
    rows = resp.json()
    return rows[0]["payload"] if rows else None


def upsert_digest(date: str, payload: dict) -> None:
    _request(
        "POST",
        "digests",
        params={"on_conflict": "date"},
        json_body=[{"date": date, "generated_at": payload["generated_at"], "payload": payload}],
        upsert=True,
    )


def fetch_index() -> list[dict]:
    rows = _request("GET", "digest_index", params={"select": "date,item_count"}).json()
    weeks = {r["week"] for r in _request("GET", "syntheses", params={"select": "week"}).json()}
    return derive_index(rows, weeks)


def upsert_synthesis(week: str, title: str, date: str, body: str) -> None:
    _request(
        "POST",
        "syntheses",
        params={"on_conflict": "week"},
        json_body=[{"week": week, "title": title, "date": date, "body": body}],
        upsert=True,
    )


def synthesis_exists(week: str) -> bool:
    rows = _request("GET", "syntheses", params={"week": f"eq.{week}", "select": "week"}).json()
    return len(rows) > 0


def cache_get(scope: str, keys: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for chunk in _chunks(keys):
        rows = _request(
            "GET",
            "kv_cache",
            params={"scope": f"eq.{scope}", "key": _in_param(chunk), "select": "key,value"},
        ).json()
        for r in rows:
            out[r["key"]] = r["value"]
    return out


def cache_put(scope: str, entries: dict[str, dict]) -> None:
    rows = [{"scope": scope, "key": k, "value": v} for k, v in entries.items()]
    for chunk in _chunks(rows):
        _request(
            "POST", "kv_cache", params={"on_conflict": "scope,key"}, json_body=chunk, upsert=True
        )
```

- [ ] **Step 4: Run** full pytest — 71 pass (67 + 4).

- [ ] **Step 5: Commit**

```bash
git add pipeline/store.py tests/test_store.py
git commit -m "feat(pipeline): add supabase store layer"
```

---

### Task 2: Injectable caches in `embed.py` + `summarize.py`

**Files:**
- Modify: `pipeline/embed.py`, `pipeline/summarize.py`
- Modify: `tests/test_embed.py`, `tests/test_summarize.py` (cache_path args → injected dict-backed fns)

- [ ] **Step 1: `pipeline/embed.py`** — replace the cache plumbing (drop `EMBEDDINGS_CACHE`, `_load_cache`, `cache_path` param, `json`/`Path` imports if then unused):

```python
from __future__ import annotations

from typing import Callable, Optional

from pipeline.models import Item

Encoder = Callable[[list[str]], list[list[float]]]
CacheGet = Callable[[list[str]], dict[str, list[float]]]
CachePut = Callable[[dict[str, list[float]]], None]

MODEL_NAME = "all-MiniLM-L6-v2"


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _text(item: Item) -> str:
    return f"{item.title}. {item.abstract}".strip()


def _default_encoder() -> Encoder:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)

    def encode(texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in model.encode(texts)]

    return encode


def _store_get(keys: list[str]) -> dict[str, list[float]]:
    from pipeline import store

    return {k: v["v"] for k, v in store.cache_get("embeddings", keys).items()}


def _store_put(entries: dict[str, list[float]]) -> None:
    from pipeline import store

    store.cache_put("embeddings", {k: {"v": v} for k, v in entries.items()})


def embed_items(
    items: list[Item],
    encoder: Optional[Encoder] = None,
    cache_get: Optional[CacheGet] = None,
    cache_put: Optional[CachePut] = None,
) -> dict[str, list[float]]:
    get = cache_get or _store_get
    put = cache_put or _store_put
    keys = [_key(it) for it in items]
    cache = get(keys)
    missing = [it for it in items if _key(it) not in cache]
    if missing:
        enc = encoder or _default_encoder()
        vectors = enc([_text(it) for it in missing])
        fresh = {_key(it): list(vec) for it, vec in zip(missing, vectors)}
        cache.update(fresh)
        put(fresh)
    return {k: cache[k] for k in keys}
```

(Vectors wrap as `{"v": [...]}` because `kv_cache.value` is a jsonb object.)

- [ ] **Step 2: `pipeline/summarize.py`** — same pattern: drop `SUMMARIES_CACHE`, `_load_cache`, `cache_path` param (and `json`/`Path` imports if then unused); `summarize_items` becomes:

```python
CacheGet = Callable[[list[str]], dict[str, dict]]
CachePut = Callable[[dict[str, dict]], None]


def _store_get(keys: list[str]) -> dict[str, dict]:
    from pipeline import store

    return store.cache_get("summaries", keys)


def _store_put(entries: dict[str, dict]) -> None:
    from pipeline import store

    store.cache_put("summaries", entries)


def summarize_items(
    items: list[Item],
    llm: Optional[LLMJson] = None,
    cache_get: Optional[CacheGet] = None,
    cache_put: Optional[CachePut] = None,
) -> dict[str, dict]:
    get = cache_get or _store_get
    put = cache_put or _store_put
    keys = [_key(it) for it in items]
    cache = get(keys)
    missing = [it for it in items if _key(it) not in cache]
    fresh: dict[str, dict] = {}
    if missing:
        call = llm if llm is not None else _default_llm()
        if call is not None:
            for it in missing:
                try:
                    fresh[_key(it)] = call(SYSTEM_PROMPT, _summary_prompt(it), SUMMARY_SCHEMA)
                except Exception:  # one bad item must not kill the batch
                    log.exception("summary failed for %s; skipping", _key(it))
            if fresh:
                put(fresh)
            cache.update(fresh)
    return {k: cache[k] for k in keys if k in cache}
```

- [ ] **Step 3: Rewire tests.** Open `tests/test_embed.py` and `tests/test_summarize.py`; wherever a test passes `cache_path=tmp_path / "cache.json"` (or relies on the file cache), replace with dict-backed fakes:

```python
def _mem_cache():
    store: dict = {}

    def get(keys):
        return {k: store[k] for k in keys if k in store}

    def put(entries):
        store.update(entries)

    return store, get, put
```

and call `embed_items(items, encoder=fake, cache_get=get, cache_put=put)` / `summarize_items(items, llm=fake, cache_get=get, cache_put=put)`. Assertions about cache reuse switch from re-reading the file to asserting against the backing dict (e.g. second call with `encoder=None`... keep passing the fake encoder but assert it was called only for missing items via a counter). Preserve each test's intent 1:1; total test count must not drop.

- [ ] **Step 4: Run** full pytest — 71 pass. (`run.py`/`backfill.py` still call the old signatures positionally only via `summarize_items(selected)` / `embed_items(items)` — unchanged args, still valid.)

- [ ] **Step 5: Commit**

```bash
git add pipeline/embed.py pipeline/summarize.py tests/test_embed.py tests/test_summarize.py
git commit -m "feat(pipeline): store-backed embedding and summary caches"
```

---

### Task 3: `synthesize.py` on the store

**Files:**
- Modify: `pipeline/synthesize.py`
- Modify: `tests/test_synthesize.py`

- [ ] **Step 1: Replace `recent_summaries` and `write_synthesis`:**

```python
FetchDigest = Callable[[str], Optional[dict]]


def recent_summaries(
    date_str: str, days: int = 7, fetch_digest: Optional[FetchDigest] = None
) -> list[dict]:
    if fetch_digest is None:
        from pipeline import store

        fetch_digest = store.fetch_digest
    end = date.fromisoformat(date_str)
    out: list[dict] = []
    for i in range(days):
        d = (end - timedelta(days=i)).isoformat()
        digest = fetch_digest(d)
        if not digest:
            continue
        for item in digest.get("items", []):
            if item.get("summary"):
                out.append(
                    {
                        "title": item.get("title", ""),
                        "summary": item["summary"],
                        "topic": item.get("topic"),
                    }
                )
    return out


def synthesis_record(date_str: str, essay: str) -> dict:
    week = iso_week(date_str)
    return {
        "week": week,
        "title": f"The Throughline - Week {week}",
        "date": date_str,
        "body": essay,
    }
```

(`write_synthesis` deleted; `DEFAULT_CONTENT_DIR`/`Path` imports removed from this module if now unused. `Callable`/`Optional` already imported or add them.)

- [ ] **Step 2: Rewire tests.** In `tests/test_synthesize.py`: `test_recent_summaries_collects_only_summarized` builds a dict of digests and passes `fetch_digest=digests.get` instead of writing tmp files; `test_write_synthesis_creates_mdx` becomes:

```python
def test_synthesis_record_shape():
    rec = synthesis_record("2026-06-14", "essay body")
    assert rec == {
        "week": "2026-24",
        "title": "The Throughline - Week 2026-24",
        "date": "2026-06-14",
        "body": "essay body",
    }
```

Other tests untouched. Count stays equal.

- [ ] **Step 3: Run** full pytest — 71 pass (run.py still imports `write_synthesis` — it will break import! So: do Task 3 and Task 4's run.py import swap TOGETHER if the suite fails on import; the plan orders Step 3 to tolerate this by running only `tests/test_synthesize.py` here, full suite green after Task 4). Run: `.venv/bin/python -m pytest tests/test_synthesize.py -q` — green.

- [ ] **Step 4: Commit**

```bash
git add pipeline/synthesize.py tests/test_synthesize.py
git commit -m "feat(pipeline): synthesis reads and records via store"
```

---

### Task 4: `run.py` + `digest.py` + `backfill.py` on the store

**Files:**
- Modify: `pipeline/run.py`, `pipeline/digest.py`, `pipeline/backfill.py`
- Modify: `tests/test_digest.py`, `tests/test_run_merge.py`

- [ ] **Step 1: `pipeline/run.py`.** Imports: drop `write_digest` (keep `build_digest` — change the digest import to `from pipeline.digest import build_digest`), drop `DEFAULT_CONTENT_DIR` if unused after, change synthesize import to `from pipeline.synthesize import iso_week, recent_summaries, synthesis_record, synthesize_week`, add `from pipeline import store`. Delete `load_existing_digest` (function). In `main()`:
  - `existing = load_existing_digest(args.date, DEFAULT_CONTENT_DIR)` → `existing = store.fetch_digest(args.date)`
  - the `write_digest(...)` call →

```python
    payload = build_digest(
        args.date,
        items,
        topics=topics,
        topic_by_key=topic_by_key,
        summaries=summaries,
        scores=scores,
    )
    store.upsert_digest(args.date, payload)
    log.info("upserted digest %s (%d items)", args.date, len(items))
```

  - synthesis block: `week_file = ...` / `week_file.exists()` → `already = store.synthesis_exists(iso_week(args.date))` and the guard `(is_sunday and not already) or args.synthesize`; success branch:

```python
            week_summaries = recent_summaries(args.date)
            essay = synthesize_week(week_summaries)
            if essay:
                rec = synthesis_record(args.date, essay)
                store.upsert_synthesis(**rec)
                log.info("upserted synthesis %s", rec["week"])
```

- [ ] **Step 2: `pipeline/digest.py`** — delete `write_digest` and `_update_index` (and now-unused imports); keep `build_digest` and `DEFAULT_CONTENT_DIR` (migration script still reads files from it).

- [ ] **Step 3: `pipeline/backfill.py`** — drop `_update_index` import (and `DEFAULT_CONTENT_DIR` usage in main), add `from pipeline import store`. In `main()` replace the whole write loop (digests_dir/index_path/prior_synthesis/file loop) with:

```python
    summaries = summarize_items(milestones, llm=llm) if milestones else {}

    for day in sorted(buckets):
        existing = store.fetch_digest(day)
        merged = merge_digest_dict(existing, day, buckets[day])
        merged = apply_summaries_to_digest(merged, summaries)
        store.upsert_digest(day, merged)
        log.info("upserted %s (%d items)", day, len(merged["items"]))
```

(`json`/`Path` imports removed from backfill if then unused.)

- [ ] **Step 4: Tests.** `tests/test_digest.py`: delete `test_write_digest_is_idempotent_and_updates_index` (and unused imports). `tests/test_run_merge.py`: delete `test_load_existing_digest_roundtrip` and the `load_existing_digest`/`json` imports; keep the three merge tests.

- [ ] **Step 5: Run** full pytest — expect **69 pass** (71 from Task 1 minus the two deleted file-IO tests). Also `.venv/bin/python -c "import pipeline.run, pipeline.backfill"` clean.

- [ ] **Step 6: Commit**

```bash
git add pipeline/run.py pipeline/digest.py pipeline/backfill.py tests/test_digest.py tests/test_run_merge.py
git commit -m "feat(pipeline): write digests and syntheses to supabase"
```

---

### Task 5: Migration script + RUN it

**Files:**
- Create: `pipeline/migrate_to_db.py`

- [ ] **Step 1: Create `pipeline/migrate_to_db.py`:**

```python
"""One-off: load committed content/ + data/ files into Supabase. Idempotent."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pipeline import store
from pipeline.digest import DEFAULT_CONTENT_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("throughline")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FRONT = re.compile(r'^---\n(.*?)\n---\n?(.*)$', re.DOTALL)


def main() -> None:
    failed = 0

    digest_files = sorted((DEFAULT_CONTENT_DIR / "digests").glob("*.json"))
    for f in digest_files:
        try:
            payload = json.loads(f.read_text())
            store.upsert_digest(payload["date"], payload)
        except Exception:
            log.exception("digest %s failed", f.name)
            failed += 1
    log.info("digests: %d migrated", len(digest_files) - failed)

    synth_files = sorted((DEFAULT_CONTENT_DIR / "synthesis").glob("*.mdx"))
    for f in synth_files:
        try:
            m = _FRONT.match(f.read_text())
            fields = dict(
                (k.strip(), v.strip().strip('"'))
                for k, v in (line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
            )
            store.upsert_synthesis(
                fields["week"], fields["title"], fields["date"], m.group(2).strip()
            )
        except Exception:
            log.exception("synthesis %s failed", f.name)
            failed += 1
    log.info("syntheses: %d migrated", len(synth_files))

    for scope, path, wrap in (
        ("summaries", DATA_DIR / "summaries" / "cache.json", False),
        ("embeddings", DATA_DIR / "embeddings" / "cache.json", True),
    ):
        if not path.exists():
            log.info("%s cache absent; skipping", scope)
            continue
        try:
            raw = json.loads(path.read_text())
            entries = {k: ({"v": v} if wrap else v) for k, v in raw.items()}
            store.cache_put(scope, entries)
            log.info("%s cache: %d entries", scope, len(entries))
        except Exception:
            log.exception("%s cache failed", scope)
            failed += 1

    if failed:
        raise SystemExit(f"{failed} migration failures")
    log.info("migration complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it** (env from .env):

```bash
cd "/Users/g/Desktop/Projects/Claude Projects" && set -a; source .env; set +a; .venv/bin/python -m pipeline.migrate_to_db
```

Expected: `digests: 161 migrated`, syntheses count (1 if the local 2026-24.mdx exists, else 0), cache counts, `migration complete`.

- [ ] **Step 3: Verify counts via store:**

```bash
set -a; source .env; set +a; .venv/bin/python -c "
from pipeline import store
idx = store.fetch_index()
print('index rows:', len(idx), 'newest:', idx[0])
d = store.fetch_digest(idx[0]['date'])
print('items in newest:', len(d['items']))"
```

Expected: `index rows: 161` (±, matches `ls content/digests | wc -l`), newest date matches, item count > 0.

- [ ] **Step 4: Commit**

```bash
git add pipeline/migrate_to_db.py
git commit -m "feat(pipeline): add one-off file-to-supabase migration"
```

---

### Task 6: Frontend loaders on Supabase

**Files:**
- Rewrite: `src/lib/content.ts`
- Rewrite: `src/lib/synthesis.ts`

- [ ] **Step 1: Rewrite `src/lib/content.ts`:**

```ts
import "server-only";
import type { Digest, IndexEntry, Item, Topic } from "./types";
import { getServiceClient } from "./supabase";

function isoWeek(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00Z`);
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-${String(week).padStart(2, "0")}`;
}

export async function getIndex(): Promise<IndexEntry[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    const [idx, syn] = await Promise.all([
      client
        .from("digest_index")
        .select("date, item_count")
        .order("date", { ascending: false }),
      client.from("syntheses").select("week"),
    ]);
    if (idx.error || !idx.data) return [];
    const weeks = new Set((syn.data ?? []).map((w) => w.week as string));
    return idx.data.map((r) => ({
      date: r.date as string,
      item_count: (r.item_count as number) ?? 0,
      has_synthesis: weeks.has(isoWeek(r.date as string)),
    }));
  } catch {
    return [];
  }
}

export async function getDigest(date: string): Promise<Digest | null> {
  const client = getServiceClient();
  if (!client) return null;
  try {
    const { data, error } = await client
      .from("digests")
      .select("payload")
      .eq("date", date)
      .maybeSingle();
    if (error || !data) return null;
    return data.payload as Digest;
  } catch {
    return null;
  }
}

async function digestsQuery(
  before: string | null,
  count: number | null,
): Promise<Digest[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    let q = client
      .from("digests")
      .select("payload")
      .order("date", { ascending: false });
    if (before) q = q.lt("date", before);
    if (count !== null) q = q.limit(count);
    const { data, error } = await q;
    if (error || !data) return [];
    return data.map((r) => r.payload as Digest);
  } catch {
    return [];
  }
}

export async function getLatestDigest(): Promise<Digest | null> {
  const [d] = await digestsQuery(null, 1);
  return d ?? null;
}

export async function getLatestTopics(): Promise<Topic[]> {
  const digest = await getLatestDigest();
  return digest?.topics ?? [];
}

export async function getTopic(
  tag: string,
): Promise<{ label: string; items: Item[] } | null> {
  const digest = await getLatestDigest();
  if (!digest) return null;
  const topic = digest.topics.find((t) => t.tag === tag);
  if (!topic) return null;
  const byKey = new Map(digest.items.map((i) => [`${i.source}:${i.id}`, i]));
  const items = topic.item_ids
    .map((id) => byKey.get(id))
    .filter((i): i is Item => Boolean(i))
    .sort((a, b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0));
  return { label: topic.label, items };
}

export async function getRecentDigests(count = 7): Promise<Digest[]> {
  return digestsQuery(null, count);
}

export async function getDigestsBefore(
  date: string,
  count = 7,
): Promise<{ digests: Digest[]; nextBefore: string | null }> {
  const page = await digestsQuery(date, count + 1);
  const digests = page.slice(0, count);
  const nextBefore =
    page.length > count && digests.length > 0
      ? digests[digests.length - 1].date
      : null;
  return { digests, nextBefore };
}

let allDigestsCache: { key: string; digests: Digest[] } | null = null;

/** Every digest, newest first. Cached per instance; invalidates on new head/length. */
export async function getAllDigests(): Promise<Digest[]> {
  const probe = await digestsQuery(null, 1);
  const head = probe[0]?.date ?? "";
  if (allDigestsCache && allDigestsCache.key.startsWith(`${head}:`)) {
    return allDigestsCache.digests;
  }
  const digests = await digestsQuery(null, null);
  allDigestsCache = { key: `${head}:${digests.length}`, digests };
  return digests;
}
```

- [ ] **Step 2: Rewrite `src/lib/synthesis.ts`:**

```ts
import "server-only";
import { getServiceClient } from "./supabase";

export type SynthesisMeta = { week: string; title: string; date: string };

export async function getSyntheses(): Promise<SynthesisMeta[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    const { data, error } = await client
      .from("syntheses")
      .select("week, title, date")
      .order("week", { ascending: false });
    if (error || !data) return [];
    return data as SynthesisMeta[];
  } catch {
    return [];
  }
}

export async function getSynthesis(
  week: string,
): Promise<{ meta: SynthesisMeta; body: string } | null> {
  const client = getServiceClient();
  if (!client) return null;
  try {
    const { data, error } = await client
      .from("syntheses")
      .select("week, title, date, body")
      .eq("week", week)
      .maybeSingle();
    if (error || !data) return null;
    const { body, ...meta } = data;
    return { meta: meta as SynthesisMeta, body: body as string };
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: Verify against the migrated DB** (dev server picks env from .env): `npx tsc --noEmit` clean; `npm test` 33; `npm run lint` 0; dev server: `/` renders board from DB (compare item count vs `content/digests/<latest>.json`), `/archive` lists 161 dates, `/search?q=anthropic` returns archive hits, `/synthesis` lists the migrated week (if any). Kill server.

- [ ] **Step 4: Commit**

```bash
git add src/lib/content.ts src/lib/synthesis.ts
git commit -m "feat(web): read digests and syntheses from supabase"
```

---

### Task 7: Workflows + repo cleanup

**Files:**
- Modify: `.github/workflows/daily-digest.yml`, `.github/workflows/backfill.yml`
- Delete: `content/`, `data/`
- Modify: `.env.example`, `.github/workflows/*` (no other)

- [ ] **Step 1:** In BOTH workflow files delete the entire final commit step (`- name: Commit digest if changed ...` / `- name: Commit backfill if changed ...` through their `git push` lines). The pipeline-run steps and env blocks stay (SUPABASE vars already present).
- [ ] **Step 2:** `git rm -r content data` (the migration in Task 5 already loaded them; history preserves them).
- [ ] **Step 3:** In `.env.example`, move/annotate `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` as REQUIRED (pipeline and site read from Supabase).
- [ ] **Step 4:** Verify: `.venv/bin/python -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/daily-digest.yml','.github/workflows/backfill.yml']]; print('yaml ok')"`; full pytest 69 (nothing imports the deleted dirs); `npm run build` succeeds (loaders read DB).
- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: retire committed data files in favor of supabase"
```

---

### Task 8: Full verification + USER GATE + push

- [ ] **Step 1:** Suites: pytest 69, vitest 33, lint 0, tsc clean, build green.
- [ ] **Step 2:** Same-day write smoke (env-sourced): `set -a; source .env; set +a; .venv/bin/python -m pipeline.run --dry-run` (fetch-only sanity). Optionally a REAL local run writes today's digest row to Supabase — acceptable (real data, same as CI would).
- [ ] **Step 3:** **USER GATE — do not push until the user confirms** `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` exist in BOTH GitHub Actions secrets and Vercel project env. Without Vercel env the deployed site renders empty; without Actions secrets every pipeline run fails loudly.
- [ ] **Step 4:** Push; verify prod board renders; dispatch `daily-digest` workflow once and confirm a digest row updates (no git commit expected from CI anymore).
