# Phase 5 — Hacker News + GitHub Sources — Design Spec

**Date:** 2026-06-05
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

Two new pipeline sources — Hacker News (Algolia) and GitHub trending repos (REST Search) —
that fold AI/ML discussion and trending code into the existing daily digest, alongside
arXiv and Tavily news.

## Decisions locked (2026-06-05)

| Decision | Choice |
|----------|--------|
| HN filter | AI/ML keywords, min **100 points**, last **48h** |
| GitHub scope | free-text "machine learning", **created last 7d**, sort by stars, any language, top ~10 |
| GitHub auth in CI | REST API over `httpx` with the Actions-provided `GITHUB_TOKEN` (the MCP connector is NOT available in CI) |
| Frontend | no change — `HN`/`GitHub` badges + `hackernews`/`github` union members already exist |

## Component: `pipeline/sources/hackernews.py`

Mirrors the arxiv/tavily shape: pure parser + thin networked class with 429/500/503 retry.

```
ALGOLIA_API = "https://hn.algolia.com/api/v1/search_by_date"
MIN_POINTS = 100
WINDOW_HOURS = 48
KEYWORDS = [
    "llm", "gpt", "transformer", "neural", "diffusion", "machine learning",
    "deep learning", "ai model", "open source model", "fine-tun", "rag",
    "agent", "inference", "pytorch", "hugging face", "anthropic", "openai",
]
```

### `parse_hn_results(payload: dict) -> list[Item]` (pure, unit-tested)

For each `hit` in `payload["hits"]`:
- `objectID` → `id = "hn:" + objectID`
- `source = "hackernews"`
- `title = hit.get("title", "")`
- `url = hit.get("url") or f"https://news.ycombinator.com/item?id={objectID}"`
- `abstract = ""` (HN stories carry no abstract)
- `authors = [hit["author"]]` when present, else `[]`
- `published_at = hit.get("created_at", "")` (Algolia already returns ISO 8601)
- `has_code = "github.com" in url`; `code_url = url if has_code else None`

### Keyword filter

`parse_hn_results` returns all parsed hits. A separate pure helper
`filter_ai_ml(items: list[Item]) -> list[Item]` keeps items whose **title** (lowercased)
contains any `KEYWORDS` substring. `HackerNewsSource.fetch()` applies it after parsing.

### `HackerNewsSource.fetch() -> list[Item]`

- Compute `since = int(time.time()) - WINDOW_HOURS*3600`.
- GET `ALGOLIA_API` params: `tags=story`,
  `numericFilters=f"points>={MIN_POINTS},created_at_i>={since}"`, `hitsPerPage=50`.
- Retry on 429/500/503 with backoff (same as ArxivSource), `User-Agent` set.
- `raise_for_status()` → `filter_ai_ml(parse_hn_results(resp.json()))`. No auth.

## Component: `pipeline/sources/github.py`

```
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
WINDOW_DAYS = 7
```

### `parse_github_results(payload: dict) -> list[Item]` (pure, unit-tested)

For each `repo` in `payload["items"]`:
- `id = "gh:" + repo["full_name"]`
- `source = "github"`
- `title = repo["full_name"]`
- `url = repo["html_url"]`
- `abstract = repo.get("description") or ""`
- `authors = [repo["owner"]["login"]]` when present, else `[]`
- `published_at = repo.get("created_at", "")` (ISO 8601)
- `has_code = True`; `code_url = repo["html_url"]`

### `GitHubSource.fetch() -> list[Item]`

- `since = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()`.
- GET `GITHUB_SEARCH_API` params: `q=f"machine learning created:>={since}"`,
  `sort="stars"`, `order="desc"`, `per_page=10`.
- Headers: `Accept: application/vnd.github+json`, `User-Agent`, and
  `Authorization: Bearer <GITHUB_TOKEN>` **only if** the env var is set (unauth still works
  at a lower rate limit).
- Retry on 429/500/503 with backoff. `raise_for_status()` → `parse_github_results(resp.json())`.

## Integration

- Add `HackerNewsSource()` and `GitHubSource()` to `SOURCES` in `pipeline/run.py`.
- Existing `collect()` wraps each source in try/except (one failing source never kills the
  run); `dedupe()` keys on `f"{source}:{id}"`. No digest/`index.json` format change.

## Frontend

No change. `Item["source"]` already includes `"hackernews"` and `"github"`; `SourceBadge`
already maps them to `HN` and `GitHub`. `ItemCard` handles empty `authors`/`abstract`.

## Configuration

- `GITHUB_TOKEN`: add to `.env.example` (blank) and to the workflow's "Run pipeline" step
  env as `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (auto-provided by Actions, no manual
  secret needed). Local use optional (raises personal rate limit).
- HN needs no configuration.
- README env table: add `GITHUB_TOKEN` row.

## Testing (TDD, all offline)

`tests/test_hackernews.py`:
1. `parse_hn_results` on a fixed payload → id `hn:` prefix, `source="hackernews"`, author
   mapping, `published_at` from `created_at`, missing-url → HN permalink fallback,
   `has_code`/`code_url` true when url is github.com.
2. `filter_ai_ml` keeps only AI/ML-titled items, drops off-topic ones.
3. `parse_hn_results({})` → `[]`.

`tests/test_github.py`:
1. `parse_github_results` on a fixed payload → id `gh:` + full_name, `source="github"`,
   `has_code is True`, `code_url == html_url`, description→abstract, owner→authors.
2. `parse_github_results({})` → `[]`.

## Error handling

- Transient HTTP (429/500/503) → retry w/ backoff, then raise; `collect()` catches + continues.
- Malformed payload (missing `hits`/`items`) → parser returns `[]`.
- GitHub unauthenticated → still works (lower rate); token only raises the limit.

## Out of scope (YAGNI)

- No `points`/`stars` field on `Item` (ranking signal deferred to Phase 6/8; add then).
- No multi-topic GitHub query fan-out (single free-text query is enough).
- No HN comment/Ask/Show filtering beyond `tags=story`.
- No frontend changes.
