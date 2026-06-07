# Phase 7 — Claude Summaries + Topic Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Claude-generated practitioner summaries (+ structured repro difficulty) to the top items per topic and replace heuristic topic labels with Claude-named ones.

**Architecture:** A new `pipeline/summarize.py` exposes pure selection/labelling logic plus an injectable `llm` callable (default: the official `anthropic` Python SDK calling `claude-haiku-4-5` with `output_config.format` json-schema structured output). `run.py` selects ≤20 items per topic, summarizes them (cached), and relabels topics. `digest.py` attaches `summary` + `repro_difficulty` to item dicts. The frontend shows a `repro:` tag.

**Tech Stack:** Python 3.12 (`anthropic` SDK, `pytest`); Next.js/TS frontend.

**API note (from the claude-api skill):** Haiku 4.5 takes **no** `effort`/`thinking` params (they 400). Use a plain `client.messages.create(...)` with `output_config={"format":{"type":"json_schema","schema":...}}` and `json.loads` the first text block. Tests inject a stub `llm` so no key/network is needed offline.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/requirements.txt     # MODIFY — add anthropic
/pipeline/summarize.py         # NEW — select_for_summary, summarize_items, label_topics, _default_llm
/pipeline/digest.py            # MODIFY — build_digest/write_digest accept summaries
/pipeline/run.py               # MODIFY — select → summarize → relabel on write path
/tests/test_summarize.py       # NEW — offline (stub llm)
/tests/test_digest.py          # MODIFY — summaries enrichment test
/data/summaries/.gitkeep       # NEW
/src/components/ItemCard.tsx    # MODIFY — repro tag
/.github/workflows/daily-digest.yml  # MODIFY — pass ANTHROPIC_API_KEY + ANTHROPIC_MODEL
```

---

### Task 1: Dependency + summaries cache dir

**Files:**
- Modify: `pipeline/requirements.txt`
- Create: `data/summaries/.gitkeep`

- [ ] **Step 1: Add the dependency**

Append `anthropic` to `pipeline/requirements.txt` so it reads:

```
httpx==0.27.2
feedparser==6.0.11
pytest==8.3.3
sentence-transformers==3.0.1
scikit-learn==1.5.2
numpy==1.26.4
anthropic==0.69.0
```

- [ ] **Step 2: Install + verify (pin to the resolved version)**

Run: `.venv/bin/pip install -r pipeline/requirements.txt`
Then: `.venv/bin/python -c "import anthropic; print(anthropic.__version__)"`
Expected: prints a version. **If pip reports that `anthropic==0.69.0` is not found**, run
`.venv/bin/pip install -U anthropic`, read the installed version from the command above, and
edit `pipeline/requirements.txt` to pin that exact version. (Goal: a working pinned version,
not literally 0.69.0.)

- [ ] **Step 3: Create the cache dir keeper**

Create empty file `data/summaries/.gitkeep`.

- [ ] **Step 4: Commit**

```bash
git add pipeline/requirements.txt data/summaries/.gitkeep
git commit -m "chore(pipeline): add anthropic dep and summaries cache dir"
```

---

### Task 2: select_for_summary (pure, round-robin per topic)

**Files:**
- Create: `pipeline/summarize.py`
- Create: `tests/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_summarize.py`:

```python
from pipeline.summarize import select_for_summary
from pipeline.models import Item


def _item(source: str, id_: str, published: str) -> Item:
    return Item(
        id=id_, source=source, title=f"T{id_}", url="http://x",
        abstract="a", authors=[], published_at=published,
        has_code=False, code_url=None,
    )


def test_round_robin_balances_topics_and_respects_cap():
    # topic A has 3 items, topic B has 1
    items = [
        _item("arxiv", "a1", "2026-06-06T03:00:00Z"),
        _item("arxiv", "a2", "2026-06-06T02:00:00Z"),
        _item("arxiv", "a3", "2026-06-06T01:00:00Z"),
        _item("hn", "b1", "2026-06-06T09:00:00Z"),
    ]
    topic_by_key = {
        "arxiv:a1": "ta", "arxiv:a2": "ta", "arxiv:a3": "ta", "hn:b1": "tb",
    }
    selected = select_for_summary(items, topic_by_key, cap=3)
    ids = [f"{i.source}:{i.id}" for i in selected]
    assert len(ids) == 3
    # both topics represented before a topic gets a second slot:
    assert "hn:b1" in ids
    # within topic A, newest first => a1 before a2
    assert ids.index("arxiv:a1") < ids.index("arxiv:a2")


def test_cap_zero_padding_and_missing_topic_defaults_all():
    items = [_item("arxiv", "x", "2026-06-06T00:00:00Z")]
    selected = select_for_summary(items, {}, cap=5)  # no topic mapping
    assert [f"{i.source}:{i.id}" for i in selected] == ["arxiv:x"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.summarize).

- [ ] **Step 3: Write the selection logic**

Create `pipeline/summarize.py`:

```python
from __future__ import annotations

from collections import defaultdict

from pipeline.models import Item

SUMMARY_CAP = 20


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def select_for_summary(
    items: list[Item],
    topic_by_key: dict[str, str],
    cap: int = SUMMARY_CAP,
) -> list[Item]:
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        groups[topic_by_key.get(_key(it), "all")].append(it)
    for g in groups.values():
        g.sort(key=lambda i: i.published_at or "", reverse=True)  # newest first

    selected: list[Item] = []
    tags = list(groups.keys())
    idx = 0
    while len(selected) < cap and any(groups.values()):
        tag = tags[idx % len(tags)]
        bucket = groups.get(tag)
        if bucket:
            selected.append(bucket.pop(0))
        idx += 1
        if idx > len(tags) * (cap + 1):  # safety: avoid infinite loop
            break
    return selected[:cap]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/summarize.py tests/test_summarize.py
git commit -m "feat(pipeline): add per-topic round-robin summary selection"
```

---

### Task 3: summarize_items (injectable llm + JSON cache)

**Files:**
- Modify: `pipeline/summarize.py`
- Modify: `tests/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_summarize.py`:

```python
from pathlib import Path

from pipeline.summarize import summarize_items


class CountingLLM:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        return {"summary": "A grounded summary.", "repro_difficulty": "med"}


def test_summarize_computes_and_caches(tmp_path: Path):
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z")]
    llm = CountingLLM()
    out = summarize_items(items, llm=llm, cache_path=cache)
    assert out["arxiv:1"]["summary"] == "A grounded summary."
    assert out["arxiv:1"]["repro_difficulty"] == "med"
    assert llm.calls == 1
    assert cache.exists()

    llm2 = CountingLLM()
    out2 = summarize_items(items, llm=llm2, cache_path=cache)
    assert llm2.calls == 0  # cached
    assert out2["arxiv:1"]["summary"] == "A grounded summary."


def test_summarize_no_llm_returns_cached_only(tmp_path: Path):
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z")]
    out = summarize_items(items, llm=None, cache_path=cache)  # no key path
    assert out == {}


def test_summarize_skips_item_on_llm_error(tmp_path: Path):
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z"),
             _item("arxiv", "2", "2026-06-06T00:00:00Z")]

    def flaky(system, user, schema):
        if "T1" in user:
            raise RuntimeError("boom")
        return {"summary": "ok", "repro_difficulty": "low"}

    out = summarize_items(items, llm=flaky, cache_path=cache)
    assert "arxiv:1" not in out  # errored item skipped
    assert out["arxiv:2"]["summary"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -k summarize -v`
Expected: FAIL (cannot import name 'summarize_items').

- [ ] **Step 3: Add constants, schema, llm-resolver, and summarize_items**

Add to the top of `pipeline/summarize.py` (after the existing imports):

```python
import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("throughline")

LLMJson = Callable[[str, str, dict], dict]

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
SUMMARIES_CACHE = (
    Path(__file__).resolve().parent.parent / "data" / "summaries" / "cache.json"
)

SYSTEM_PROMPT = (
    "You write tight, grounded summaries for an audience of engineers who ship "
    "ML systems. No hype, no corporate filler. For the given item, write 2-3 "
    "sentences: what it is, and why someone shipping ML systems should care. Then "
    "judge how hard it would be to reproduce or adopt: 'low', 'med', or 'high'."
)

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "repro_difficulty": {"type": "string", "enum": ["low", "med", "high"]},
    },
    "required": ["summary", "repro_difficulty"],
    "additionalProperties": False,
}


def _default_llm() -> Optional[LLMJson]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set; skipping summaries/labels")
        return None
    import anthropic

    client = anthropic.Anthropic()

    def call(system: str, user: str, schema: dict) -> dict:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return json.loads(text)

    return call


def _summary_prompt(item: Item) -> str:
    code = "yes" if item.has_code else "no"
    return (
        f"Title: {item.title}\n"
        f"Source: {item.source}\n"
        f"Code available: {code}\n"
        f"Abstract: {item.abstract}"
    )


def _load_cache(cache_path: Path) -> dict[str, dict]:
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}


def summarize_items(
    items: list[Item],
    llm: Optional[LLMJson] = None,
    cache_path: Path = SUMMARIES_CACHE,
) -> dict[str, dict]:
    cache = _load_cache(cache_path)
    missing = [it for it in items if _key(it) not in cache]
    if missing:
        call = llm if llm is not None else _default_llm()
        if call is not None:
            for it in missing:
                try:
                    cache[_key(it)] = call(SYSTEM_PROMPT, _summary_prompt(it), SUMMARY_SCHEMA)
                except Exception:  # one bad item must not kill the batch
                    log.exception("summary failed for %s; skipping", _key(it))
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache))
    return {_key(it): cache[_key(it)] for it in items if _key(it) in cache}
```

Note: `Item` is already imported at the top of the file from Task 2.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -k summarize -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/summarize.py tests/test_summarize.py
git commit -m "feat(pipeline): add Claude summaries with structured output and cache"
```

---

### Task 4: label_topics (Claude relabel, graceful fallback)

**Files:**
- Modify: `pipeline/summarize.py`
- Modify: `tests/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_summarize.py`:

```python
from pipeline.summarize import label_topics


def test_label_topics_replaces_by_tag():
    topics = [
        {"tag": "t1", "label": "Old One", "item_ids": ["arxiv:1"]},
        {"tag": "t2", "label": "Old Two", "item_ids": ["arxiv:2"]},
    ]
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z"),
             _item("arxiv", "2", "2026-06-06T00:00:00Z")]

    def llm(system, user, schema):
        return {"labels": [{"tag": "t1", "label": "Diffusion Models"}]}

    out = label_topics(topics, items, llm=llm)
    by_tag = {t["tag"]: t["label"] for t in out}
    assert by_tag["t1"] == "Diffusion Models"  # replaced
    assert by_tag["t2"] == "Old Two"  # unmatched tag keeps old label


def test_label_topics_no_llm_unchanged():
    topics = [{"tag": "t1", "label": "Old", "item_ids": ["arxiv:1"]}]
    out = label_topics(topics, [_item("arxiv", "1", "2026-06-06T00:00:00Z")], llm=None)
    assert out == topics


def test_label_topics_llm_error_unchanged():
    topics = [{"tag": "t1", "label": "Old", "item_ids": ["arxiv:1"]}]

    def boom(system, user, schema):
        raise RuntimeError("x")

    out = label_topics(topics, [_item("arxiv", "1", "2026-06-06T00:00:00Z")], llm=boom)
    assert out == topics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -k label -v`
Expected: FAIL (cannot import name 'label_topics').

- [ ] **Step 3: Add LABEL_SYSTEM, LABELS_SCHEMA, label_topics**

Append to `pipeline/summarize.py`:

```python
LABEL_SYSTEM = (
    "You name clusters of AI/ML items with short, specific topic labels of 2-4 "
    "words in Title Case, based on the member titles. Return one label per tag given."
)

LABELS_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["tag", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


def _labels_prompt(topics: list[dict], items: list[Item]) -> str:
    by_key = {_key(it): it for it in items}
    lines: list[str] = []
    for t in topics:
        titles = [
            by_key[k].title for k in t["item_ids"][:5] if k in by_key
        ]
        lines.append(f"tag {t['tag']}:")
        for title in titles:
            lines.append(f"  - {title}")
    return "\n".join(lines)


def label_topics(
    topics: list[dict],
    items: list[Item],
    llm: Optional[LLMJson] = None,
) -> list[dict]:
    call = llm if llm is not None else _default_llm()
    if call is None:
        return topics
    try:
        result = call(LABEL_SYSTEM, _labels_prompt(topics, items), LABELS_SCHEMA)
        new_labels = {x["tag"]: x["label"] for x in result.get("labels", [])}
    except Exception:
        log.exception("topic labelling failed; keeping heuristic labels")
        return topics
    return [
        {**t, "label": new_labels.get(t["tag"], t["label"])} for t in topics
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_summarize.py -v`
Expected: PASS (all summarize tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/summarize.py tests/test_summarize.py
git commit -m "feat(pipeline): add Claude topic labelling with heuristic fallback"
```

---

### Task 5: Digest enrichment (summary + repro_difficulty)

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_digest.py`:

```python
def test_build_digest_attaches_summaries():
    items = [_item("1")]
    summaries = {"arxiv:1": {"summary": "S", "repro_difficulty": "low"}}
    d = build_digest("2026-06-06", items, summaries=summaries)
    assert d["items"][0]["summary"] == "S"
    assert d["items"][0]["repro_difficulty"] == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_digest.py::test_build_digest_attaches_summaries -v`
Expected: FAIL (unexpected keyword argument 'summaries').

- [ ] **Step 3: Update build_digest and write_digest**

In `pipeline/digest.py`, change `build_digest` to accept and apply `summaries`:

```python
def build_digest(
    date: str,
    items: list[Item],
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
    summaries: dict[str, dict] | None = None,
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
        item_dicts.append(d)
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_dicts,
        "topics": topics or [],
    }
```

And update `write_digest` to thread `summaries` through:

```python
def write_digest(
    date: str,
    items: list[Item],
    content_dir: Path = DEFAULT_CONTENT_DIR,
    has_synthesis: bool = False,
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
    summaries: dict[str, dict] | None = None,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(
        date, items, topics=topics, topic_by_key=topic_by_key, summaries=summaries
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
git commit -m "feat(pipeline): attach Claude summary and repro difficulty to digest items"
```

---

### Task 6: Wire summaries + labels into run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Add imports**

In `pipeline/run.py`, add after the existing `from pipeline.embed import embed_items` line:

```python
from pipeline.summarize import label_topics, select_for_summary, summarize_items
```

- [ ] **Step 2: Extend the write-path block**

In `pipeline/run.py`, replace the existing ML block (the `if items:` block that calls
`embed_items`/`cluster_items`) with:

```python
    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    summaries: dict[str, dict] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
            selected = select_for_summary(items, topic_by_key)
            summaries = summarize_items(selected)
            log.info("summarized %d items", len(summaries))
            topics = label_topics(topics, items)
        except Exception:  # ML/LLM failure must not lose the digest
            log.exception("ml/summarize step failed; writing with what we have")

    out = write_digest(
        args.date,
        items,
        topics=topics,
        topic_by_key=topic_by_key,
        summaries=summaries,
    )
    log.info("wrote %s", out)
```

- [ ] **Step 3: Full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (Phase 6's 25 + summarize 8 + digest 1 = 34).

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): summarize top items and relabel topics on write path"
```

---

### Task 7: Frontend — repro tag

**Files:**
- Modify: `src/components/ItemCard.tsx`

- [ ] **Step 1: Add the repro tag to the metadata row**

In `src/components/ItemCard.tsx`, add a repro tag after the topic tag. The metadata `<div>`
should read:

```tsx
      <div className="flex items-center gap-3">
        <SourceBadge source={item.source} />
        {item.has_code && (
          <span className="font-mono text-xs text-emerald-500">code</span>
        )}
        {item.repro_difficulty && (
          <span className="font-mono text-xs text-amber-500">
            repro: {item.repro_difficulty}
          </span>
        )}
        {item.topic && (
          <span className="font-mono text-xs text-neutral-600">#{item.topic}</span>
        )}
        <time className="font-mono text-xs text-neutral-600">
          {item.published_at.slice(0, 10)}
        </time>
      </div>
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit`
Expected: no errors.
Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
git add src/components/ItemCard.tsx
git commit -m "feat(web): show reproduction-difficulty tag on item cards"
```

---

### Task 8: CI — pass Anthropic env to the pipeline

**Files:**
- Modify: `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Add ANTHROPIC env to the Run pipeline step**

In `.github/workflows/daily-digest.yml`, extend the "Run pipeline" step's `env` block:

```yaml
      - name: Run pipeline
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_MODEL: claude-haiku-4-5
        run: python -m pipeline.run
```

- [ ] **Step 2: Commit + push**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "ci: pass Anthropic API key and model to the pipeline"
git push
```

---

### Task 9: Live verification

**Files:** none

- [ ] **Step 1: Live run with all keys**

Run:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-06
```
Expected: logs `clustered into N topics`, `summarized M items` (M ≤ 20); writes
`content/digests/2026-06-06.json` with Claude topic labels and per-item `summary` +
`repro_difficulty` on the selected items.

- [ ] **Step 2: Inspect output**

Run:
```bash
.venv/bin/python -c "import json;d=json.load(open('content/digests/2026-06-06.json'));print('labels:',[t['label'] for t in d['topics']]);s=[i for i in d['items'] if i.get('summary')];print('summarized:',len(s));print('sample:',s[0]['summary'][:120] if s else 'none','| repro:',s[0].get('repro_difficulty') if s else '-')"
```
Expected: real topic labels (not generic "Language Learning"); ≥1 summarized item with a
`repro_difficulty`.

- [ ] **Step 3 (optional): visual check**

`npm run dev`, Playwright `http://localhost:3000`, confirm topic section headings read as
real labels and summarized cards show a `repro:` tag + the Claude summary as body text. Then
restore content + caches (do not commit hand-run output):
```bash
git checkout content/index.json 2>/dev/null; rm -f content/digests/2026-06-06.json data/summaries/cache.json data/embeddings/cache.json
pkill -f "next dev"; pkill -f "next-server"
```

- [ ] **Step 4: Add the GitHub Actions secret (handoff)**

Tell the user to add `ANTHROPIC_API_KEY` as a repository secret (Settings → Secrets and
variables → Actions). Without it, the Action still runs and writes digests, but with no
summaries and heuristic topic labels.

---

## Self-review notes

- **Spec coverage:** dep + cache dir (T1), per-topic round-robin selection (T2), summaries +
  injectable llm + cache + per-item error skip + no-key path (T3), Claude labels + fallback
  (T4), digest enrichment (T5), run.py wiring with fault-tolerant fallback (T6), repro tag
  (T7), CI env (T8), live check + secret handoff (T9). All spec sections mapped.
- **API correctness (claude-api skill):** Haiku 4.5 → plain `messages.create`, no
  `effort`/`thinking`; `output_config.format` json_schema for structured output; official
  `anthropic` SDK; `json.loads` of the text block. Model from `ANTHROPIC_MODEL` env, default
  `claude-haiku-4-5`. No-key path returns gracefully (None llm).
- **Type consistency:** `select_for_summary(items, topic_by_key, cap) -> list[Item]`;
  `summarize_items(items, llm, cache_path) -> dict[str, dict]` (`{key: {summary,
  repro_difficulty}}`); `label_topics(topics, items, llm) -> list[dict]`; `_key` =
  `f"{source}:{id}"` everywhere (matches embed/cluster/digest/frontend). `LLMJson =
  Callable[[str, str, dict], dict]` used by all three. `build_digest`/`write_digest` gain
  `summaries`. Frontend reads `item.summary` (already via `summary ?? abstract`) and
  `item.repro_difficulty` (already in the TS `Item` type).
- **Placeholder scan:** none. Blank caches + `.gitkeep` are intentional. The `anthropic`
  version pin is resolved-at-install (T1 Step 2), not a placeholder.
- **Test math:** Phase 6 left 25; +8 summarize (2 select, 3 summarize, 3 label) +1 digest = 34.
- **No backdating / no Claude trailer** on commits.
```
