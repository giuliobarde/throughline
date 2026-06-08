# Phase 8b — Personalization Ranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score each digest item with a `for_you_score` from a LogisticRegression trained on 👍/👎 feedback (cold-start heuristic until enough feedback), and surface a "For You" strip + score-ordered topics.

**Architecture:** `pipeline/rank.py` reads feedback from Supabase PostgREST via httpx (injectable for tests) and computes per-item scores: a trained `LogisticRegression` on cached embeddings once there are ≥3 👍 and ≥3 👎, else a recency/source/code cold-start heuristic. `run.py` wires it on the write path; `digest.py` attaches `for_you_score`; the home page renders a "For You" strip and sorts topic items by score.

**Tech Stack:** Python 3.12 (`httpx`, `scikit-learn`, `numpy`, `pytest` — all present); Next.js/TS frontend.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/rank.py             # NEW — fetch_feedback, compute_scores, _cold_start helpers
/pipeline/digest.py           # MODIFY — build_digest/write_digest accept scores
/pipeline/run.py              # MODIFY — fetch_feedback → compute_scores on write path
/tests/test_rank.py           # NEW
/tests/test_digest.py         # MODIFY — scores enrichment test
/src/app/page.tsx             # MODIFY — For You strip + score-sorted topics
/.github/workflows/daily-digest.yml  # MODIFY — pass SUPABASE_URL + SERVICE_ROLE_KEY
```

---

### Task 1: Cold-start scoring (pure)

**Files:**
- Create: `pipeline/rank.py`
- Create: `tests/test_rank.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rank.py`:

```python
from pipeline.rank import compute_scores
from pipeline.models import Item


def _item(source: str, id_: str, published: str, has_code: bool = False) -> Item:
    return Item(
        id=id_, source=source, title=f"T{id_}", url="http://x",
        abstract="a", authors=[], published_at=published,
        has_code=has_code, code_url=None,
    )


def test_cold_start_ranks_newer_code_github_higher():
    items = [
        _item("github", "g", "2026-06-08T00:00:00Z", has_code=True),
        _item("arxiv", "a", "2026-06-01T00:00:00Z", has_code=False),
    ]
    scores = compute_scores(items, embeddings={}, feedback_rows=[])
    assert scores["github:g"] > scores["arxiv:a"]


def test_below_threshold_uses_cold_start():
    # 2 pos / 2 neg is below the >=3/>=3 threshold -> heuristic, not model
    items = [
        _item("github", "g", "2026-06-08T00:00:00Z", has_code=True),
        _item("arxiv", "a", "2026-06-01T00:00:00Z"),
    ]
    embeddings = {"github:g": [0.0, 0.0], "arxiv:a": [1.0, 1.0]}
    feedback = [("x1", 1), ("x2", 1), ("y1", -1), ("y2", -1)]
    # those item_ids aren't in embeddings, so training set is empty anyway;
    # cold-start ordering must hold
    scores = compute_scores(items, embeddings, feedback)
    assert scores["github:g"] > scores["arxiv:a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rank.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.rank).

- [ ] **Step 3: Write the cold-start core**

Create `pipeline/rank.py`:

```python
from __future__ import annotations

from pipeline.models import Item

SOURCE_WEIGHT = {"github": 0.15, "hackernews": 0.10, "news": 0.10, "arxiv": 0.05}
MIN_PER_CLASS = 3


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _recency_norm(items: list[Item]) -> dict[str, float]:
    order = sorted(items, key=lambda i: i.published_at or "", reverse=True)
    n = len(order)
    return {_key(it): (1.0 if n <= 1 else 1.0 - idx / (n - 1)) for idx, it in enumerate(order)}


def _cold_start_scores(items: list[Item]) -> dict[str, float]:
    recency = _recency_norm(items)
    scores: dict[str, float] = {}
    for it in items:
        scores[_key(it)] = (
            recency[_key(it)]
            + SOURCE_WEIGHT.get(it.source, 0.0)
            + (0.1 if it.has_code else 0.0)
        )
    return scores


def compute_scores(
    items: list[Item],
    embeddings: dict[str, list[float]],
    feedback_rows: list[tuple[str, int]],
) -> dict[str, float]:
    # Training set: fed-back items that have a cached embedding.
    train_x: list[list[float]] = []
    train_y: list[int] = []
    for item_id, signal in feedback_rows:
        if item_id in embeddings:
            train_x.append(embeddings[item_id])
            train_y.append(1 if signal > 0 else 0)
    pos = sum(train_y)
    neg = len(train_y) - pos
    if pos < MIN_PER_CLASS or neg < MIN_PER_CLASS:
        return _cold_start_scores(items)

    import numpy as np
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(np.array(train_x), np.array(train_y))
    pos_idx = list(clf.classes_).index(1)
    cold = _cold_start_scores(items)
    scores: dict[str, float] = {}
    for it in items:
        k = _key(it)
        if k in embeddings:
            proba = clf.predict_proba(np.array([embeddings[k]]))[0][pos_idx]
            scores[k] = float(proba)
        else:
            scores[k] = cold[k]
    return scores
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rank.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/rank.py tests/test_rank.py
git commit -m "feat(pipeline): add cold-start ranking and score scaffold"
```

---

### Task 2: Trained-path test

**Files:**
- Modify: `tests/test_rank.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rank.py`:

```python
def test_trained_path_scores_near_positive_higher():
    # cluster A near [0,0,0]; cluster B near [9,9,9]
    items = [
        _item("arxiv", "newA", "2026-06-08T00:00:00Z"),
        _item("arxiv", "newB", "2026-06-08T00:00:00Z"),
    ]
    embeddings = {
        # fed-back training items
        "arxiv:a1": [0.0, 0.0, 0.1], "arxiv:a2": [0.1, 0.0, 0.0], "arxiv:a3": [0.0, 0.1, 0.0],
        "arxiv:b1": [9.0, 9.0, 9.1], "arxiv:b2": [9.1, 9.0, 9.0], "arxiv:b3": [9.0, 9.1, 9.0],
        # items to score
        "arxiv:newA": [0.05, 0.05, 0.0], "arxiv:newB": [9.0, 9.0, 9.0],
    }
    feedback = [
        ("arxiv:a1", 1), ("arxiv:a2", 1), ("arxiv:a3", 1),
        ("arxiv:b1", -1), ("arxiv:b2", -1), ("arxiv:b3", -1),
    ]
    scores = compute_scores(items, embeddings, feedback)
    assert scores["arxiv:newA"] > scores["arxiv:newB"]
    assert 0.0 <= scores["arxiv:newA"] <= 1.0
```

- [ ] **Step 2: Run test to verify it passes (already implemented in Task 1)**

Run: `.venv/bin/python -m pytest tests/test_rank.py::test_trained_path_scores_near_positive_higher -v`
Expected: PASS (the trained branch from Task 1 handles this).

- [ ] **Step 3: Commit**

```bash
git add tests/test_rank.py
git commit -m "test(pipeline): cover trained ranking path"
```

---

### Task 3: fetch_feedback (injectable httpx)

**Files:**
- Modify: `pipeline/rank.py`
- Modify: `tests/test_rank.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rank.py`:

```python
from pipeline.rank import fetch_feedback


def test_fetch_feedback_parses_rows():
    def stub():
        return [{"item_id": "arxiv:1", "signal": 1}, {"item_id": "hn:2", "signal": -1}]

    assert fetch_feedback(fetcher=stub) == [("arxiv:1", 1), ("hn:2", -1)]


def test_fetch_feedback_missing_env_returns_empty(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert fetch_feedback() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rank.py -k fetch -v`
Expected: FAIL (cannot import name 'fetch_feedback').

- [ ] **Step 3: Add fetch_feedback**

Add to the top imports of `pipeline/rank.py`:

```python
import logging
import os
from typing import Callable, Optional

import httpx
```

and add this `log` + function (place `log` after imports, function below `compute_scores`):

```python
log = logging.getLogger("throughline")

USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"

FeedbackFetcher = Callable[[], list[dict]]


def _default_fetcher() -> list[dict]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.warning("Supabase env not set; ranking without feedback")
        return []
    resp = httpx.get(
        f"{url}/rest/v1/feedback",
        params={"select": "item_id,signal"},
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "User-Agent": USER_AGENT,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_feedback(fetcher: Optional[FeedbackFetcher] = None) -> list[tuple[str, int]]:
    call = fetcher if fetcher is not None else _default_fetcher
    try:
        rows = call()
    except Exception:
        log.exception("fetch_feedback failed; returning no feedback")
        return []
    out: list[tuple[str, int]] = []
    for r in rows:
        item_id = r.get("item_id")
        signal = r.get("signal")
        if isinstance(item_id, str) and isinstance(signal, int):
            out.append((item_id, signal))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rank.py -v`
Expected: PASS (all rank tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/rank.py tests/test_rank.py
git commit -m "feat(pipeline): read feedback from Supabase PostgREST (injectable)"
```

---

### Task 4: Digest enrichment (for_you_score)

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_digest.py`:

```python
def test_build_digest_attaches_scores():
    items = [_item("1")]
    d = build_digest("2026-06-08", items, scores={"arxiv:1": 0.87})
    assert d["items"][0]["for_you_score"] == 0.87
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_digest.py::test_build_digest_attaches_scores -v`
Expected: FAIL (unexpected keyword argument 'scores').

- [ ] **Step 3: Update build_digest and write_digest**

In `pipeline/digest.py`, change `build_digest` signature + body to add `scores`:

```python
def build_digest(
    date: str,
    items: list[Item],
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
    summaries: dict[str, dict] | None = None,
    scores: dict[str, float] | None = None,
) -> dict:
    item_dicts = []
    for it in items:
        d = it.to_dict()
        key = f"{it.source}:{it.id}"
        if topic_by_key is not None:
            d["topic"] = topic_by_key.get(key)
        if summaries is not None and key in summaries:
            d["summary"] = summaries[key].get("summary")
            d["repro_difficulty"] = summaries[key].get("repro_difficulty")
        if scores is not None and key in scores:
            d["for_you_score"] = scores[key]
        item_dicts.append(d)
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_dicts,
        "topics": topics or [],
    }
```

And add `scores` to `write_digest` (pass-through):

```python
def write_digest(
    date: str,
    items: list[Item],
    content_dir: Path = DEFAULT_CONTENT_DIR,
    has_synthesis: bool = False,
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
    summaries: dict[str, dict] | None = None,
    scores: dict[str, float] | None = None,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(
        date,
        items,
        topics=topics,
        topic_by_key=topic_by_key,
        summaries=summaries,
        scores=scores,
    )
    out = digests_dir / f"{date}.json"
    out.write_text(json.dumps(digest, indent=2) + "\n")
    _update_index(content_dir, date, len(items), has_synthesis)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_digest.py -v`
Expected: PASS (all digest tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat(pipeline): attach for_you_score to digest items"
```

---

### Task 5: Wire ranking into run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Add import**

In `pipeline/run.py`, add after the summarize import line:

```python
from pipeline.rank import compute_scores, fetch_feedback
```

- [ ] **Step 2: Compute scores in the write-path block**

In `pipeline/run.py`, the write-path `if items:` block currently ends with
`topics = label_topics(items)`. Replace the whole block + the `write_digest` call with:

```python
    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    summaries: dict[str, dict] = {}
    scores: dict[str, dict] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
            selected = select_for_summary(items, topic_by_key)
            summaries = summarize_items(selected)
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

(Note: `scores` is typed `dict[str, dict]` only to satisfy the existing local-var style; the
values are floats. If a stricter annotation is preferred, use `dict[str, float]`.)

- [ ] **Step 3: Full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (34 + rank 5 + digest 1 = 40).

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): score items with personalization ranker on write path"
```

---

### Task 6: Frontend — For You strip + score-sorted topics

**Files:**
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Add the strip and sorting**

In `src/app/page.tsx`, after `const readSet = await getReadStates();` add a score sorter and a
"For You" list:

```tsx
  const byScore = (a: Item, b: Item) =>
    (b.for_you_score ?? 0) - (a.for_you_score ?? 0);
  const hasScores =
    !!digest && digest.items.some((i) => typeof i.for_you_score === "number");
  const forYou =
    digest && hasScores ? [...digest.items].sort(byScore).slice(0, 5) : [];
```

Then, inside the `digest.items.length > 0` branch, render the strip **above** the topics
block. Place this just before the `digest.topics.length > 0 ? (...)` expression by wrapping
the existing content. Concretely, change the structure to:

```tsx
      {!digest || digest.items.length === 0 ? (
        <p className="text-neutral-500">
          No digest yet. The pipeline runs daily.
        </p>
      ) : (
        <>
          {forYou.length > 0 && (
            <section className="mb-12">
              <h2 className="mb-2 font-mono text-xs uppercase tracking-wider text-amber-500">
                For You
              </h2>
              <div>
                {forYou.map((item) => (
                  <ItemCard
                    key={`fy-${itemKey(item)}`}
                    item={item}
                    initialRead={readSet.has(itemKey(item))}
                  />
                ))}
              </div>
            </section>
          )}

          {digest.topics.length > 0 ? (
            <div className="space-y-12">
              {digest.topics.map((topic) => {
                const byKey = new Map(digest.items.map((i) => [itemKey(i), i]));
                const topicItems = topic.item_ids
                  .map((id) => byKey.get(id))
                  .filter((i): i is Item => Boolean(i))
                  .sort(byScore);
                if (topicItems.length === 0) return null;
                return (
                  <section key={topic.tag}>
                    <h2 className="mb-2 font-mono text-xs uppercase tracking-wider text-neutral-500">
                      {topic.label}
                    </h2>
                    <div>
                      {topicItems.map((item) => (
                        <ItemCard
                          key={itemKey(item)}
                          item={item}
                          initialRead={readSet.has(itemKey(item))}
                        />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          ) : (
            <div>
              {[...digest.items].sort(byScore).map((item) => (
                <ItemCard
                  key={itemKey(item)}
                  item={item}
                  initialRead={readSet.has(itemKey(item))}
                />
              ))}
            </div>
          )}
        </>
      )}
```

(The `key={`fy-${itemKey(item)}`}` prefix avoids duplicate React keys since a For-You item
also appears in its topic section.)

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit`
Expected: no errors.
Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
git add src/app/page.tsx
git commit -m "feat(web): add For You strip and score-ordered topics"
```

---

### Task 7: CI — pass Supabase env to the pipeline

**Files:**
- Modify: `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Add Supabase env to the Run pipeline step**

In `.github/workflows/daily-digest.yml`, extend the "Run pipeline" `env` block:

```yaml
      - name: Run pipeline
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_MODEL: claude-haiku-4-5
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python -m pipeline.run
```

- [ ] **Step 2: Commit + push**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "ci: pass Supabase env to the pipeline for ranking"
git push
```

---

### Task 8: Live verification

**Files:** none

- [ ] **Step 1: Live run with all env (incl. Supabase)**

Run:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-08
```
Expected: logs `scored N items`; writes `content/digests/2026-06-08.json` with a
`for_you_score` on items. (Cold-start until ≥3 👍 + ≥3 👎 exist — that's expected now.)

- [ ] **Step 2: Inspect output**

Run:
```bash
.venv/bin/python -c "import json;d=json.load(open('content/digests/2026-06-08.json'));s=[(round(i.get('for_you_score',0),3),i['source'],i['title'][:40]) for i in d['items'] if 'for_you_score' in i];s.sort(reverse=True);print('scored:',len(s));[print(x) for x in s[:5]]"
```
Expected: top items skew newer / has_code / github+hn (cold-start heuristic).

- [ ] **Step 3: Visual check**

`set -a && . ./.env && set +a && npm run dev`, Playwright `http://localhost:3000`, confirm a
`FOR YOU` strip renders at the top. Screenshot. Then restore + stop:
```bash
git checkout content/index.json 2>/dev/null; rm -f content/digests/2026-06-08.json data/summaries/cache.json data/embeddings/cache.json
git checkout data 2>/dev/null
pkill -f "next dev"; pkill -f "next-server"
```
(If `content/digests/2026-06-08.json` was a committed Action digest, `git checkout` it instead
of `rm`.)

- [ ] **Step 4: Handoff reminder**

Confirm the user has added `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` to GitHub Actions
secrets so the daily Action ranks with real feedback.

---

## Self-review notes

- **Spec coverage:** cold-start scoring (T1), trained path (T2), fetch_feedback injectable +
  missing-env (T3), digest enrichment (T4), run.py wiring fault-tolerant (T5), For You strip +
  score-sorted topics (T6), CI env (T7), live verify + handoff (T8). All spec sections mapped.
- **Type consistency:** `compute_scores(items, embeddings, feedback_rows) -> dict[str, float]`;
  `fetch_feedback(fetcher=None) -> list[tuple[str,int]]`; `_key` = `f"{source}:{id}"`
  everywhere (matches embed/cluster/summarize/digest/frontend `itemKey`). `build_digest`/
  `write_digest` gain `scores`. Frontend reads `item.for_you_score` (already in TS `Item`).
- **Placeholder scan:** none.
- **Test math:** prior 34 + rank (2 cold-start + 1 trained + 2 fetch = 5) + digest 1 = 40.
- **Fault tolerance:** missing Supabase env → `fetch_feedback` `[]` → cold-start; any rank
  exception caught in run.py; offline pytest via injected fetcher + monkeypatched env.
- **No backdating / no Claude trailer** on commits.
```
