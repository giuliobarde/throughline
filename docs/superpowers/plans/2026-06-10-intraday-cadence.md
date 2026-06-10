# Intraday Cadence + Same-Day Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the pipeline every 3 hours with same-day digest merging (no item/summary loss on rerun) and a once-per-week synthesis guard.

**Architecture:** Two pure helpers in `pipeline/run.py` (`load_existing_digest`, `merge_run_items`) feed the existing write path: merged item pool goes through the unchanged ML steps, carried-forward summaries layer under this run's results. The workflow cron flips to `0 */3 * * *`. Synthesis is skipped when the week's `.mdx` already exists unless `--synthesize` forces it.

**Tech Stack:** Python 3.12 · pytest · GitHub Actions cron.

**Spec:** `docs/superpowers/specs/2026-06-10-intraday-cadence-design.md`

**Commit rules (repo non-negotiable):** plain `git commit`, exact messages, NO Co-Authored-By/Claude trailer.

**Key existing facts:**
- `pipeline/run.py` `main()` currently: `collect()` → ML steps over fetched `items` → `write_digest(args.date, items, topics=, topic_by_key=, summaries=, scores=)` → Sunday/`--synthesize` synthesis block. `DEFAULT_CONTENT_DIR` imported from `pipeline.digest`.
- `pipeline/models.py` `Item.from_dict(d)` reads only the nine dataclass fields — tolerates digest dicts' extra keys (`topic`, `summary`, `for_you_score`, `repro_difficulty`).
- `pipeline/synthesize.py` exports `iso_week(date_str) -> "YYYY-WW"`; synthesis files live at `content/synthesis/{week}.mdx`; `DEFAULT_CONTENT_DIR` is the same `content/` root.
- Digest item dicts carry `summary`/`repro_difficulty` when summarized; key everywhere `f"{source}:{id}"`.
- pytest baseline: **63 pass** (`.venv/bin/python -m pytest -q`).
- `.github/workflows/daily-digest.yml` line 5: `- cron: "0 12 * * *" # ~daily at 12:00 UTC`.

---

### Task 1: Merge helpers in `pipeline/run.py`

**Files:**
- Modify: `pipeline/run.py`
- Test: `tests/test_run_merge.py` (create)

- [ ] **Step 1: Write failing tests** — create `tests/test_run_merge.py`:

```python
from __future__ import annotations

import json

from pipeline.models import Item
from pipeline.run import load_existing_digest, merge_run_items


def _item(id: str, source: str = "arxiv", title: str = "fresh") -> Item:
    return Item(
        id=id,
        source=source,
        title=title,
        url=f"https://example.com/{id}",
        abstract="",
        authors=[],
        published_at="2026-06-10T00:00:00+00:00",
        has_code=False,
        code_url=None,
    )


def _existing_digest() -> dict:
    return {
        "date": "2026-06-10",
        "generated_at": "earlier",
        "items": [
            {
                "id": "a",
                "source": "arxiv",
                "title": "old title wins",
                "url": "https://example.com/a",
                "abstract": "",
                "authors": [],
                "published_at": "2026-06-10T00:00:00+00:00",
                "has_code": False,
                "code_url": None,
                "summary": "carried summary",
                "repro_difficulty": "low",
                "topic": "t1",
                "for_you_score": 0.5,
            },
            {
                "id": "b",
                "source": "github",
                "title": "no summary yet",
                "url": "https://example.com/b",
                "abstract": "",
                "authors": [],
                "published_at": "2026-06-10T01:00:00+00:00",
                "has_code": True,
                "code_url": "https://example.com/b",
            },
        ],
        "topics": [],
    }


def test_merge_existing_wins_and_new_appended():
    pool, carried = merge_run_items(_existing_digest(), [_item("a"), _item("c")])
    keys = [f"{i.source}:{i.id}" for i in pool]
    assert keys == ["arxiv:a", "github:b", "arxiv:c"]
    assert pool[0].title == "old title wins"  # existing version kept


def test_merge_carries_only_nonempty_summaries():
    _, carried = merge_run_items(_existing_digest(), [])
    assert carried == {
        "arxiv:a": {"summary": "carried summary", "repro_difficulty": "low"}
    }


def test_merge_none_existing_is_passthrough():
    fetched = [_item("x")]
    pool, carried = merge_run_items(None, fetched)
    assert pool == fetched
    assert carried == {}


def test_load_existing_digest_roundtrip(tmp_path):
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "2026-06-10.json").write_text(json.dumps({"date": "2026-06-10", "items": [], "topics": []}))
    assert load_existing_digest("2026-06-10", tmp_path) == {
        "date": "2026-06-10",
        "items": [],
        "topics": [],
    }
    assert load_existing_digest("2026-06-09", tmp_path) is None
    (digests / "bad.json").write_text("{not json")
    assert load_existing_digest("bad", tmp_path) is None
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_run_merge.py -q` — FAIL (imports missing).

- [ ] **Step 3: Implement** — in `pipeline/run.py`, add to the imports block:

```python
from pathlib import Path
from typing import Optional
```

and add after `dedupe()`:

```python
def load_existing_digest(date: str, content_dir: Path) -> Optional[dict]:
    """Today's digest from an earlier run, or None (absent/corrupt → fresh build)."""
    path = content_dir / "digests" / f"{date}.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def merge_run_items(
    existing: Optional[dict], fetched: list[Item]
) -> tuple[list[Item], dict[str, dict]]:
    """Union of an earlier same-day run and this fetch.

    Existing items win on duplicate keys (their metadata is already enriched);
    new keys append. Carried summaries survive even if their item isn't
    selected for summarization this run.
    """
    if not existing:
        return fetched, {}
    pool: list[Item] = []
    carried: dict[str, dict] = {}
    seen: set[str] = set()
    for d in existing.get("items", []):
        key = f"{d['source']}:{d['id']}"
        seen.add(key)
        pool.append(Item.from_dict(d))
        if d.get("summary"):
            carried[key] = {
                "summary": d["summary"],
                "repro_difficulty": d.get("repro_difficulty"),
            }
    for it in fetched:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        pool.append(it)
    return pool, carried
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` — 67 pass (63 + 4).

- [ ] **Step 5: Commit**

```bash
git add pipeline/run.py tests/test_run_merge.py
git commit -m "feat(pipeline): add same-day digest merge helpers"
```

---

### Task 2: Wire merge into `main()` + synthesis guard

**Files:**
- Modify: `pipeline/run.py` (`main()`)

No new unit tests (wiring; helpers are covered; verified by full suite + a local same-day double-run check against a temp copy is NOT possible without writing content/ — verify via code inspection + suite + CI behavior).

- [ ] **Step 1: Modify `main()`** — replace the block between `items = collect()` and the `if args.dry_run:` check so the merge happens after the dry-run early-exit. The full new `main()` body from `items = collect()` through the `write_digest(...)` call:

```python
    items = collect()
    log.info("collected %d items for %s", len(items), args.date)

    if args.dry_run:
        print(json.dumps([it.to_dict() for it in items], indent=2))
        return

    existing = load_existing_digest(args.date, DEFAULT_CONTENT_DIR)
    items, carried_summaries = merge_run_items(existing, items)
    if existing:
        log.info("merged with earlier run: %d items in pool", len(items))

    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    summaries: dict[str, dict] = dict(carried_summaries)
    scores: dict[str, float] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
            selected = select_for_summary(items, topic_by_key)
            summaries = {**carried_summaries, **summarize_items(selected)}
            log.info("summarized %d items", len(summaries))
            topics = label_topics(topics, items)
            scores = compute_scores(items, embeddings, fetch_feedback())
            log.info("scored %d items", len(scores))
        except Exception:  # ML/LLM/ranking failure must not lose the digest
            log.exception("ml/summarize/rank step failed; writing with what we have")

    out = write_digest(
        args.date,
        items,
        topics=topics,
        topic_by_key=topic_by_key,
        summaries=summaries,
        scores=scores,
    )
    log.info("wrote %s", out)
```

(Note the two deliberate details: `summaries` initializes to `dict(carried_summaries)` so an ML-step crash still writes carried summaries; the success path layers fresh results over carried ones.)

- [ ] **Step 2: Synthesis guard** — replace the synthesis block at the end of `main()`:

```python
    is_sunday = date_cls.fromisoformat(args.date).weekday() == 6
    week_file = DEFAULT_CONTENT_DIR / "synthesis" / f"{iso_week(args.date)}.mdx"
    if (is_sunday and not week_file.exists()) or args.synthesize:
        try:
            week_summaries = recent_summaries(DEFAULT_CONTENT_DIR, args.date)
            essay = synthesize_week(week_summaries)
            if essay:
                log.info("wrote synthesis %s", write_synthesis(args.date, essay))
            else:
                log.info("no synthesis written (empty essay)")
        except Exception:
            log.exception("synthesis step failed; digest already written")
    elif is_sunday:
        log.info("synthesis for %s already exists; skipping", iso_week(args.date))
```

and add `iso_week` to the existing synthesize import line:

```python
from pipeline.synthesize import iso_week, recent_summaries, synthesize_week, write_synthesis
```

- [ ] **Step 3: Verify** — `.venv/bin/python -m pytest -q` 67 pass (registration test in test_blogs imports run.py — confirms it still imports cleanly). Then `.venv/bin/python -m pipeline.run --dry-run` runs and prints fetched JSON without touching content/ (`git status --porcelain content/` empty).

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): merge same-day runs and guard weekly synthesis"
```

---

### Task 3: Cron to every 3 hours

**Files:**
- Modify: `.github/workflows/daily-digest.yml:5`

- [ ] **Step 1: Edit the schedule line:**

```yaml
    - cron: "0 */3 * * *" # every 3 hours UTC; same-day runs merge into one digest
```

- [ ] **Step 2: Validate** `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-digest.yml')); print('yaml ok')"` → `yaml ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "ci: run digest pipeline every 3 hours"
```

---

### Task 4: Verification

- [ ] **Step 1:** `.venv/bin/python -m pytest -q` → 67 pass; `npm test` → 26 pass; `npm run lint` → 0; `npx tsc --noEmit` → clean (frontend untouched — sanity only).
- [ ] **Step 2:** Hand back to controller: push; optionally `workflow_dispatch` daily-digest once and confirm a second same-day run grows (not replaces) today's digest, preserving summaries.
