# Tavily AI-News Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Tavily-backed AI/ML news source that folds recent industry news into the existing daily digest.

**Architecture:** A new `pipeline/sources/tavily.py` mirrors the arXiv source (pure parser + thin networked class with 429/500/503 retry). It POSTs to the Tavily Search API with `topic="news"` and a curated `include_domains` allowlist, maps results to the existing `Item` dataclass with `source="news"`, and is added to `run.py`'s `SOURCES`. The frontend gains a `news` badge. No digest/index format change.

**Tech Stack:** Python 3.12 (`httpx`, `pytest`), Tavily Search API; Next.js/TS frontend (`Item` union + `SourceBadge`).

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/sources/tavily.py    # NEW — parse_tavily_results() + TavilySource
/pipeline/run.py               # MODIFY — add TavilySource to SOURCES
/tests/test_tavily.py          # NEW — offline parser + missing-key tests
/src/lib/types.ts              # MODIFY — add "news" to Item.source union
/src/components/SourceBadge.tsx# MODIFY — add news -> "NEWS" label
/.env, /.env.example           # MODIFY — add TAVILY_API_KEY
/README.md                     # MODIFY — env table row
/.github/workflows/daily-digest.yml  # MODIFY — pass TAVILY_API_KEY secret
```

---

### Task 1: Tavily parser (pure, offline)

**Files:**
- Create: `pipeline/sources/tavily.py`
- Create: `tests/test_tavily.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tavily.py`:

```python
from pipeline.sources.tavily import parse_tavily_results

SAMPLE = {
    "results": [
        {
            "title": "Claude gets a new feature",
            "url": "https://www.anthropic.com/news/claude-new-feature",
            "content": "Anthropic announced a new capability for Claude today.",
            "score": 0.9,
            "published_date": "2026-06-04T10:00:00Z",
        },
        {
            "title": "OpenAI ships something",
            "url": "https://openai.com/blog/something",
            "content": "Details about the release.",
            "score": 0.8,
            "published_date": "2026-06-05T08:00:00Z",
        },
    ]
}


def test_parse_maps_fields_to_items():
    items = parse_tavily_results(SAMPLE)
    assert len(items) == 2
    it = items[0]
    assert it.source == "news"
    assert it.title == "Claude gets a new feature"
    assert it.url == "https://www.anthropic.com/news/claude-new-feature"
    assert it.abstract == "Anthropic announced a new capability for Claude today."
    assert it.authors == []
    assert it.published_at == "2026-06-04T10:00:00Z"
    assert it.has_code is False
    assert it.code_url is None


def test_parse_id_is_stable_and_prefixed():
    items = parse_tavily_results(SAMPLE)
    first = items[0].id
    again = parse_tavily_results(SAMPLE)[0].id
    assert first == again  # deterministic
    assert first.startswith("news:")
    assert len(first) == len("news:") + 12  # 12 hex chars


def test_parse_missing_results_key_returns_empty():
    assert parse_tavily_results({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tavily.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.sources.tavily).

- [ ] **Step 3: Write the parser**

Create `pipeline/sources/tavily.py`:

```python
from __future__ import annotations

import hashlib

from pipeline.models import Item


def _news_id(url: str) -> str:
    return "news:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def parse_tavily_results(payload: dict) -> list[Item]:
    results = payload.get("results") or []
    items: list[Item] = []
    for r in results:
        url = r.get("url", "")
        items.append(
            Item(
                id=_news_id(url),
                source="news",
                title=r.get("title", ""),
                url=url,
                abstract=r.get("content", ""),
                authors=[],
                published_at=r.get("published_date", ""),
                has_code=False,
                code_url=None,
            )
        )
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tavily.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/tavily.py tests/test_tavily.py
git commit -m "feat(pipeline): add Tavily news result parser"
```

---

### Task 2: TavilySource (networked, with retry + missing-key guard)

**Files:**
- Modify: `pipeline/sources/tavily.py`
- Modify: `tests/test_tavily.py`

- [ ] **Step 1: Write the failing test (no network: missing key returns [])**

Append to `tests/test_tavily.py`:

```python
from pipeline.sources.tavily import TavilySource


def test_fetch_returns_empty_when_key_missing(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert TavilySource().fetch() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tavily.py::test_fetch_returns_empty_when_key_missing -v`
Expected: FAIL (cannot import name 'TavilySource').

- [ ] **Step 3: Add the source class**

Append to `pipeline/sources/tavily.py`:

```python
import logging
import os
import time

import httpx

log = logging.getLogger("throughline")

TAVILY_API = "https://api.tavily.com/search"
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
QUERY = "latest artificial intelligence and machine learning developments"
ALLOWED_DOMAINS = [
    "anthropic.com",
    "openai.com",
    "deepmind.google",
    "ai.meta.com",
    "huggingface.co",
    "mistral.ai",
    "ai.googleblog.com",
    "blog.google",
]


class TavilySource:
    name = "news"

    def __init__(
        self, max_results: int = 10, days: int = 2, timeout: float = 30.0, retries: int = 3
    ) -> None:
        self.max_results = max_results
        self.days = days
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            log.warning("TAVILY_API_KEY not set; skipping news source")
            return []
        body = {
            "query": QUERY,
            "topic": "news",
            "days": self.days,
            "max_results": self.max_results,
            "include_domains": ALLOWED_DOMAINS,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "User-Agent": USER_AGENT,
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.post(
                    TAVILY_API, json=body, headers=headers, timeout=self.timeout
                )
                resp.raise_for_status()
                return parse_tavily_results(resp.json())
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                transient = exc.response.status_code in (429, 500, 503)
                if transient and attempt < self.retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
```

Note: keep the existing `from __future__`, `hashlib`, `Item` import and the parser at the
top of the file; add these imports near the top (after `import hashlib`) and the class below
the parser. Final import order at top of file:
```python
from __future__ import annotations

import hashlib
import logging
import os
import time

import httpx

from pipeline.models import Item
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tavily.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/tavily.py tests/test_tavily.py
git commit -m "feat(pipeline): add TavilySource with retry and missing-key guard"
```

---

### Task 3: Wire into run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Add the import and register the source**

In `pipeline/run.py`, change the import block:

```python
from pipeline.sources.arxiv import ArxivSource
from pipeline.sources.tavily import TavilySource
```

and change the `SOURCES` line:

```python
SOURCES = [ArxivSource(), TavilySource()]
```

- [ ] **Step 2: Verify dry-run still works and tolerates a missing key**

Run (without TAVILY_API_KEY exported): `.venv/bin/python -m pipeline.run --dry-run`
Expected: logs `source news: 0 items` OR a warning `TAVILY_API_KEY not set; skipping news source`, and the run completes without error (arXiv may also be empty if rate-limited — fine).

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (7 total).

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): register Tavily news source in pipeline run"
```

---

### Task 4: Frontend — news badge

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/components/SourceBadge.tsx`

- [ ] **Step 1: Extend the source union**

In `src/lib/types.ts`, change the `source` field of `Item`:

```ts
  source: "arxiv" | "hackernews" | "github" | "news";
```

- [ ] **Step 2: Add the badge label**

In `src/components/SourceBadge.tsx`, change the `LABELS` map:

```tsx
const LABELS: Record<Item["source"], string> = {
  arxiv: "arXiv",
  hackernews: "HN",
  github: "GitHub",
  news: "NEWS",
};
```

- [ ] **Step 3: Verify typecheck + build**

Run: `npx tsc --noEmit`
Expected: no errors.
Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 4: Commit**

```bash
git add src/lib/types.ts src/components/SourceBadge.tsx
git commit -m "feat(web): add news source badge"
```

---

### Task 5: Config — env + README + CI secret wiring

**Files:**
- Modify: `.env.example`, `.env`, `README.md`, `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Add to `.env.example`**

Add a section to `.env.example`:

```
# --- Tavily (AI/ML news source) ---
TAVILY_API_KEY=
```

- [ ] **Step 2: Add to `.env`**

Add the same key to `.env` (gitignored; user pastes the real value):

```
# --- Tavily (AI/ML news source) ---
TAVILY_API_KEY=
```

- [ ] **Step 3: README env table**

In `README.md`, add a row to the environment-variables table:

```
| `TAVILY_API_KEY` | AI/ML news source (Tavily Search) | news |
```

- [ ] **Step 4: Pass the secret in CI**

In `.github/workflows/daily-digest.yml`, give the "Run pipeline" step the secret:

```yaml
      - name: Run pipeline
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        run: python -m pipeline.run
```

- [ ] **Step 5: Commit (env.example, README, workflow — NOT .env)**

```bash
git add .env.example README.md .github/workflows/daily-digest.yml
git commit -m "chore: wire TAVILY_API_KEY into env template, README, and CI"
```

- [ ] **Step 6: Push**

```bash
git push
```

---

### Task 6: Live verification

**Files:** none

- [ ] **Step 1: Confirm the key is in `.env`** (user-provided). Then run live:

Run: `set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --dry-run`
Expected: logs `source news: N items` with N >= 0; printed JSON includes objects with
`"source": "news"` (assuming the allowlisted domains published in the last 2 days).

- [ ] **Step 2: Add the GitHub Actions secret**

Add repository secret `TAVILY_API_KEY` (Settings → Secrets and variables → Actions →
Secrets → New repository secret). Required so the daily Action can fetch news.

- [ ] **Step 3 (optional): local visual check**

Seed a digest including a news item, `npm run dev`, confirm the `NEWS` badge renders, then
restore the real digest (do not commit seeded content).

---

## Self-review notes

- **Spec coverage:** parser (T1), networked source + retry + missing-key guard (T2),
  run.py registration (T3), frontend union + badge (T4), env/README/CI (T5), live check +
  CI secret (T6). All spec sections mapped.
- **Type consistency:** `parse_tavily_results(payload: dict) -> list[Item]` and
  `TavilySource.fetch() -> list[Item]` match the spec and the existing `Source` protocol.
  `Item` fields used match `pipeline/models.py`. Frontend `"news"` added in both the TS
  union and the badge `Record`, so the exhaustive `Record<Item["source"], string>` stays
  valid (a missing key would be a compile error — covered by T4 typecheck).
- **Placeholder scan:** none. `TAVILY_API_KEY=` blank in env files is intentional (secret
  filled by user), not a plan placeholder.
- **No backdating / no Claude trailer** on every commit.
```
