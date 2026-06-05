# Tavily AI-News Source — Design Spec

**Date:** 2026-06-05
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

A new pipeline source that pulls recent **AI/ML industry news** via the Tavily Search
API, restricted to a curated domain allowlist (Anthropic, OpenAI, etc.), and folds the
results into the existing daily digest. Keeps the digest current on the state of the field,
alongside arXiv papers (and later HN + GitHub).

## Decisions locked (2026-06-05)

| Decision | Choice |
|----------|--------|
| Content focus | AI/ML industry news only (curated allowlist) |
| Fetch mechanism | Tavily **Search** API, `topic="news"`, `include_domains` allowlist |
| Presentation | Same digest list, distinct `news` source badge (no separate section) |

## Component: `pipeline/sources/tavily.py`

Mirrors the existing source interface (`fetch() -> list[Item]`) and the arXiv module's
shape (pure parser + thin networked class with retry).

```
ALLOWED_DOMAINS = [
    "anthropic.com", "openai.com", "deepmind.google", "ai.meta.com",
    "huggingface.co", "mistral.ai", "ai.googleblog.com", "blog.google",
]
TAVILY_API = "https://api.tavily.com/search"
QUERY = "latest artificial intelligence and machine learning developments"
```

### `parse_tavily_results(payload: dict) -> list[Item]` (pure, unit-tested)

For each `result` in `payload["results"]`:
- `id = "news:" + sha1(url).hexdigest()[:12]` — stable across reruns, dedupes cleanly.
- `source = "news"`
- `title = result["title"]`
- `url = result["url"]`
- `abstract = result.get("content", "")` (Tavily snippet)
- `authors = []`
- `published_at = result.get("published_date", "")`
- `has_code = False`, `code_url = None`

### `TavilySource.fetch() -> list[Item]`

- Reads `TAVILY_API_KEY` from env. If missing → log warning, return `[]` (fault-tolerant).
- POST `TAVILY_API`, header `Authorization: Bearer <key>`, JSON body:
  `{"query": QUERY, "topic": "news", "days": 2, "max_results": 10, "include_domains": ALLOWED_DOMAINS}`.
- Retry on 429/500/503 with polite backoff (same pattern as `ArxivSource`), `User-Agent` set.
- `resp.raise_for_status()` then `return parse_tavily_results(resp.json())`.

## Integration

- Add `TavilySource()` to `SOURCES` in `pipeline/run.py`. Existing `collect()` already
  wraps each source in try/except (one failing source never kills the run) and `dedupe()`
  keys on `f"{source}:{id}"`.
- No change to digest JSON / `index.json` format — news items are ordinary `Item`s.

## Frontend

- Extend the `Item["source"]` union in `src/lib/types.ts` with `"news"`.
- Add `news: "NEWS"` to the `LABELS` map in `src/components/SourceBadge.tsx`.
- `ItemCard` already handles empty `authors` and `has_code=false` — no other change.

## Configuration

- New env var `TAVILY_API_KEY`.
- Add to `.env` (real, gitignored) and `.env.example` (template).
- README env table: add row, Phase note "tech news".
- CI: store as a GitHub Actions **secret**; pass into the workflow's pipeline step via
  `env: TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}`. Vercel does not need it
  (pipeline-only; no client/runtime use).

## Testing (TDD)

`tests/test_tavily.py`, all offline:
1. `parse_tavily_results` on a fixed sample payload → correct count, `source="news"`,
   `published_at` mapped, `authors == []`, `has_code is False`.
2. `id` is stable + deterministic for a given URL (`news:` prefix + 12 hex chars).
3. `TavilySource().fetch()` with `TAVILY_API_KEY` unset → returns `[]` (no network call).

## Error handling

- Missing key → `[]`.
- Transient HTTP (429/500/503) → retry w/ backoff, then raise; `collect()` catches, logs,
  continues.
- Malformed payload (no `results`) → `parse_tavily_results` treats missing key as empty list.

## Out of scope (YAGNI)

- No broad/general tech news (AI/ML allowlist only).
- No separate news section or per-outlet badges (single `NEWS` badge).
- No Tavily Extract / full-text scraping (snippet from Search is enough).
- No Vercel env change (pipeline-only secret).
