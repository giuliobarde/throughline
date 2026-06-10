# Search + Blog Source — Design Spec

**Date:** 2026-06-10
**Status:** Approved
**Builds on:** `2026-06-09-social-board-design.md` (social board, shipped)

## Summary

Two additions to the Throughline board:

1. **Board-wide search** — a nav search box (plain GET form) feeding a server-rendered `/search` page that ranks matches across the latest item pool and topic labels.
2. **`blog` source** — first-party vendor posts (Anthropic, OpenAI, DeepMind, Google AI, Meta, Hugging Face, Mistral) ingested daily with full pipeline treatment (embed → cluster → summarize → rank), shown with a violet BLOG badge.

## Part 1 — Board-wide search

### Nav entry

`src/app/layout.tsx` nav gains a compact form (no client JS):

```html
<form action="/search"><input name="q" placeholder="search" /></form>
```

Styled to match nav (mono, dark, subtle border). Width ~7rem, grows on focus (sm+ screens); included on mobile.

### Search engine (`src/lib/search.ts`, pure, vitest-tested)

```ts
export type SearchResults = { items: FeedItem[]; topics: Topic[] };
export function searchItems(items: FeedItem[], topics: Topic[], q: string, limit = 20): SearchResults
```

- Tokenize `q` lowercase on whitespace; ignore empty/whitespace-only queries (return empty results).
- Item score = sum over terms: title substring match ×3, topic tag/label match ×2, summary/abstract match ×1. Items with score 0 dropped; sort score desc, tie → newer `published_at` first; cap `limit`.
- Matching topics: topic whose `label` or `tag` contains any term.
- Module stays client-safe/pure (no fs/server-only) per repo convention, though it is currently consumed server-side only.

### `/search` page (`src/app/search/page.tsx`, dynamic)

- Reads `searchParams.q` (Next 16: `searchParams` is a Promise — await it).
- Pool: `getRecentDigests(7)` → `mergeDigests`; topics from latest digest; votes via `getVoteCounts()`.
- Renders: heading `results for “q”`, matching t/ chips (links), then `PostCard` list (`initialNet` from votes). Empty `q` → prompt to type something; no matches → "nothing found" state.
- No tabs/infinite scroll/density on search results (YAGNI).

## Part 2 — `blog` pipeline source

### Feed reality (probed 2026-06-10)

Live RSS:
- OpenAI — `https://openai.com/news/rss.xml`
- Google DeepMind — `https://deepmind.google/blog/rss.xml`
- Google AI — `https://blog.google/technology/ai/rss/`
- Hugging Face — `https://huggingface.co/blog/feed.xml`

No RSS exists (404/403 on all known candidates): Anthropic news, Claude blog, Meta AI, Mistral. These are covered by a **targeted Tavily query** instead (Tavily client pattern + `TAVILY_API_KEY` already in pipeline/CI):
- `include_domains = ["anthropic.com", "claude.com", "ai.meta.com", "mistral.ai"]`
- query: `"announcement OR release OR research update"`, `topic="news"`, `days=7`.

### `pipeline/sources/blogs.py`

- `FEEDS: list[tuple[str, str]]` — (publisher name, feed URL) for the four live feeds.
- `parse_feed(publisher: str, raw: str) -> list[Item]` — pure, feedparser on the raw XML string; per entry:
  - `id = "blog:" + sha1(link)[:12]` (same scheme as tavily `_news_id`)
  - `source = "blog"`, `title`, `url = link`
  - `abstract` = entry summary/description with HTML tags stripped (regex `<[^>]+>` → ""), whitespace collapsed, truncated ~500 chars
  - `authors = [publisher]`
  - `published_at` = ISO 8601 from `published_parsed`/`updated_parsed` (else "")
  - `has_code = False`, `code_url = None`
- `filter_window(items, days=7)` — keep items with parseable `published_at` within the last 7 days (unparseable → dropped); cap 5 per publisher.
- `fetch_tavily_blogs() -> list[Item]` — targeted Tavily call described above; items get the same `blog:`-hashed ids, `source="blog"`, `authors=[domain]`. Missing `TAVILY_API_KEY` or HTTP error → `[]` (logged), matching tavily.py behavior.
- `class BlogSource: name = "blog"; fetch()` — RSS feeds (each in try/except, dead feed logged + skipped) + Tavily fallback, window-filtered, deduped by id.
- feedparser 6.0.11 already pinned in requirements.txt — no new deps.

### Pipeline integration

- `run.py`: add `BlogSource()` to `SOURCES`.
- `rank.py`: `SOURCE_WEIGHT["blog"] = 0.12` (first-party vendor posts rank between github .15 and hn/news .10 for cold-start).
- `models.py`: `Item.source` is plain `str` (verified) — no change needed.

### Frontend

- `src/lib/types.ts`: `source` union += `"blog"`.
- `SourceBadge.tsx`: label `BLOG`, color `text-violet-400`.
- No other UI changes — blog items flow through board, topics, search like any item.

## Error handling

- Per-feed fetch/parse failures: log + skip, never fail the run (matches existing fault-tolerant write path).
- Tavily fallback degrades to `[]` without key.
- Search: empty/garbage query → empty state; pool load failures already null-safe.

## Testing

- **pytest** (`tests/test_blogs.py`): `parse_feed` against an inline RSS fixture (title/url/id/abstract-strip/date), `filter_window` (old item dropped, cap respected), BlogSource registered in run.py SOURCES, Tavily fallback returns [] without key.
- **vitest** (`tests/web/search.test.ts`): scoring order (title beats abstract), multi-term, topic matching, empty query, limit, tie-break by recency.
- **Live:** `/search?q=` flows; after next pipeline run, BLOG badge renders.

## Out of scope

Fuzzy/typo matching, search-as-you-type, archive-wide (older than 7 digests) search, HTML scraping of no-RSS vendors.
