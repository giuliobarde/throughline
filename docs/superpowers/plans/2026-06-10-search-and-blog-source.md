# Search + Blog Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Board-wide search (`/search` + nav box) and a `blog` pipeline source for first-party vendor posts (RSS where it exists, targeted Tavily for Anthropic/Claude/Meta/Mistral which have no feeds).

**Architecture:** Search is a pure scoring function (`src/lib/search.ts`, vitest-tested) consumed by a dynamic server page fed by existing loaders; the nav entry is a zero-JS GET form. The blog source follows the existing `Source` protocol (`pipeline/sources/blogs.py`): feedparser over four verified RSS feeds + a Tavily `include_domains` query for the no-RSS vendors, window-filtered and capped, flowing through the unchanged embed→cluster→summarize→rank path.

**Tech Stack:** Next.js 16 App Router · TS strict · Vitest · Python 3.12 · feedparser 6.0.11 (already pinned) · httpx · pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-search-and-blog-source-design.md`

**Commit rules (repo non-negotiable):** plain `git commit` (author preconfigured: Giulio), exact messages given, **NO Co-Authored-By / Claude trailer of any kind**.

**Key existing facts:**
- `src/lib/feed.ts` exports `FeedItem` (Item & `{digestDate: string}`), `itemKey`, `mergeDigests`; `src/lib/types.ts` exports `Topic = {tag, label, item_ids}` and the `Item.source` union `"arxiv" | "hackernews" | "github" | "news"`.
- `src/lib/content.ts` has `getRecentDigests(count=7)`; `src/lib/votes.ts` has `getVoteCounts()` (server-only).
- `PostCard` takes `{item: FeedItem, initialNet: number}`.
- Pipeline `Item.source` is plain `str` (`pipeline/models.py`) — no change needed there.
- `pipeline/run.py:23` → `SOURCES = [ArxivSource(), TavilySource(), HackerNewsSource(), GitHubSource()]`.
- `pipeline/rank.py:14` → `SOURCE_WEIGHT = {"github": 0.15, "hackernews": 0.10, "news": 0.10, "arxiv": 0.05}`.
- `pipeline/sources/tavily.py` exports `_iso_date(raw)` (RFC2822/ISO → ISO-8601 normalizer) — reuse it.
- Feed probe (2026-06-10): live RSS = OpenAI `https://openai.com/news/rss.xml`, DeepMind `https://deepmind.google/blog/rss.xml`, Google AI `https://blog.google/technology/ai/rss/`, Hugging Face `https://huggingface.co/blog/feed.xml`. All Anthropic/Claude/Meta/Mistral candidates 404/403.
- Python runs via `.venv/bin/python -m pytest -q` (currently 46 pass). Vitest via `npm test` (currently 15 pass).

---

### Task 1: Search engine (`src/lib/search.ts`)

Pure, client-safe module (no fs / server-only). TDD.

**Files:**
- Create: `src/lib/search.ts`
- Test: `tests/web/search.test.ts`

- [ ] **Step 1: Write failing tests** — create `tests/web/search.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { FeedItem } from "@/lib/feed";
import type { Item, Topic } from "@/lib/types";
import { searchItems } from "@/lib/search";

const base: Omit<Item, "id" | "source" | "title"> = {
  url: "https://example.com/x",
  abstract: "",
  authors: [],
  published_at: "2026-06-08T00:00:00+00:00",
  has_code: false,
  code_url: null,
};

function fi(id: string, title: string, extra: Partial<FeedItem> = {}): FeedItem {
  return { ...base, id, source: "arxiv", title, digestDate: "2026-06-08", ...extra };
}

const topics: Topic[] = [
  { tag: "agents", label: "Agent Safety", item_ids: [] },
  { tag: "training", label: "Training Efficiency", item_ids: [] },
];

describe("searchItems", () => {
  it("empty or whitespace query returns nothing", () => {
    expect(searchItems([fi("1", "LLM stuff")], topics, "")).toEqual({ items: [], topics: [] });
    expect(searchItems([fi("1", "LLM stuff")], topics, "   ")).toEqual({ items: [], topics: [] });
  });

  it("title matches outrank abstract matches", () => {
    const inTitle = fi("t", "Diffusion models go brrr");
    const inBody = fi("b", "Unrelated title", { abstract: "all about diffusion sampling" });
    const { items } = searchItems([inBody, inTitle], topics, "diffusion");
    expect(items.map((i) => i.id)).toEqual(["t", "b"]);
  });

  it("matches items via their topic's label", () => {
    const viaTopic = fi("k", "Plain title", { topic: "agents" });
    const { items } = searchItems([viaTopic], topics, "safety");
    expect(items.map((i) => i.id)).toEqual(["k"]); // matched via topic label "Agent Safety"
  });

  it("multi-term accumulates score and drops non-matches", () => {
    const both = fi("ab", "agent diffusion", {});
    const one = fi("a", "agent only");
    const none = fi("n", "nothing relevant");
    const { items } = searchItems([none, one, both], topics, "agent diffusion");
    expect(items.map((i) => i.id)).toEqual(["ab", "a"]);
  });

  it("ties break by newer published date and limit caps results", () => {
    const older = fi("old", "rag pipeline", { published_at: "2026-06-01T00:00:00+00:00" });
    const newer = fi("new", "rag pipeline", { published_at: "2026-06-08T00:00:00+00:00" });
    const { items } = searchItems([older, newer], topics, "rag");
    expect(items.map((i) => i.id)).toEqual(["new", "old"]);
    expect(searchItems([older, newer], topics, "rag", 1).items).toHaveLength(1);
  });

  it("returns matching topics by tag or label", () => {
    const { topics: matched } = searchItems([], topics, "training");
    expect(matched.map((t) => t.tag)).toEqual(["training"]);
  });
});
```

- [ ] **Step 2: Run `npm test`** — expect FAIL (`@/lib/search` unresolved).

- [ ] **Step 3: Implement `src/lib/search.ts`:**

```ts
import type { FeedItem } from "./feed";
import type { Topic } from "./types";

export type SearchResults = { items: FeedItem[]; topics: Topic[] };

function terms(q: string): string[] {
  return q.toLowerCase().split(/\s+/).filter(Boolean);
}

function itemDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

/** Substring scoring: title x3, topic tag/label x2, summary-or-abstract x1. */
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
      const topicText = item.topic
        ? `${item.topic.toLowerCase()} ${labelByTag.get(item.topic) ?? ""}`
        : "";
      let score = 0;
      for (const t of ts) {
        if (title.includes(t)) score += 3;
        if (topicText.includes(t)) score += 2;
        if (body.includes(t)) score += 1;
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

- [ ] **Step 4: Run `npm test`** — all pass (15 existing + 6 new = 21). `npx tsc --noEmit` clean.

- [ ] **Step 5: Commit**

```bash
git add src/lib/search.ts tests/web/search.test.ts
git commit -m "feat(web): add board search scoring engine"
```

---

### Task 2: `/search` page + nav search box

**Files:**
- Create: `src/app/search/page.tsx`
- Modify: `src/app/layout.tsx` (nav)

- [ ] **Step 1: Create `src/app/search/page.tsx`:**

```tsx
import Link from "next/link";
import { PostCard } from "@/components/PostCard";
import { getRecentDigests } from "@/lib/content";
import { itemKey, mergeDigests } from "@/lib/feed";
import { searchItems } from "@/lib/search";
import { getVoteCounts } from "@/lib/votes";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();
  const [digests, votes] = await Promise.all([getRecentDigests(7), getVoteCounts()]);
  const pool = mergeDigests(digests);
  const topics = digests[0]?.topics ?? [];
  const { items, topics: matchedTopics } = searchItems(pool, topics, query);

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-bold">
        {query ? (
          <>
            results for <span className="text-amber-400">&ldquo;{query}&rdquo;</span>
          </>
        ) : (
          "Search"
        )}
      </h1>
      {!query ? (
        <p className="mt-6 text-neutral-500">Type something in the search box up top.</p>
      ) : (
        <>
          {matchedTopics.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {matchedTopics.map((t) => (
                <Link
                  key={t.tag}
                  href={`/topics/${t.tag}`}
                  className="rounded-full border border-neutral-800 px-3 py-1 font-mono text-xs text-sky-400 transition-colors hover:border-neutral-700"
                >
                  t/{t.tag} · {t.label}
                </Link>
              ))}
            </div>
          )}
          {items.length === 0 ? (
            <p className="mt-6 text-neutral-500">Nothing found in the current pool.</p>
          ) : (
            <div className="mt-6 space-y-3">
              {items.map((item) => (
                <PostCard
                  key={itemKey(item)}
                  item={item}
                  initialNet={votes[itemKey(item)] ?? 0}
                />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
```

(No `revalidate` export — reading `searchParams` makes the page dynamic, which is intended.)

- [ ] **Step 2: Add the nav search form in `src/app/layout.tsx`.**

Inside the nav links container `<div className="flex gap-6 font-mono text-xs text-neutral-400">`, insert as the FIRST child (before the `topics` Link) — also change that container's `gap-6` to `items-center gap-5`:

```tsx
<form action="/search">
  <input
    name="q"
    placeholder="search"
    aria-label="Search the board"
    className="w-24 rounded-md border border-neutral-800 bg-neutral-900/60 px-2.5 py-1 font-mono text-xs text-neutral-200 outline-none transition-all placeholder:text-neutral-600 focus:w-40 focus:border-amber-500/60 sm:w-28 sm:focus:w-48"
  />
</form>
```

- [ ] **Step 3: Verify in dev.** `npx tsc --noEmit` clean; `npm test` green. Start `npm run dev` (background; read port from output), then:

```bash
curl -s "http://localhost:3000/search?q=llm" | grep -c "article"     # > 0 (matches exist in current data)
curl -s "http://localhost:3000/search?q=zzzqqq" | grep -o "Nothing found in the current pool."
curl -s "http://localhost:3000/search" | grep -o "Type something in the search box up top."
curl -s "http://localhost:3000/" | grep -o 'action="/search"'
```

Kill the dev server after.

- [ ] **Step 4: Commit**

```bash
git add src/app/search/page.tsx src/app/layout.tsx
git commit -m "feat(web): add /search page and nav search box"
```

---

### Task 3: Blog feed parsing (`pipeline/sources/blogs.py` — pure parts)

TDD with pytest. Parsing + window filtering only; network class comes in Task 4.

**Files:**
- Create: `pipeline/sources/blogs.py`
- Test: `tests/test_blogs.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_blogs.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pipeline.models import Item
from pipeline.sources.blogs import filter_window, parse_feed

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Example Blog</title>
<item>
  <title>Model X released</title>
  <link>https://example.com/model-x</link>
  <description>&lt;p&gt;Big &lt;b&gt;news&lt;/b&gt;   today.&lt;/p&gt;</description>
  <pubDate>Mon, 08 Jun 2026 12:00:00 +0000</pubDate>
</item>
<item>
  <title>No link entry</title>
  <description>skipped</description>
</item>
</channel></rss>"""


def _blog_item(published_at: str, publisher: str = "OpenAI", url: str = "https://x.com/a") -> Item:
    return Item(
        id="blog:abc",
        source="blog",
        title="t",
        url=url,
        abstract="",
        authors=[publisher],
        published_at=published_at,
        has_code=False,
        code_url=None,
    )


def test_parse_feed_maps_fields_and_strips_html():
    items = parse_feed("Example", RSS_FIXTURE)
    assert len(items) == 1  # entry without link skipped
    it = items[0]
    assert it.source == "blog"
    assert it.id.startswith("blog:") and len(it.id) == len("blog:") + 12
    assert it.title == "Model X released"
    assert it.url == "https://example.com/model-x"
    assert it.abstract == "Big news today."
    assert it.authors == ["Example"]
    assert it.published_at.startswith("2026-06-08T12:00:00")
    assert it.has_code is False


def test_filter_window_drops_old_and_undated_and_caps_per_publisher():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=30)).isoformat()
    items = [
        _blog_item(fresh, url="https://x.com/1"),
        _blog_item(old, url="https://x.com/2"),
        _blog_item("", url="https://x.com/3"),
        _blog_item("not-a-date", url="https://x.com/4"),
    ]
    kept = filter_window(items)
    assert [i.url for i in kept] == ["https://x.com/1"]

    many = [_blog_item(fresh, url=f"https://x.com/{n}") for n in range(8)]
    assert len(filter_window(many, cap=5)) == 5
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_blogs.py -q` — expect FAIL (module not found).

- [ ] **Step 3: Implement the pure parts of `pipeline/sources/blogs.py`:**

```python
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

from pipeline.models import Item
from pipeline.sources.tavily import _iso_date

log = logging.getLogger("throughline")

USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
TAVILY_API = "https://api.tavily.com/search"

# Live RSS feeds (probed 2026-06-10).
FEEDS: list[tuple[str, str]] = [
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
]

# Vendors with no RSS feed (all known candidates 404/403): reach them via Tavily.
NO_RSS_DOMAINS = ["anthropic.com", "claude.com", "ai.meta.com", "mistral.ai"]
TAVILY_QUERY = "announcement OR release OR research update"

WINDOW_DAYS = 7
PER_PUBLISHER_CAP = 5

_TAG_RE = re.compile(r"<[^>]+>")


def _blog_id(url: str) -> str:
    return "blog:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw or "")
    return re.sub(r"\s+", " ", text).strip()[:500]


def _entry_date(entry: dict) -> str:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return ""


def parse_feed(publisher: str, raw: str) -> list[Item]:
    parsed = feedparser.parse(raw)
    items: list[Item] = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        items.append(
            Item(
                id=_blog_id(link),
                source="blog",
                title=entry.get("title", ""),
                url=link,
                abstract=_strip_html(entry.get("summary", "") or entry.get("description", "")),
                authors=[publisher],
                published_at=_entry_date(entry),
                has_code=False,
                code_url=None,
            )
        )
    return items


def filter_window(
    items: list[Item], days: int = WINDOW_DAYS, cap: int = PER_PUBLISHER_CAP
) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[Item] = []
    counts: dict[str, int] = {}
    for it in items:
        if not it.published_at:
            continue
        try:
            when = datetime.fromisoformat(it.published_at)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < cutoff:
            continue
        publisher = it.authors[0] if it.authors else ""
        if counts.get(publisher, 0) >= cap:
            continue
        counts[publisher] = counts.get(publisher, 0) + 1
        out.append(it)
    return out
```

(`os` and `httpx` imports are used by Task 4's additions to this same file; keep them now so the file is final-shaped — if your linter complains, it doesn't: the repo has no Python linter in CI.)

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_blogs.py -q` — 2 pass. Full suite `.venv/bin/python -m pytest -q` — 48 pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/blogs.py tests/test_blogs.py
git commit -m "feat(pipeline): add blog feed parsing and window filter"
```

---

### Task 4: BlogSource fetch + Tavily fallback + pipeline registration

**Files:**
- Modify: `pipeline/sources/blogs.py` (append)
- Modify: `pipeline/run.py:14-23`
- Modify: `pipeline/rank.py:14`
- Test: append to `tests/test_blogs.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_blogs.py`:

```python
def test_fetch_tavily_blogs_without_key_returns_empty(monkeypatch):
    from pipeline.sources.blogs import fetch_tavily_blogs

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert fetch_tavily_blogs() == []


def test_blog_source_registered_in_pipeline():
    from pipeline.run import SOURCES

    assert "blog" in [s.name for s in SOURCES]


def test_blog_source_weight_set():
    from pipeline.rank import SOURCE_WEIGHT

    assert SOURCE_WEIGHT["blog"] == 0.12
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_blogs.py -q` — 3 new FAIL.

- [ ] **Step 3: Append to `pipeline/sources/blogs.py`:**

```python
def fetch_tavily_blogs(
    days: int = WINDOW_DAYS, max_results: int = 10, timeout: float = 30.0
) -> list[Item]:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        log.warning("TAVILY_API_KEY not set; skipping no-RSS blog vendors")
        return []
    body = {
        "query": TAVILY_QUERY,
        "topic": "news",
        "days": days,
        "max_results": max_results,
        "include_domains": NO_RSS_DOMAINS,
    }
    headers = {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}
    try:
        resp = httpx.post(TAVILY_API, json=body, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:  # fallback is best-effort; RSS feeds already fetched
        log.exception("tavily blog fallback failed; skipping")
        return []
    items: list[Item] = []
    for r in resp.json().get("results") or []:
        url = r.get("url", "")
        if not url:
            continue
        domain = url.split("/")[2].removeprefix("www.") if "://" in url else ""
        items.append(
            Item(
                id=_blog_id(url),
                source="blog",
                title=r.get("title", ""),
                url=url,
                abstract=_strip_html(r.get("content", "")),
                authors=[domain],
                published_at=_iso_date(r.get("published_date", "")),
                has_code=False,
                code_url=None,
            )
        )
    return items


class BlogSource:
    name = "blog"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for publisher, url in FEEDS:
            try:
                resp = httpx.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                items.extend(parse_feed(publisher, resp.text))
            except Exception:  # one dead feed must not kill the source
                log.exception("blog feed %s failed; skipping", publisher)
        items.extend(fetch_tavily_blogs())
        seen: set[str] = set()
        deduped: list[Item] = []
        for it in items:
            if it.id in seen:
                continue
            seen.add(it.id)
            deduped.append(it)
        return filter_window(deduped)
```

- [ ] **Step 4: Register in `pipeline/run.py`.** Add import after the existing source imports (line 18):

```python
from pipeline.sources.blogs import BlogSource
```

Change line 23 to:

```python
SOURCES = [ArxivSource(), TavilySource(), HackerNewsSource(), GitHubSource(), BlogSource()]
```

- [ ] **Step 5: Weight in `pipeline/rank.py`.** Change line 14 to:

```python
SOURCE_WEIGHT = {
    "github": 0.15,
    "blog": 0.12,
    "hackernews": 0.10,
    "news": 0.10,
    "arxiv": 0.05,
}
```

- [ ] **Step 6: Run** `.venv/bin/python -m pytest -q` — 51 pass. Live smoke (RSS only; no key in shell env is fine):

```bash
.venv/bin/python -c "from pipeline.sources.blogs import BlogSource; xs = BlogSource().fetch(); print(len(xs)); print(*[f'{x.authors[0]}: {x.title}' for x in xs[:5]], sep='\n')"
```

Expected: a handful of items from OpenAI/DeepMind/Google AI/Hugging Face published within 7 days (count may be small or zero on a quiet week — zero is acceptable if the command runs clean; check the log lines for per-feed errors).

- [ ] **Step 7: Commit**

```bash
git add pipeline/sources/blogs.py pipeline/run.py pipeline/rank.py tests/test_blogs.py
git commit -m "feat(pipeline): add blog source with RSS feeds and Tavily fallback"
```

---

### Task 5: Frontend `blog` badge

**Files:**
- Modify: `src/lib/types.ts:3`
- Modify: `src/components/SourceBadge.tsx`

- [ ] **Step 1: `src/lib/types.ts`** — extend the union:

```ts
source: "arxiv" | "hackernews" | "github" | "news" | "blog";
```

- [ ] **Step 2: `src/components/SourceBadge.tsx`** — add to both records:

In `LABELS`: `blog: "BLOG",`
In `COLORS`: `blog: "text-violet-400",`

- [ ] **Step 3: Verify** `npx tsc --noEmit` clean; `npm test` 21 pass; `npm run lint` zero problems.

- [ ] **Step 4: Commit**

```bash
git add src/lib/types.ts src/components/SourceBadge.tsx
git commit -m "feat(web): add blog source badge"
```

---

### Task 6: Full verification + push

- [ ] **Step 1: Full suite**

```bash
npm run lint        # 0 problems
npm test            # 21 pass
npx tsc --noEmit    # clean
npm run build       # succeeds (note /search listed as dynamic ƒ)
.venv/bin/python -m pytest -q   # 51 pass
```

- [ ] **Step 2: Dev smoke** (background `npm run dev`):
- `/` nav shows search box; submitting navigates to `/search?q=...`
- `/search?q=llm` shows results with PostCards; `/search?q=zzzqqq` shows empty state
- Kill server.

- [ ] **Step 3: Push** — `git pull --rebase origin main` (daily Action may have committed digests), re-run `npm test` + `.venv/bin/python -m pytest -q`, then `git push origin main`. If the environment blocks the push, stop and hand back to the user. After deploy: `/search?q=ai` on production returns 200. BLOG badge appears after the next daily pipeline run (no action needed).
