# Phase 5 — HN + GitHub Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hacker News (Algolia) and GitHub trending (REST Search) pipeline sources that fold AI/ML discussion and trending repos into the daily digest.

**Architecture:** Two new source modules (`pipeline/sources/hackernews.py`, `pipeline/sources/github.py`) follow the established arxiv/tavily pattern: a pure parser plus a thin networked class with 429/500/503 retry. Both normalize to the existing `Item` dataclass and are registered in `run.py`'s `SOURCES`. No frontend or digest-format change.

**Tech Stack:** Python 3.12 (`httpx`, `pytest`), HN Algolia API, GitHub REST Search API.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/sources/hackernews.py   # NEW — parse_hn_results, filter_ai_ml, HackerNewsSource
/pipeline/sources/github.py       # NEW — parse_github_results, GitHubSource
/pipeline/run.py                  # MODIFY — register both sources
/tests/test_hackernews.py         # NEW
/tests/test_github.py             # NEW
/.env.example                     # MODIFY — add GITHUB_TOKEN
/README.md                        # MODIFY — env table row
/.github/workflows/daily-digest.yml  # MODIFY — pass GITHUB_TOKEN to pipeline step
```

---

### Task 1: HN parser + AI/ML filter (pure, offline)

**Files:**
- Create: `pipeline/sources/hackernews.py`
- Create: `tests/test_hackernews.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hackernews.py`:

```python
from pipeline.sources.hackernews import parse_hn_results, filter_ai_ml

SAMPLE = {
    "hits": [
        {
            "objectID": "111",
            "title": "Show HN: A new LLM inference engine",
            "url": "https://github.com/acme/fast-llm",
            "author": "alice",
            "points": 250,
            "created_at": "2026-06-05T09:00:00.000Z",
        },
        {
            "objectID": "222",
            "title": "My thoughts on remote work",
            "url": "https://example.com/remote",
            "author": "bob",
            "points": 300,
            "created_at": "2026-06-05T08:00:00.000Z",
        },
        {
            "objectID": "333",
            "title": "Ask HN: best transformer tutorials?",
            "url": None,
            "author": "carol",
            "points": 120,
            "created_at": "2026-06-05T07:00:00.000Z",
        },
    ]
}


def test_parse_maps_fields_and_code_detection():
    items = parse_hn_results(SAMPLE)
    assert len(items) == 3
    it = items[0]
    assert it.id == "hn:111"
    assert it.source == "hackernews"
    assert it.title == "Show HN: A new LLM inference engine"
    assert it.url == "https://github.com/acme/fast-llm"
    assert it.authors == ["alice"]
    assert it.published_at == "2026-06-05T09:00:00.000Z"
    assert it.has_code is True  # github.com url
    assert it.code_url == "https://github.com/acme/fast-llm"


def test_parse_uses_hn_permalink_when_url_missing():
    items = parse_hn_results(SAMPLE)
    carol = [i for i in items if i.id == "hn:333"][0]
    assert carol.url == "https://news.ycombinator.com/item?id=333"
    assert carol.has_code is False
    assert carol.code_url is None


def test_filter_keeps_only_ai_ml_titles():
    items = filter_ai_ml(parse_hn_results(SAMPLE))
    ids = {i.id for i in items}
    assert "hn:111" in ids  # "LLM"
    assert "hn:333" in ids  # "transformer"
    assert "hn:222" not in ids  # remote work -> dropped


def test_parse_missing_hits_returns_empty():
    assert parse_hn_results({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hackernews.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.sources.hackernews).

- [ ] **Step 3: Write the parser + filter (no networked class yet)**

Create `pipeline/sources/hackernews.py`:

```python
from __future__ import annotations

from pipeline.models import Item

ALGOLIA_API = "https://hn.algolia.com/api/v1/search_by_date"
MIN_POINTS = 100
WINDOW_HOURS = 48
KEYWORDS = [
    "llm",
    "gpt",
    "transformer",
    "neural",
    "diffusion",
    "machine learning",
    "deep learning",
    "ai model",
    "open source model",
    "fine-tun",
    "rag",
    "agent",
    "inference",
    "pytorch",
    "hugging face",
    "anthropic",
    "openai",
]


def parse_hn_results(payload: dict) -> list[Item]:
    hits = payload.get("hits") or []
    items: list[Item] = []
    for h in hits:
        object_id = str(h.get("objectID", ""))
        url = h.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        has_code = "github.com" in url
        author = h.get("author")
        items.append(
            Item(
                id=f"hn:{object_id}",
                source="hackernews",
                title=h.get("title", ""),
                url=url,
                abstract="",
                authors=[author] if author else [],
                published_at=h.get("created_at", ""),
                has_code=has_code,
                code_url=url if has_code else None,
            )
        )
    return items


def filter_ai_ml(items: list[Item]) -> list[Item]:
    return [
        it for it in items if any(kw in it.title.lower() for kw in KEYWORDS)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hackernews.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/hackernews.py tests/test_hackernews.py
git commit -m "feat(pipeline): add Hacker News parser and AI/ML title filter"
```

---

### Task 2: HackerNewsSource (networked, retry)

**Files:**
- Modify: `pipeline/sources/hackernews.py`
- Modify: `tests/test_hackernews.py`

- [ ] **Step 1: Write the failing test (network-free: monkeypatch httpx.get)**

Append to `tests/test_hackernews.py`:

```python
import httpx

from pipeline.sources.hackernews import HackerNewsSource


def test_fetch_parses_and_filters(monkeypatch):
    def fake_get(url, params=None, timeout=None, headers=None):
        return httpx.Response(
            200,
            json=SAMPLE,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    items = HackerNewsSource().fetch()
    ids = {i.id for i in items}
    assert ids == {"hn:111", "hn:333"}  # off-topic 222 filtered out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hackernews.py::test_fetch_parses_and_filters -v`
Expected: FAIL (cannot import name 'HackerNewsSource').

- [ ] **Step 3: Add the source class**

Append to `pipeline/sources/hackernews.py` (and add the imports `time`, `httpx` to the top
import block so it reads):

```python
from __future__ import annotations

import time

import httpx

from pipeline.models import Item
```

Class (append at end of file):

```python
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"


class HackerNewsSource:
    name = "hackernews"

    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        since = int(time.time()) - WINDOW_HOURS * 3600
        params = {
            "tags": "story",
            "numericFilters": f"points>={MIN_POINTS},created_at_i>={since}",
            "hitsPerPage": "50",
        }
        headers = {"User-Agent": USER_AGENT}
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    ALGOLIA_API, params=params, timeout=self.timeout, headers=headers
                )
                resp.raise_for_status()
                return filter_ai_ml(parse_hn_results(resp.json()))
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

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hackernews.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/hackernews.py tests/test_hackernews.py
git commit -m "feat(pipeline): add HackerNewsSource with retry"
```

---

### Task 3: GitHub parser (pure, offline)

**Files:**
- Create: `pipeline/sources/github.py`
- Create: `tests/test_github.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_github.py`:

```python
from pipeline.sources.github import parse_github_results

SAMPLE = {
    "items": [
        {
            "full_name": "acme/awesome-llm",
            "html_url": "https://github.com/acme/awesome-llm",
            "description": "A fast LLM training framework.",
            "owner": {"login": "acme"},
            "stargazers_count": 1200,
            "created_at": "2026-06-01T00:00:00Z",
        },
        {
            "full_name": "beta/no-desc",
            "html_url": "https://github.com/beta/no-desc",
            "description": None,
            "owner": {"login": "beta"},
            "stargazers_count": 800,
            "created_at": "2026-06-02T00:00:00Z",
        },
    ]
}


def test_parse_maps_repo_fields():
    items = parse_github_results(SAMPLE)
    assert len(items) == 2
    it = items[0]
    assert it.id == "gh:acme/awesome-llm"
    assert it.source == "github"
    assert it.title == "acme/awesome-llm"
    assert it.url == "https://github.com/acme/awesome-llm"
    assert it.abstract == "A fast LLM training framework."
    assert it.authors == ["acme"]
    assert it.published_at == "2026-06-01T00:00:00Z"
    assert it.has_code is True
    assert it.code_url == "https://github.com/acme/awesome-llm"


def test_parse_handles_null_description():
    items = parse_github_results(SAMPLE)
    assert items[1].abstract == ""


def test_parse_missing_items_returns_empty():
    assert parse_github_results({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_github.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.sources.github).

- [ ] **Step 3: Write the parser**

Create `pipeline/sources/github.py`:

```python
from __future__ import annotations

from pipeline.models import Item

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
WINDOW_DAYS = 7


def parse_github_results(payload: dict) -> list[Item]:
    repos = payload.get("items") or []
    items: list[Item] = []
    for r in repos:
        html_url = r.get("html_url", "")
        owner = (r.get("owner") or {}).get("login")
        items.append(
            Item(
                id=f"gh:{r.get('full_name', '')}",
                source="github",
                title=r.get("full_name", ""),
                url=html_url,
                abstract=r.get("description") or "",
                authors=[owner] if owner else [],
                published_at=r.get("created_at", ""),
                has_code=True,
                code_url=html_url,
            )
        )
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_github.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/github.py tests/test_github.py
git commit -m "feat(pipeline): add GitHub repo search parser"
```

---

### Task 4: GitHubSource (networked, optional auth, retry)

**Files:**
- Modify: `pipeline/sources/github.py`
- Modify: `tests/test_github.py`

- [ ] **Step 1: Write the failing test (network-free: monkeypatch httpx.get)**

Append to `tests/test_github.py`:

```python
import httpx

from pipeline.sources.github import GitHubSource


def test_fetch_parses_results(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["params"] = params
        captured["headers"] = headers
        return httpx.Response(200, json=SAMPLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    items = GitHubSource().fetch()
    assert {i.id for i in items} == {"gh:acme/awesome-llm", "gh:beta/no-desc"}
    assert captured["params"]["sort"] == "stars"
    assert "Authorization" not in captured["headers"]  # no token -> no auth header


def test_fetch_adds_auth_header_when_token_set(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["headers"] = headers
        return httpx.Response(200, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setenv("GITHUB_TOKEN", "ghtok123")
    GitHubSource().fetch()
    assert captured["headers"]["Authorization"] == "Bearer ghtok123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_github.py::test_fetch_parses_results -v`
Expected: FAIL (cannot import name 'GitHubSource').

- [ ] **Step 3: Add the source class**

Update the top import block of `pipeline/sources/github.py` to:

```python
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import httpx

from pipeline.models import Item
```

Append the class at the end of the file:

```python
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"


class GitHubSource:
    name = "github"

    def __init__(self, per_page: int = 10, timeout: float = 30.0, retries: int = 3) -> None:
        self.per_page = per_page
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        since = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
        params = {
            "q": f"machine learning created:>={since}",
            "sort": "stars",
            "order": "desc",
            "per_page": str(self.per_page),
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    GITHUB_SEARCH_API, params=params, timeout=self.timeout, headers=headers
                )
                resp.raise_for_status()
                return parse_github_results(resp.json())
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

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_github.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/github.py tests/test_github.py
git commit -m "feat(pipeline): add GitHubSource with optional token auth and retry"
```

---

### Task 5: Register both sources in run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Update imports and SOURCES**

In `pipeline/run.py`, change the source imports to:

```python
from pipeline.sources.arxiv import ArxivSource
from pipeline.sources.github import GitHubSource
from pipeline.sources.hackernews import HackerNewsSource
from pipeline.sources.tavily import TavilySource
```

and the `SOURCES` line to:

```python
SOURCES = [ArxivSource(), TavilySource(), HackerNewsSource(), GitHubSource()]
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (19 total).

- [ ] **Step 3: Live dry-run (network; tolerant of failures)**

Run: `.venv/bin/python -m pipeline.run --dry-run`
Expected: logs a `source hackernews: N items` and `source github: N items` line; run completes.
Any source that fails (rate limit / throttle) logs and is skipped — acceptable.

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): register Hacker News and GitHub sources"
```

---

### Task 6: Config — GITHUB_TOKEN in env template, README, CI

**Files:**
- Modify: `.env.example`, `README.md`, `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Add to `.env.example`**

Append to `.env.example`:

```
# --- GitHub (trending repos source; optional locally, raises rate limit) ---
GITHUB_TOKEN=
```

- [ ] **Step 2: README env table**

In `README.md`, add a row:

```
| `GITHUB_TOKEN` | GitHub trending source rate limit (auto-provided in CI) | news |
```

- [ ] **Step 3: Pass the token to the pipeline step in CI**

In `.github/workflows/daily-digest.yml`, extend the "Run pipeline" step's `env` block so it
includes the GitHub token alongside the Tavily key:

```yaml
      - name: Run pipeline
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python -m pipeline.run
```

(`secrets.GITHUB_TOKEN` is auto-provided by Actions; no manual secret needed.)

- [ ] **Step 4: Commit + push**

```bash
git add .env.example README.md .github/workflows/daily-digest.yml
git commit -m "chore: wire GITHUB_TOKEN into env template, README, and CI"
git push
```

---

### Task 7: Live verification

**Files:** none

- [ ] **Step 1: Live HN fetch**

Run:
```bash
.venv/bin/python -c "from pipeline.sources.hackernews import HackerNewsSource; r=HackerNewsSource().fetch(); print('hn', len(r)); [print(' ', i.title[:60]) for i in r[:5]]"
```
Expected: prints recent AI/ML HN stories (count may be small or 0 depending on the last 48h
at >=100 pts — that is valid).

- [ ] **Step 2: Live GitHub fetch**

Run:
```bash
.venv/bin/python -c "from pipeline.sources.github import GitHubSource; r=GitHubSource().fetch(); print('gh', len(r)); [print(' ', i.title, '-', i.abstract[:40]) for i in r[:5]]"
```
Expected: prints up to 10 recent ML repos by stars. (Unauthenticated search may hit a rate
limit; if so, retry after a minute or set GITHUB_TOKEN locally.)

- [ ] **Step 3 (optional): visual check**

Run the pipeline live to write a digest including HN/GitHub items, `npm run dev`, confirm
`HN` and `GitHub` badges render, then restore the real digest (do not commit seeded content).

---

## Self-review notes

- **Spec coverage:** HN parser+filter (T1), HackerNewsSource+retry (T2), GitHub parser (T3),
  GitHubSource+optional-auth+retry (T4), run.py registration (T5), env/README/CI for
  GITHUB_TOKEN (T6), live verification (T7). All spec sections mapped.
- **Type consistency:** all parsers return `list[Item]`; `*.fetch() -> list[Item]`; fields
  match `pipeline/models.py`. Module-level constants (`ALGOLIA_API`, `MIN_POINTS`,
  `WINDOW_HOURS`, `KEYWORDS`, `GITHUB_SEARCH_API`, `WINDOW_DAYS`) referenced consistently.
  `USER_AGENT` defined once per module.
- **Placeholder scan:** none. Blank `GITHUB_TOKEN=` in env is intentional (optional secret).
- **Test count math:** existing 9 + HN 5 + GitHub 5 = 19 (matches T5 Step 2).
- **No frontend change:** `Item["source"]` already has `"hackernews"`/`"github"`; badges exist.
- **No backdating / no Claude trailer** on every commit.
- **Import-block note:** Tasks 2 and 4 instruct replacing the module's top import block (not
  duplicating `from __future__`), so each file ends with a single, correct import section.
```
