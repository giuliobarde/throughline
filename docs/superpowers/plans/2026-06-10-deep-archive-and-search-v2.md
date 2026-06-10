# Deep Archive + Search v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill the archive from 2026-01-01 (with Claude-selected weekly milestone summaries), make search cover the entire archive with alias/domain-aware relevance, and add a debounced dynamic search dropdown.

**Architecture:** Backfill is a new pipeline CLI (`pipeline/backfill.py`) composed of pure, tested helpers (week chunking, date bucketing, merge-never-clobber, milestone selection with injectable LLM) plus thin `fetch_range` additions to existing sources; it runs in CI via a `workflow_dispatch` Action. Web side: a module-cached `getAllDigests` loader feeds both `/search` and a new lean `GET /api/search`; `src/lib/search.ts` gains alias groups, hostname/authors fields, and domain-term handling; the nav input becomes a `SearchBox` client component with a 250ms-debounced dropdown and a no-JS form fallback.

**Tech Stack:** Python 3.12 · httpx · feedparser · anthropic (json-schema output) · pytest · Next.js 16 · TS strict · Vitest.

**Spec:** `docs/superpowers/specs/2026-06-10-deep-archive-and-search-v2-design.md`

**Commit rules (repo non-negotiable):** plain `git commit` (author preconfigured Giulio), exact messages, **NO Co-Authored-By / Claude trailer**.

**Key existing facts:**
- `pipeline/models.py` `Item` frozen dataclass with `.to_dict()`; keys everywhere are `f"{source}:{id}"`.
- `pipeline/digest.py` exports `DEFAULT_CONTENT_DIR` and `_update_index(content_dir, date, item_count, has_synthesis)`.
- `pipeline/summarize.py` exports `LLMJson = Callable[[str, str, dict], dict]`, `_default_llm()` (None without `ANTHROPIC_API_KEY`), `summarize_items(items, llm=None, cache_path=...)` (cache at `data/summaries/cache.json`).
- `pipeline/sources/arxiv.py`: `ARXIV_API`, `CATEGORIES`, `USER_AGENT`, `parse_arxiv_feed`. `hackernews.py`: `ALGOLIA_API`, `MIN_POINTS`, `USER_AGENT`, `parse_hn_results`, `filter_ai_ml` (imports `time` only — range fn needs `datetime`/`timezone` added). `github.py`: `GITHUB_SEARCH_API`, `USER_AGENT`, `parse_github_results` (already imports `os`, `date`). `blogs.py`: `FEEDS`, `USER_AGENT`, `parse_feed`.
- Web: `src/lib/content.ts` has `getIndex`/`getDigest`; `src/lib/feed.ts` has `itemKey`, `mergeDigests`, type `FeedItem`; `src/lib/search.ts` has `searchItems(items, topics, q, limit=20)`; `src/app/layout.tsx` nav has a `<form action="/search">` with one styled input; `/search` page uses `getRecentDigests(7)`.
- Tests: `.venv/bin/python -m pytest -q` → 51 pass; `npm test` → 20 pass. Repo lint pattern: mount-time setState needs `// eslint-disable-next-line react-hooks/set-state-in-effect`.
- `.github/workflows/daily-digest.yml` is the template for env/secrets/commit steps (commit author Giulio, message `chore(digest): <date>`).
- arXiv rate-limits the local dev IP — backfill executes in CI; local verification uses `--dry-run` and tolerates arXiv failures (fault-tolerant skip).

---

### Task 1: Backfill pure helpers

**Files:**
- Create: `pipeline/backfill.py` (pure parts)
- Test: `tests/test_backfill.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_backfill.py`:

```python
from __future__ import annotations

from datetime import date

from pipeline.models import Item
from pipeline.backfill import (
    apply_summaries_to_digest,
    bucket_by_date,
    merge_digest_dict,
    week_chunks,
)


def _item(id: str, published_at: str, source: str = "arxiv") -> Item:
    return Item(
        id=id,
        source=source,
        title=f"title {id}",
        url=f"https://example.com/{id}",
        abstract="",
        authors=[],
        published_at=published_at,
        has_code=False,
        code_url=None,
    )


def test_week_chunks_align_to_weeks_inclusive():
    # Thu Jan 1 2026 .. Mon Jan 12 2026
    chunks = week_chunks(date(2026, 1, 1), date(2026, 1, 12))
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 4)),    # partial week (Sun end)
        (date(2026, 1, 5), date(2026, 1, 11)),   # full Mon-Sun
        (date(2026, 1, 12), date(2026, 1, 12)),  # partial tail
    ]


def test_bucket_by_date_bounds_and_dedupe():
    items = [
        _item("a", "2026-01-03T10:00:00+00:00"),
        _item("a", "2026-01-03T10:00:00+00:00"),  # dup key dropped
        _item("b", "2026-01-04T00:00:00+00:00"),
        _item("early", "2025-12-31T23:59:00+00:00"),  # before range
        _item("late", "2026-02-01T00:00:00+00:00"),   # after range
        _item("undated", ""),                          # dropped
    ]
    buckets = bucket_by_date(items, date(2026, 1, 1), date(2026, 1, 31))
    assert sorted(buckets.keys()) == ["2026-01-03", "2026-01-04"]
    assert [i.id for i in buckets["2026-01-03"]] == ["a"]


def test_merge_digest_dict_never_clobbers_existing():
    existing = {
        "date": "2026-01-03",
        "generated_at": "old",
        "items": [
            {"id": "a", "source": "arxiv", "summary": "keep me", "title": "old a"},
        ],
        "topics": [{"tag": "t", "label": "T", "item_ids": []}],
    }
    merged = merge_digest_dict(existing, "2026-01-03", [_item("a", "x"), _item("b", "2026-01-03T00:00:00+00:00")])
    ids = [d["id"] for d in merged["items"]]
    assert ids == ["a", "b"]  # existing first, new appended, dup skipped
    assert merged["items"][0]["summary"] == "keep me"  # untouched
    assert merged["topics"] == existing["topics"]


def test_merge_digest_dict_from_scratch():
    merged = merge_digest_dict(None, "2026-01-05", [_item("c", "2026-01-05T00:00:00+00:00")])
    assert merged["date"] == "2026-01-05"
    assert merged["topics"] == []
    assert [d["id"] for d in merged["items"]] == ["c"]


def test_apply_summaries_to_digest_patches_matching_items():
    digest = {
        "date": "2026-01-03",
        "items": [
            {"id": "a", "source": "arxiv", "title": "t"},
            {"id": "b", "source": "github", "title": "t"},
        ],
        "topics": [],
    }
    out = apply_summaries_to_digest(
        digest, {"arxiv:a": {"summary": "s!", "repro_difficulty": "low"}}
    )
    assert out["items"][0]["summary"] == "s!"
    assert out["items"][0]["repro_difficulty"] == "low"
    assert "summary" not in out["items"][1]
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_backfill.py -q` — FAIL (no module).

- [ ] **Step 3: Implement** — create `pipeline/backfill.py`:

```python
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from pipeline.digest import DEFAULT_CONTENT_DIR, _update_index
from pipeline.models import Item
from pipeline.summarize import LLMJson, _default_llm, summarize_items

log = logging.getLogger("throughline")

SELECT_SYSTEM = (
    "You curate a tech-history archive. From this week's item listing, select ONLY "
    "landmark events: major model announcements, breakout open-source repos, or "
    "landmark research papers. Fewer is better; zero is acceptable. Never more than 5. "
    "Return the item ids exactly as given."
)

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 5}
    },
    "required": ["item_ids"],
    "additionalProperties": False,
}


def week_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Inclusive [start, end] split at Sunday boundaries (first/last may be partial)."""
    chunks: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        week_end = min(cur + timedelta(days=6 - cur.weekday()), end)
        chunks.append((cur, week_end))
        cur = week_end + timedelta(days=1)
    return chunks


def bucket_by_date(items: list[Item], start: date, end: date) -> dict[str, list[Item]]:
    """Group by published date; drop undated, out-of-range, and duplicate keys."""
    buckets: dict[str, list[Item]] = {}
    seen: set[str] = set()
    lo, hi = start.isoformat(), end.isoformat()
    for it in items:
        day = (it.published_at or "")[:10]
        if not day or day < lo or day > hi:
            continue
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        buckets.setdefault(day, []).append(it)
    return buckets


def merge_digest_dict(
    existing: Optional[dict], date_str: str, new_items: list[Item]
) -> dict:
    """Append new items to an existing digest dict; never touch existing entries."""
    items: list[dict] = list(existing.get("items", [])) if existing else []
    seen = {f"{d['source']}:{d['id']}" for d in items}
    for it in new_items:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        items.append(it.to_dict())
    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "topics": (existing or {}).get("topics", []),
    }


def apply_summaries_to_digest(digest: dict, summaries: dict[str, dict]) -> dict:
    for d in digest.get("items", []):
        key = f"{d['source']}:{d['id']}"
        if key in summaries:
            d["summary"] = summaries[key].get("summary")
            d["repro_difficulty"] = summaries[key].get("repro_difficulty")
    return digest
```

(`argparse`, `json`, `time`, `Path`, `httpx`, `_update_index`, `_default_llm`, `summarize_items`, `SELECT_*` are used by Tasks 3-4 appending to this file — keep them now; repo has no Python linter in CI.)

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_backfill.py -q` — 5 pass. Full suite — 56 pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/backfill.py tests/test_backfill.py
git commit -m "feat(pipeline): add backfill chunking, bucketing, and merge helpers"
```

---

### Task 2: Historical `fetch_range` for arXiv / HN / GitHub

**Files:**
- Modify: `pipeline/sources/arxiv.py` (append)
- Modify: `pipeline/sources/hackernews.py` (append; add `datetime`/`timezone` imports)
- Modify: `pipeline/sources/github.py` (append)
- Test: append to `tests/test_backfill.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_backfill.py`:

```python
def test_arxiv_range_params_window():
    from pipeline.sources.arxiv import arxiv_range_params

    p = arxiv_range_params(date(2026, 1, 5), date(2026, 1, 11))
    assert "submittedDate:[202601050000 TO 202601112359]" in p["search_query"]
    assert p["search_query"].startswith("(cat:")
    assert p["max_results"] == "100"


def test_hn_range_params_filters():
    from pipeline.sources.hackernews import hn_range_params

    p = hn_range_params(1000, 2000)
    assert p["numericFilters"] == "points>=100,created_at_i>=1000,created_at_i<2000"
    assert p["hitsPerPage"] == "1000"


def test_github_range_params_query():
    from pipeline.sources.github import github_range_params

    p = github_range_params(date(2026, 1, 5), date(2026, 1, 11))
    assert p["q"] == "machine learning created:2026-01-05..2026-01-11"
    assert p["sort"] == "stars"
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_backfill.py -q` — 3 new FAIL.

- [ ] **Step 3: Implement.**

Append to `pipeline/sources/arxiv.py`:

```python
def arxiv_range_params(
    start, end, start_index: int = 0, max_results: int = 100
) -> dict:
    query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    window = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    return {
        "search_query": f"({query}) AND {window}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": str(start_index),
        "max_results": str(max_results),
    }


def fetch_arxiv_range(start, end, timeout: float = 30.0) -> list[Item]:
    resp = httpx.get(
        ARXIV_API,
        params=arxiv_range_params(start, end),
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return parse_arxiv_feed(resp.text)
```

Append to `pipeline/sources/hackernews.py` (and add `from datetime import datetime, timezone` to its imports):

```python
def hn_range_params(start_ts: int, end_ts: int) -> dict:
    return {
        "tags": "story",
        "numericFilters": (
            f"points>={MIN_POINTS},created_at_i>={start_ts},created_at_i<{end_ts}"
        ),
        "hitsPerPage": "1000",
    }


def fetch_hn_range(start, end, timeout: float = 30.0) -> list[Item]:
    start_ts = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86400
    resp = httpx.get(
        ALGOLIA_API,
        params=hn_range_params(start_ts, end_ts),
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return filter_ai_ml(parse_hn_results(resp.json()))
```

Append to `pipeline/sources/github.py`:

```python
def github_range_params(start: date, end: date, per_page: int = 10) -> dict:
    return {
        "q": f"machine learning created:{start.isoformat()}..{end.isoformat()}",
        "sort": "stars",
        "order": "desc",
        "per_page": str(per_page),
    }


def fetch_github_range(start: date, end: date, timeout: float = 30.0) -> list[Item]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.get(
        GITHUB_SEARCH_API,
        params=github_range_params(start, end),
        timeout=timeout,
        headers=headers,
    )
    resp.raise_for_status()
    return parse_github_results(resp.json())
```

- [ ] **Step 4: Run** full suite — 59 pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/arxiv.py pipeline/sources/hackernews.py pipeline/sources/github.py tests/test_backfill.py
git commit -m "feat(pipeline): add historical fetch_range to arxiv, hn, github sources"
```

---

### Task 3: Milestone selection

**Files:**
- Modify: `pipeline/backfill.py` (append)
- Test: append to `tests/test_backfill.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_backfill.py`:

```python
def test_select_milestones_with_injectable_llm_filters_bad_ids():
    from pipeline.backfill import select_milestones

    items = [_item("a", "2026-01-03T00:00:00+00:00"), _item("b", "2026-01-04T00:00:00+00:00")]

    def llm(system, user, schema):
        assert "arxiv:a" in user and "arxiv:b" in user
        return {"item_ids": ["arxiv:a", "bogus:zzz", "arxiv:a"]}

    picked = select_milestones(items, llm)
    assert [i.id for i in picked] == ["a"]  # bad id dropped, dup collapses


def test_select_milestones_no_llm_or_empty():
    from pipeline.backfill import select_milestones

    assert select_milestones([_item("a", "2026-01-03T00:00:00+00:00")], None) == []
    assert select_milestones([], lambda s, u, j: {"item_ids": []}) == []


def test_select_milestones_llm_error_returns_empty():
    from pipeline.backfill import select_milestones

    def boom(system, user, schema):
        raise RuntimeError("api down")

    assert select_milestones([_item("a", "2026-01-03T00:00:00+00:00")], boom) == []
```

- [ ] **Step 2: Run** — 3 new FAIL.

- [ ] **Step 3: Implement** — append to `pipeline/backfill.py`:

```python
def week_listing(items: list[Item]) -> str:
    lines: list[str] = []
    for it in items:
        who = it.authors[0] if it.authors else ""
        lines.append(f"{it.source}:{it.id} | {it.source} | {who} | {it.title}")
    return "\n".join(lines)


def select_milestones(items: list[Item], llm: Optional[LLMJson]) -> list[Item]:
    if llm is None or not items:
        return []
    by_key = {f"{it.source}:{it.id}": it for it in items}
    try:
        result = llm(SELECT_SYSTEM, week_listing(items), SELECT_SCHEMA)
    except Exception:  # selection is optional polish; never block the backfill
        log.exception("milestone selection failed for week; skipping")
        return []
    picked: list[Item] = []
    seen: set[str] = set()
    for key in result.get("item_ids", [])[:5]:
        if key in by_key and key not in seen:
            seen.add(key)
            picked.append(by_key[key])
    return picked
```

- [ ] **Step 4: Run** full suite — 62 pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/backfill.py tests/test_backfill.py
git commit -m "feat(pipeline): add Claude milestone selection for backfill weeks"
```

---

### Task 4: Backfill CLI orchestration

**Files:**
- Modify: `pipeline/backfill.py` (append `fetch_blog_history` + `main`)

No unit tests for the wiring (network + fs glue, mirrors run.py's untested main); verified via `--dry-run` and CI run.

- [ ] **Step 1: Append to `pipeline/backfill.py`:**

```python
def fetch_blog_history(since: date, timeout: float = 30.0) -> list[Item]:
    from pipeline.sources.blogs import FEEDS, USER_AGENT, parse_feed

    items: list[Item] = []
    for publisher, url in FEEDS:
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                follow_redirects=True,
            )
            resp.raise_for_status()
            items.extend(parse_feed(publisher, resp.text))
        except Exception:
            log.exception("blog feed %s failed; skipping", publisher)
    lo = since.isoformat()
    return [it for it in items if it.published_at and it.published_at[:10] >= lo]


def collect_week(ws: date, we: date) -> list[Item]:
    from pipeline.sources.arxiv import fetch_arxiv_range
    from pipeline.sources.github import fetch_github_range
    from pipeline.sources.hackernews import fetch_hn_range

    items: list[Item] = []
    for name, fn in (
        ("arxiv", fetch_arxiv_range),
        ("hackernews", fetch_hn_range),
        ("github", fetch_github_range),
    ):
        try:
            fetched = fn(ws, we)
            log.info("backfill %s %s..%s: %d items", name, ws, we, len(fetched))
            items.extend(fetched)
        except Exception:  # one source must not kill the week
            log.exception("backfill %s failed for %s..%s; skipping", name, ws, we)
        time.sleep(3)  # API politeness (arXiv especially)
    return items


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Throughline historical backfill")
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    parser.add_argument("--no-summaries", action="store_true", help="skip milestone summaries")
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    all_items: list[Item] = []
    milestones: list[Item] = []
    llm = None if (args.no_summaries or args.dry_run) else _default_llm()

    for ws, we in week_chunks(start, end):
        week_items = collect_week(ws, we)
        all_items.extend(week_items)
        if llm is not None and week_items:
            milestones.extend(select_milestones(week_items, llm))

    all_items.extend(fetch_blog_history(start))
    buckets = bucket_by_date(all_items, start, end)

    if args.dry_run:
        for day in sorted(buckets):
            print(f"{day}: {len(buckets[day])} items")
        print(f"total: {sum(len(v) for v in buckets.values())} items, {len(milestones)} milestones")
        return

    summaries = summarize_items(milestones, llm=llm) if milestones else {}

    digests_dir = DEFAULT_CONTENT_DIR / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    index_path = DEFAULT_CONTENT_DIR / "index.json"
    prior_synthesis = {}
    if index_path.exists():
        prior_synthesis = {
            e["date"]: e.get("has_synthesis", False)
            for e in json.loads(index_path.read_text())
        }

    for day in sorted(buckets):
        path = digests_dir / f"{day}.json"
        existing = json.loads(path.read_text()) if path.exists() else None
        merged = merge_digest_dict(existing, day, buckets[day])
        merged = apply_summaries_to_digest(merged, summaries)
        path.write_text(json.dumps(merged, indent=2) + "\n")
        _update_index(
            DEFAULT_CONTENT_DIR,
            day,
            len(merged["items"]),
            prior_synthesis.get(day, False),
        )
        log.info("wrote %s (%d items)", path, len(merged["items"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify locally** (arXiv may 429 locally — its skip-log is acceptable):

```bash
.venv/bin/python -m pytest -q                       # 62 pass
.venv/bin/python -m pipeline.backfill --from 2026-06-01 --to 2026-06-03 --dry-run
```

Expected dry-run: per-day counts printed (HN/GitHub/blogs at minimum), `total: N items, 0 milestones`, no files written (`git status --porcelain content/` empty).

- [ ] **Step 3: Commit**

```bash
git add pipeline/backfill.py
git commit -m "feat(pipeline): add backfill CLI orchestration"
```

---

### Task 5: Backfill workflow

**Files:**
- Create: `.github/workflows/backfill.yml`

- [ ] **Step 1: Create `.github/workflows/backfill.yml`:**

```yaml
name: backfill

on:
  workflow_dispatch:
    inputs:
      from:
        description: "start date YYYY-MM-DD"
        required: true
        default: "2026-01-01"
      to:
        description: "end date YYYY-MM-DD"
        required: true

permissions:
  contents: write

concurrency:
  group: daily-digest # share the daily pipeline's group: never write content concurrently
  cancel-in-progress: false

jobs:
  backfill:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: pipeline/requirements.txt

      - name: Install pipeline deps
        run: pip install -r pipeline/requirements.txt

      - name: Run backfill
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_MODEL: claude-haiku-4-5
        run: python -m pipeline.backfill --from "${{ inputs.from }}" --to "${{ inputs.to }}"

      - name: Commit backfill if changed
        run: |
          if [ -z "$(git status --porcelain content data)" ]; then
            echo "No content changes; nothing to commit."
            exit 0
          fi
          # Author as the repo owner via the verified GitHub noreply email so the
          # commit counts toward the contribution graph. Real timestamp; never backdated.
          git config user.name "Giulio"
          git config user.email "giuliobarde@users.noreply.github.com"
          git add content data
          git commit -m "chore(backfill): ${{ inputs.from }}..${{ inputs.to }}"
          git pull --rebase origin main
          git push
```

- [ ] **Step 2: Validate YAML**

Run: `npx --yes yaml-lint .github/workflows/backfill.yml 2>/dev/null || .venv/bin/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/backfill.yml')); print('yaml ok')"`
Expected: `yaml ok` (or yaml-lint pass).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/backfill.yml
git commit -m "ci: add dispatchable backfill workflow"
```

---

### Task 6: `getAllDigests` cached loader

**Files:**
- Modify: `src/lib/content.ts` (append)

Fs glue following the file's untested-loader pattern; exercised by Task 8's routes + build.

- [ ] **Step 1: Append to `src/lib/content.ts`:**

```ts
let allDigestsCache: { key: string; digests: Digest[] } | null = null;

/** Every digest in the archive, newest first. Cached per server instance;
 *  invalidates when the index head or length changes (new daily digest). */
export async function getAllDigests(): Promise<Digest[]> {
  const index = await getIndex();
  const cacheKey = `${index[0]?.date ?? ""}:${index.length}`;
  if (allDigestsCache && allDigestsCache.key === cacheKey) {
    return allDigestsCache.digests;
  }
  const digests = (
    await Promise.all(index.map((e) => getDigest(e.date)))
  ).filter((d): d is Digest => Boolean(d));
  allDigestsCache = { key: cacheKey, digests };
  return digests;
}
```

- [ ] **Step 2: Verify** `npx tsc --noEmit` clean; `npm test` 20 pass.

- [ ] **Step 3: Commit**

```bash
git add src/lib/content.ts
git commit -m "feat(web): add cached archive-wide digest loader"
```

---

### Task 7: Search relevance v2 (aliases, hostname, authors, domain terms)

**Files:**
- Modify: `src/lib/search.ts`
- Test: append to `tests/web/search.test.ts`

- [ ] **Step 1: Write failing tests** — append inside the existing `describe("searchItems")` in `tests/web/search.test.ts`:

```ts
  it("alias: 'claude' finds anthropic items via hostname and authors", () => {
    const viaHost = fi("h", "New model drops", { url: "https://www.anthropic.com/news/x" });
    const viaAuthor = fi("a", "Some announcement", {
      source: "blog",
      authors: ["Anthropic"],
      url: "https://example.org/y",
    });
    const miss = fi("m", "Unrelated", { url: "https://other.com/z" });
    const { items } = searchItems([miss, viaHost, viaAuthor], topics, "claude");
    expect(items.map((i) => i.id).sort()).toEqual(["a", "h"]);
  });

  it("alias works in reverse: 'openai' matches gpt in title", () => {
    const gptTitle = fi("g", "GPT-6 rumors intensify");
    const { items } = searchItems([gptTitle], topics, "openai");
    expect(items.map((i) => i.id)).toEqual(["g"]);
  });

  it("domain query matches hostname only", () => {
    const fromSite = fi("s", "Anything", { url: "https://anthropic.com/research/q" });
    const mentions = fi("m", "anthropic.com mentioned in title", { url: "https://other.com/p" });
    const { items } = searchItems([fromSite, mentions], topics, "anthropic.com");
    expect(items.map((i) => i.id)).toEqual(["s"]);
  });

  it("hostname match scores like a title match", () => {
    const hostHit = fi("hh", "Plain words", { url: "https://huggingface.co/blog/z" });
    const bodyHit = fi("bb", "Plain words", { abstract: "huggingface release notes" });
    const { items } = searchItems([bodyHit, hostHit], topics, "huggingface");
    expect(items.map((i) => i.id)).toEqual(["hh", "bb"]);
  });
```

- [ ] **Step 2: Run** `npm test` — 4 new FAIL.

- [ ] **Step 3: Rewrite `src/lib/search.ts`:**

```ts
import type { FeedItem } from "./feed";
import type { Topic } from "./types";

export type SearchResults = { items: FeedItem[]; topics: Topic[] };

/** Bidirectional alias groups: a query term expands to its whole group. */
const ALIAS_GROUPS: string[][] = [
  ["claude", "anthropic"],
  ["gpt", "openai", "chatgpt"],
  ["gemini", "deepmind"],
  ["llama", "meta"],
  ["huggingface", "hf"],
];

function expand(term: string): string[] {
  for (const group of ALIAS_GROUPS) {
    if (group.includes(term)) return group;
  }
  return [term];
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function terms(q: string): string[] {
  return q.toLowerCase().split(/\s+/).filter(Boolean);
}

function itemDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

/** Scoring per term: title x3, hostname/authors x3 (identity), topic x2, body x1.
 *  Terms containing a dot are domain queries: hostname only. Aliases expand terms. */
export function searchItems(
  items: FeedItem[],
  topics: Topic[],
  q: string,
  limit = 20,
): SearchResults {
  const ts = terms(q);
  if (ts.length === 0) return { items: [], topics: [] };
  const labelByTag = new Map(topics.map((t) => [t.tag, t.label.toLowerCase()]));

  const ranked = items
    .map((item) => {
      const title = item.title.toLowerCase();
      const body = (item.summary ?? item.abstract).toLowerCase();
      const host = hostname(item.url);
      const authors = item.authors.join(" ").toLowerCase();
      const topicText = item.topic
        ? `${item.topic.toLowerCase()} ${labelByTag.get(item.topic) ?? ""}`
        : "";
      let score = 0;
      for (const t of ts) {
        if (t.includes(".")) {
          if (host.includes(t)) score += 3;
          continue;
        }
        const variants = expand(t);
        const hit = (field: string) => variants.some((v) => field.includes(v));
        if (hit(title)) score += 3;
        if (hit(host) || hit(authors)) score += 3;
        if (hit(topicText)) score += 2;
        if (hit(body)) score += 1;
      }
      return { item, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || itemDate(b.item) - itemDate(a.item))
    .slice(0, limit)
    .map((s) => s.item);

  const matchedTopics = topics.filter((t) =>
    ts.some(
      (term) => t.tag.toLowerCase().includes(term) || t.label.toLowerCase().includes(term),
    ),
  );
  return { items: ranked, topics: matchedTopics };
}
```

- [ ] **Step 4: Run** `npm test` — all pass (24). `npx tsc --noEmit` clean. (Note: the old "title matches outrank abstract matches" test still passes — title 3 > body 1; the new hostname-vs-body test pins the ×3 identity weight.)

- [ ] **Step 5: Commit**

```bash
git add src/lib/search.ts tests/web/search.test.ts
git commit -m "feat(web): alias and domain aware search relevance"
```

---

### Task 8: `GET /api/search` + `/search` goes archive-wide

**Files:**
- Create: `src/app/api/search/route.ts`
- Modify: `src/app/search/page.tsx` (swap loader)

- [ ] **Step 1: Create `src/app/api/search/route.ts`:**

```ts
import { NextResponse } from "next/server";
import { getAllDigests } from "@/lib/content";
import { itemKey, mergeDigests } from "@/lib/feed";
import { searchItems } from "@/lib/search";

export async function GET(request: Request) {
  const q = (new URL(request.url).searchParams.get("q") ?? "").trim();
  if (q.length > 100) {
    return NextResponse.json({ error: "query too long" }, { status: 400 });
  }
  if (!q) return NextResponse.json({ items: [] });
  const digests = await getAllDigests();
  const pool = mergeDigests(digests);
  const topics = digests[0]?.topics ?? [];
  const { items } = searchItems(pool, topics, q, 8);
  return NextResponse.json({
    items: items.map((i) => ({
      key: itemKey(i),
      title: i.title,
      url: i.url,
      source: i.source,
      date: (i.published_at || i.digestDate).slice(0, 10),
    })),
  });
}
```

- [ ] **Step 2: Modify `src/app/search/page.tsx`** — two changes only:
- Import line: replace `import { getRecentDigests } from "@/lib/content";` with `import { getAllDigests } from "@/lib/content";`
- Loader line: replace `Promise.all([getRecentDigests(7), getVoteCounts()])` with `Promise.all([getAllDigests(), getVoteCounts()])`

- [ ] **Step 3: Verify** `npx tsc --noEmit` clean; dev server: `curl -s "http://localhost:3000/api/search?q=llm"` → JSON with ≤8 lean items; `curl -s "http://localhost:3000/api/search?q=$(python3 -c 'print("x"*101)')" -o /dev/null -w "%{http_code}"` → 400; `/search?q=llm` still renders. Kill server.

- [ ] **Step 4: Commit**

```bash
git add src/app/api/search/route.ts src/app/search/page.tsx
git commit -m "feat(web): add search API and make /search archive-wide"
```

---

### Task 9: `SearchBox` dynamic dropdown

**Files:**
- Create: `src/components/SearchBox.tsx`
- Modify: `src/app/layout.tsx` (replace the nav form with `<SearchBox />`)

- [ ] **Step 1: Create `src/components/SearchBox.tsx`:**

```tsx
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Hit = { key: string; title: string; url: string; source: string; date: string };

export function SearchBox() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) {
      setHits([]);
      setOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
          signal: ctrl.signal,
        });
        if (!res.ok) return;
        const data = (await res.json()) as { items: Hit[] };
        setHits(data.items);
        setOpen(data.items.length > 0);
      } catch {
        // aborted or offline — dropdown just stays as-is
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    function onDocMousedown(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocMousedown);
    return () => document.removeEventListener("mousedown", onDocMousedown);
  }, []);

  return (
    <div ref={boxRef} className="relative">
      <form action="/search">
        <input
          name="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          placeholder="search"
          aria-label="Search the board"
          aria-expanded={open}
          autoComplete="off"
          className="w-24 rounded-md border border-neutral-800 bg-neutral-900/60 px-2.5 py-1 font-mono text-xs text-neutral-200 outline-none transition-all placeholder:text-neutral-600 focus:w-40 focus:border-amber-500/60 sm:w-28 sm:focus:w-48"
        />
      </form>
      {open && hits.length > 0 && (
        <div
          role="listbox"
          aria-label="Search results"
          className="absolute right-0 top-full z-20 mt-2 w-72 rounded-xl border border-neutral-800 bg-neutral-950/95 p-1 shadow-xl backdrop-blur"
        >
          {hits.map((h) => (
            <a
              key={h.key}
              href={h.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg px-3 py-2 transition-colors hover:bg-neutral-900"
            >
              <span className="block truncate text-xs font-semibold text-neutral-200">
                {h.title}
              </span>
              <span className="font-mono text-[10px] uppercase text-neutral-500">
                {h.source} · {h.date}
              </span>
            </a>
          ))}
          <Link
            href={`/search?q=${encodeURIComponent(q.trim())}`}
            className="block rounded-lg px-3 py-2 font-mono text-[11px] text-amber-400 transition-colors hover:bg-neutral-900"
            onClick={() => setOpen(false)}
          >
            all results for &ldquo;{q.trim()}&rdquo; →
          </Link>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Swap into `src/app/layout.tsx`** — add `import { SearchBox } from "@/components/SearchBox";` and replace the whole `<form action="/search">…</form>` block in the nav with `<SearchBox />`.

- [ ] **Step 3: Verify** `npx tsc --noEmit` clean; `npm test` 24 pass; `npm run lint` 0 problems (if the rules complain about setState-in-effect here, add the repo's standard `// eslint-disable-next-line react-hooks/set-state-in-effect` on the flagged lines and note it). Dev server: type into the nav box → dropdown appears after ~250ms (verify via browser or by confirming `/api/search?q=ll` returns items and the page hydrates without console errors); Enter still navigates to `/search?q=…`. Kill server.

- [ ] **Step 4: Commit**

```bash
git add src/components/SearchBox.tsx src/app/layout.tsx
git commit -m "feat(web): dynamic search dropdown in nav"
```

---

### Task 10: Full verification

- [ ] **Step 1: Suites**

```bash
npm run lint        # 0 problems
npm test            # 24 pass
npx tsc --noEmit    # clean
npm run build       # succeeds
.venv/bin/python -m pytest -q   # 62 pass
```

- [ ] **Step 2: Dev smoke** — `/` nav search dropdown works; `/search?q=claude` returns Anthropic-ish hits (authors/hostname matching); `/api/search?q=zzz` → `{"items":[]}`.

- [ ] **Step 3: Hand back to controller** — push, dispatch the backfill Action (`gh workflow run backfill.yml -f from=2026-01-01 -f to=<today>`), watch the run, then verify production: `/search?q=fable`, `/search?q=claude`, `/search?q=openai.com`, and infinite scroll reaching January. (Controller handles push permission and Action monitoring.)
