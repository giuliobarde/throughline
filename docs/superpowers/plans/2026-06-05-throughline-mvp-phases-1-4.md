# Throughline MVP (Phases 1–4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deployed Throughline site whose digest is produced by a daily arXiv pipeline and committed honestly by a scheduled GitHub Action authored as the user.

**Architecture:** A Python pipeline (`pipeline/run.py`) fetches arXiv items, normalizes them to an `Item` dataclass, and writes `content/digests/YYYY-MM-DD.json` + updates `content/index.json`. A Next.js (App Router, TS strict, Tailwind) site reads those committed files at build time with ISR and renders `/`, `/archive`, `/about`. A GitHub Action runs the pipeline daily, commits changed files with the real timestamp authored as the user (GitHub noreply email), and pushes; Vercel auto-deploys.

**Tech Stack:** Next.js 15 + TypeScript + Tailwind; Python 3.12, `httpx`/`feedparser`, `pytest`; GitHub Actions; Vercel.

**Scope note:** This plan covers Phases 1–4 only (the MVP + honest daily loop + deploy). Phases 5–10 (more sources, ML/clustering, Claude summaries, Supabase personalization, weekly synthesis, polish) each get their own spec→plan cycle after this loop is live.

**Honest-commit rules (apply to EVERY commit in this plan):** real timestamps only; never `--date`; never a Claude trailer/co-author line; Conventional Commits.

---

## File structure (created across this plan)

```
/pipeline
  __init__.py
  models.py            # Item dataclass + to_dict/from_dict
  sources/
    __init__.py
    base.py            # Source protocol: fetch() -> list[Item]
    arxiv.py           # ArxivSource
  digest.py            # build digest dict, write file, update index.json
  run.py               # CLI entrypoint: --date, --dry-run
  requirements.txt
/tests
  test_models.py
  test_arxiv.py
  test_digest.py
/content
  digests/             # YYYY-MM-DD.json (generated)
  index.json           # manifest
/lib
  content.ts           # typed loaders for digests + index
  types.ts             # Item / Digest / IndexEntry TS types
/app
  layout.tsx
  page.tsx             # today's digest
  globals.css
  archive/page.tsx
  about/page.tsx
/components
  ItemCard.tsx
  SourceBadge.tsx
/.github/workflows/daily-digest.yml
next.config.ts, tsconfig.json, tailwind config, package.json   # from scaffold
README.md
```

---

# PHASE 1 — Scaffold

### Task 1: Next.js + TS + Tailwind scaffold

**Files:** creates Next.js app in repo root (package.json, tsconfig.json, app/, etc.)

- [ ] **Step 1: Scaffold app into current directory**

The repo root already contains `.git`, `.gitignore`, and `docs/`. Scaffold in place:

```bash
npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir=false --import-alias "@/*" --no-turbopack --use-npm
```
If prompted to proceed in a non-empty dir, accept. Expected: creates `app/`, `package.json`, `next.config.ts`, `tsconfig.json`, Tailwind config, `package-lock.json`.

- [ ] **Step 2: Enable TS strict**

Confirm `tsconfig.json` has `"strict": true` under `compilerOptions` (create-next-app sets this). If absent, add it.

- [ ] **Step 3: Verify build runs**

Run: `npm run build`
Expected: build succeeds (default template).

- [ ] **Step 4: Add Prettier**

```bash
npm i -D prettier
printf '{\n  "semi": true,\n  "singleQuote": false,\n  "trailingComma": "all"\n}\n' > .prettierrc
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold Next.js + TS + Tailwind app"
```

### Task 2: README skeleton + /about placeholder

**Files:**
- Create: `README.md`, `app/about/page.tsx`

- [ ] **Step 1: Write README skeleton**

Create `README.md`:

```markdown
# Throughline

Self-updating AI research & engineering intelligence hub. A daily Python pipeline fetches
new ML/AI content, writes a dated digest, and a scheduled GitHub Action commits it with a
real timestamp. A Next.js site renders the digest, archive, and (later) weekly synthesis.

## Architecture

\`\`\`
sources → fetch → dedupe → embed → cluster → rank → summarize (Claude)
  → [weekly: synthesize] → write dated JSON/MDX → commit & push → Vercel ISR
\`\`\`

## Local setup

### Frontend
\`\`\`
npm install
npm run dev
\`\`\`

### Pipeline
\`\`\`
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py --dry-run            # print, don't write
python run.py --date 2026-06-05    # write a specific date
\`\`\`

## How the daily job works

\`.github/workflows/daily-digest.yml\` runs on a cron (\`0 12 * * *\`), executes the
pipeline, and if files changed commits them authored as the repo owner using the GitHub
noreply email (real timestamp, no backdating) and pushes to \`main\`. Vercel auto-deploys.

## Environment variables

| Var | Purpose | Phase |
|-----|---------|-------|
| \`ANTHROPIC_API_KEY\` | Claude summaries + synthesis | 7 |
| \`ANTHROPIC_MODEL\` | model id, defaults to \`claude-haiku-4-5\` | 7 |
| \`SUPABASE_URL\` / \`SUPABASE_ANON_KEY\` / \`SUPABASE_SERVICE_ROLE_KEY\` | personalization store | 8 |

Secrets live in GitHub Actions secrets / Vercel env. Never committed.
```

- [ ] **Step 2: Write /about placeholder**

Create `app/about/page.tsx`:

```tsx
export default function AboutPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-bold">About Throughline</h1>
      <p className="mt-4 text-neutral-400">
        A self-updating AI research &amp; engineering intelligence hub. Built in public,
        committed daily. More soon.
      </p>
    </main>
  );
}
```

- [ ] **Step 3: Verify**

Run: `npm run build`
Expected: build succeeds, `/about` route compiled.

- [ ] **Step 4: Commit**

```bash
git add README.md app/about/page.tsx
git commit -m "docs: add README skeleton and /about placeholder"
```

---

# PHASE 2 — Pipeline skeleton (arXiv → digest JSON)

### Task 3: Item model

**Files:**
- Create: `pipeline/__init__.py`, `pipeline/models.py`, `pipeline/requirements.txt`, `tests/test_models.py`

- [ ] **Step 1: Write requirements + package init**

Create `pipeline/requirements.txt`:
```
httpx==0.27.2
feedparser==6.0.11
pytest==8.3.3
```
Create empty `pipeline/__init__.py`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_models.py`:

```python
from pipeline.models import Item


def test_item_roundtrips_to_dict_and_back():
    item = Item(
        id="2401.00001",
        source="arxiv",
        title="A Title",
        url="http://arxiv.org/abs/2401.00001",
        abstract="An abstract.",
        authors=["Ada Lovelace"],
        published_at="2026-06-05T00:00:00Z",
        has_code=False,
        code_url=None,
    )
    d = item.to_dict()
    assert d["id"] == "2401.00001"
    assert d["authors"] == ["Ada Lovelace"]
    assert Item.from_dict(d) == item
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.models).

- [ ] **Step 4: Write minimal implementation**

Create `pipeline/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class Item:
    id: str
    source: str
    title: str
    url: str
    abstract: str
    authors: list[str]
    published_at: str  # ISO 8601
    has_code: bool
    code_url: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            id=d["id"],
            source=d["source"],
            title=d["title"],
            url=d["url"],
            abstract=d["abstract"],
            authors=list(d["authors"]),
            published_at=d["published_at"],
            has_code=bool(d["has_code"]),
            code_url=d.get("code_url"),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/__init__.py pipeline/models.py pipeline/requirements.txt tests/test_models.py
git commit -m "feat(pipeline): add Item dataclass with dict serialization"
```

### Task 4: arXiv source

**Files:**
- Create: `pipeline/sources/__init__.py`, `pipeline/sources/base.py`, `pipeline/sources/arxiv.py`, `tests/test_arxiv.py`

- [ ] **Step 1: Write the Source protocol + package init**

Create empty `pipeline/sources/__init__.py`.
Create `pipeline/sources/base.py`:

```python
from __future__ import annotations

from typing import Protocol

from pipeline.models import Item


class Source(Protocol):
    name: str

    def fetch(self) -> list[Item]:
        ...
```

- [ ] **Step 2: Write the failing test (parse a fixed Atom feed, no network)**

Create `tests/test_arxiv.py`:

```python
from pipeline.sources.arxiv import parse_arxiv_feed

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Scaling Laws for Widgets</title>
    <summary>We study widgets. Code available.</summary>
    <published>2026-06-05T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate"/>
  </entry>
</feed>"""


def test_parse_arxiv_feed_extracts_items():
    items = parse_arxiv_feed(SAMPLE)
    assert len(items) == 1
    it = items[0]
    assert it.id == "2401.00001"
    assert it.source == "arxiv"
    assert it.title == "Scaling Laws for Widgets"
    assert it.authors == ["Ada Lovelace", "Alan Turing"]
    assert it.url == "http://arxiv.org/abs/2401.00001v1"
    assert it.has_code is True  # "code" mentioned in summary
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_arxiv.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 4: Write implementation**

Create `pipeline/sources/arxiv.py`:

```python
from __future__ import annotations

import re

import feedparser
import httpx

from pipeline.models import Item

ARXIV_API = "http://export.arxiv.org/api/query"
CATEGORIES = ["cs.LG", "cs.CL", "cs.AI", "cs.MA"]
_ABS_ID = re.compile(r"abs/([^v]+)")
_CODE_HINT = re.compile(r"\b(code|github|implementation)\b", re.IGNORECASE)


def _arxiv_id(raw_id: str) -> str:
    m = _ABS_ID.search(raw_id)
    return m.group(1) if m else raw_id


def parse_arxiv_feed(xml: str) -> list[Item]:
    feed = feedparser.parse(xml)
    items: list[Item] = []
    for e in feed.entries:
        summary = getattr(e, "summary", "") or ""
        authors = [a.get("name", "") for a in getattr(e, "authors", []) if a.get("name")]
        items.append(
            Item(
                id=_arxiv_id(getattr(e, "id", "")),
                source="arxiv",
                title=" ".join(getattr(e, "title", "").split()),
                url=getattr(e, "link", ""),
                abstract=" ".join(summary.split()),
                authors=authors,
                published_at=getattr(e, "published", ""),
                has_code=bool(_CODE_HINT.search(summary)),
                code_url=None,
            )
        )
    return items


class ArxivSource:
    name = "arxiv"

    def __init__(self, max_results: int = 50, timeout: float = 30.0) -> None:
        self.max_results = max_results
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        query = "+OR+".join(f"cat:{c}" for c in CATEGORIES)
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(self.max_results),
        }
        resp = httpx.get(ARXIV_API, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return parse_arxiv_feed(resp.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_arxiv.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/sources/__init__.py pipeline/sources/base.py pipeline/sources/arxiv.py tests/test_arxiv.py
git commit -m "feat(pipeline): add arXiv source with feed parsing"
```

### Task 5: Digest builder + index manifest

**Files:**
- Create: `pipeline/digest.py`, `tests/test_digest.py`, `content/digests/.gitkeep`

- [ ] **Step 1: Write the failing test**

Create `tests/test_digest.py`:

```python
import json
from pathlib import Path

from pipeline.digest import build_digest, write_digest
from pipeline.models import Item


def _item(i: str) -> Item:
    return Item(
        id=i, source="arxiv", title=f"T{i}", url=f"http://x/{i}",
        abstract="a", authors=["Z"], published_at="2026-06-05T00:00:00Z",
        has_code=False, code_url=None,
    )


def test_build_digest_shape():
    d = build_digest("2026-06-05", [_item("1"), _item("2")])
    assert d["date"] == "2026-06-05"
    assert "generated_at" in d
    assert len(d["items"]) == 2
    assert d["topics"] == []


def test_write_digest_is_idempotent_and_updates_index(tmp_path: Path):
    content = tmp_path / "content"
    write_digest("2026-06-05", [_item("1")], content_dir=content)
    write_digest("2026-06-05", [_item("1"), _item("2")], content_dir=content)  # rerun

    digest = json.loads((content / "digests" / "2026-06-05.json").read_text())
    assert len(digest["items"]) == 2  # overwritten cleanly

    index = json.loads((content / "index.json").read_text())
    assert len(index) == 1  # not duplicated
    assert index[0] == {"date": "2026-06-05", "item_count": 2, "has_synthesis": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write implementation**

Create `pipeline/digest.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.models import Item

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def build_digest(date: str, items: list[Item]) -> dict:
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [it.to_dict() for it in items],
        "topics": [],
    }


def _update_index(content_dir: Path, date: str, item_count: int, has_synthesis: bool) -> None:
    index_path = content_dir / "index.json"
    index: list[dict] = []
    if index_path.exists():
        index = json.loads(index_path.read_text())
    index = [e for e in index if e["date"] != date]  # idempotent: drop existing
    index.append({"date": date, "item_count": item_count, "has_synthesis": has_synthesis})
    index.sort(key=lambda e: e["date"], reverse=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n")


def write_digest(
    date: str,
    items: list[Item],
    content_dir: Path = DEFAULT_CONTENT_DIR,
    has_synthesis: bool = False,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(date, items)
    out = digests_dir / f"{date}.json"
    out.write_text(json.dumps(digest, indent=2) + "\n")
    _update_index(content_dir, date, len(items), has_synthesis)
    return out
```

Create `content/digests/.gitkeep` (empty) so the dir is tracked.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_digest.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py content/digests/.gitkeep
git commit -m "feat(pipeline): add idempotent digest writer and index manifest"
```

### Task 6: CLI entrypoint (run.py)

**Files:**
- Create: `pipeline/run.py`

- [ ] **Step 1: Write run.py**

Create `pipeline/run.py`:

```python
from __future__ import annotations

import argparse
import json
import logging
from datetime import date as date_cls

from pipeline.digest import write_digest
from pipeline.models import Item
from pipeline.sources.arxiv import ArxivSource

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("throughline")

SOURCES = [ArxivSource()]


def collect() -> list[Item]:
    items: list[Item] = []
    for source in SOURCES:
        try:
            fetched = source.fetch()
            log.info("source %s: %d items", source.name, len(fetched))
            items.extend(fetched)
        except Exception:  # fault-tolerant: one source must not kill the run
            log.exception("source %s failed; skipping", source.name)
    return dedupe(items)


def dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Throughline daily pipeline")
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = parser.parse_args()

    items = collect()
    log.info("collected %d items for %s", len(items), args.date)

    if args.dry_run:
        print(json.dumps([it.to_dict() for it in items], indent=2))
        return

    out = write_digest(args.date, items)
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify dry-run works (real network)**

Run: `python -m pipeline.run --dry-run`
Expected: logs `source arxiv: N items`, prints a JSON array. If network is unavailable, the source logs an error and prints `[]` (fault-tolerant) — acceptable.

- [ ] **Step 3: Verify a dated write**

Run: `python -m pipeline.run --date 2026-06-05`
Expected: writes `content/digests/2026-06-05.json` and `content/index.json`.

- [ ] **Step 4: Commit (code + first generated digest)**

```bash
git add pipeline/run.py content/digests/2026-06-05.json content/index.json
git commit -m "feat(pipeline): add run.py entrypoint with --date and --dry-run"
```

---

# PHASE 3 — Frontend reads content

### Task 7: TS types + content loaders

**Files:**
- Create: `lib/types.ts`, `lib/content.ts`

- [ ] **Step 1: Write TS types**

Create `lib/types.ts`:

```ts
export type Item = {
  id: string;
  source: "arxiv" | "hackernews" | "github";
  title: string;
  url: string;
  abstract: string;
  authors: string[];
  published_at: string;
  has_code: boolean;
  code_url: string | null;
  summary?: string;
  topic?: string;
  repro_difficulty?: "low" | "med" | "high";
  for_you_score?: number;
};

export type Topic = { tag: string; label: string; item_ids: string[] };

export type Digest = {
  date: string;
  generated_at: string;
  items: Item[];
  topics: Topic[];
};

export type IndexEntry = {
  date: string;
  item_count: number;
  has_synthesis: boolean;
};
```

- [ ] **Step 2: Write loaders**

Create `lib/content.ts`:

```ts
import { promises as fs } from "fs";
import path from "path";
import type { Digest, IndexEntry } from "./types";

const CONTENT = path.join(process.cwd(), "content");

export async function getIndex(): Promise<IndexEntry[]> {
  try {
    const raw = await fs.readFile(path.join(CONTENT, "index.json"), "utf-8");
    return JSON.parse(raw) as IndexEntry[];
  } catch {
    return [];
  }
}

export async function getDigest(date: string): Promise<Digest | null> {
  try {
    const raw = await fs.readFile(
      path.join(CONTENT, "digests", `${date}.json`),
      "utf-8",
    );
    return JSON.parse(raw) as Digest;
  } catch {
    return null;
  }
}

export async function getLatestDigest(): Promise<Digest | null> {
  const index = await getIndex();
  if (index.length === 0) return null;
  return getDigest(index[0].date);
}
```

- [ ] **Step 3: Verify typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add lib/types.ts lib/content.ts
git commit -m "feat(web): add content types and JSON loaders"
```

### Task 8: Item card + source badge components

**Files:**
- Create: `components/SourceBadge.tsx`, `components/ItemCard.tsx`

- [ ] **Step 1: Write SourceBadge**

Create `components/SourceBadge.tsx`:

```tsx
import type { Item } from "@/lib/types";

const LABELS: Record<Item["source"], string> = {
  arxiv: "arXiv",
  hackernews: "HN",
  github: "GitHub",
};

export function SourceBadge({ source }: { source: Item["source"] }) {
  return (
    <span className="font-mono text-xs uppercase tracking-wider text-neutral-500">
      {LABELS[source]}
    </span>
  );
}
```

- [ ] **Step 2: Write ItemCard**

Create `components/ItemCard.tsx`:

```tsx
import type { Item } from "@/lib/types";
import { SourceBadge } from "./SourceBadge";

export function ItemCard({ item }: { item: Item }) {
  return (
    <article className="border-b border-neutral-800 py-6">
      <div className="flex items-center gap-3">
        <SourceBadge source={item.source} />
        {item.has_code && (
          <span className="font-mono text-xs text-emerald-500">code</span>
        )}
        <time className="font-mono text-xs text-neutral-600">
          {item.published_at.slice(0, 10)}
        </time>
      </div>
      <h2 className="mt-2 text-lg font-semibold leading-snug">
        <a href={item.url} className="hover:underline" target="_blank" rel="noreferrer">
          {item.title}
        </a>
      </h2>
      <p className="mt-2 line-clamp-3 text-sm text-neutral-400">
        {item.summary ?? item.abstract}
      </p>
      {item.authors.length > 0 && (
        <p className="mt-2 font-mono text-xs text-neutral-600">
          {item.authors.slice(0, 4).join(", ")}
          {item.authors.length > 4 ? " et al." : ""}
        </p>
      )}
    </article>
  );
}
```

- [ ] **Step 3: Verify typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add components/SourceBadge.tsx components/ItemCard.tsx
git commit -m "feat(web): add ItemCard and SourceBadge components"
```

### Task 9: Layout + home page (today's digest) with ISR

**Files:**
- Modify: `app/layout.tsx`, `app/globals.css`
- Replace: `app/page.tsx`

- [ ] **Step 1: Set dark-default layout**

Replace `app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Throughline",
  description: "Self-updating AI research & engineering intelligence hub.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <nav className="border-b border-neutral-800">
          <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
            <a href="/" className="font-mono text-sm font-bold tracking-tight">
              throughline
            </a>
            <div className="flex gap-6 font-mono text-xs text-neutral-400">
              <a href="/archive" className="hover:text-neutral-100">archive</a>
              <a href="/about" className="hover:text-neutral-100">about</a>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Ensure globals.css keeps Tailwind directives**

Confirm `app/globals.css` contains the Tailwind import line generated by the scaffold (e.g. `@import "tailwindcss";` for v4, or the three `@tailwind` directives for v3). Leave as-is; do not remove them.

- [ ] **Step 3: Replace home page**

Replace `app/page.tsx` with:

```tsx
import { ItemCard } from "@/components/ItemCard";
import { getLatestDigest } from "@/lib/content";

export const revalidate = 3600; // ISR: rebuild hourly

export default async function HomePage() {
  const digest = await getLatestDigest();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Today&rsquo;s digest</h1>
        {digest && (
          <p className="mt-1 font-mono text-xs text-neutral-500">
            {digest.date} · {digest.items.length} items
          </p>
        )}
      </header>

      {!digest || digest.items.length === 0 ? (
        <p className="text-neutral-500">No digest yet. The pipeline runs daily.</p>
      ) : (
        <div>
          {digest.items.map((item) => (
            <ItemCard key={`${item.source}:${item.id}`} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Verify build + dev render**

Run: `npm run build`
Expected: succeeds; `/` is statically generated using `content/digests/2026-06-05.json`.

- [ ] **Step 5: Commit**

```bash
git add app/layout.tsx app/page.tsx app/globals.css
git commit -m "feat(web): render today's digest on home page with ISR"
```

### Task 10: Archive page

**Files:**
- Create: `app/archive/page.tsx`

- [ ] **Step 1: Write archive page**

Create `app/archive/page.tsx`:

```tsx
import { getIndex } from "@/lib/content";

export const revalidate = 3600;

export default async function ArchivePage() {
  const index = await getIndex();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Archive</h1>
      {index.length === 0 ? (
        <p className="mt-6 text-neutral-500">No digests yet.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {index.map((entry) => (
            <li key={entry.date} className="flex items-center justify-between py-3">
              <span className="font-mono text-sm">{entry.date}</span>
              <span className="font-mono text-xs text-neutral-500">
                {entry.item_count} items{entry.has_synthesis ? " · synthesis" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `npm run build`
Expected: `/archive` compiled, lists 2026-06-05.

- [ ] **Step 3: Commit**

```bash
git add app/archive/page.tsx
git commit -m "feat(web): add archive page listing past digests"
```

---

# PHASE 4 — Automation + deploy (the honest daily loop)

> Requires user-provided values. Before Task 11, collect from the user:
> - GitHub **username** (to build the noreply email and remote URL)
> - Confirm GitHub noreply email format: `USERNAME@users.noreply.github.com` OR the
>   id-prefixed `ID+USERNAME@users.noreply.github.com` (from GitHub → Settings → Emails →
>   "Keep my email addresses private"). Prefer the id-prefixed form if present.

### Task 11: Create the public GitHub repo and push

**Files:** none (git remote operations)

- [ ] **Step 1: Create the repo via the GitHub connector**

Use the GitHub MCP tool `create_repository` with: name `throughline`, visibility **public**,
description "Self-updating AI research & engineering intelligence hub", `autoInit: false`.

- [ ] **Step 2: Set the remote and push existing honest history**

```bash
git remote add origin https://github.com/<USERNAME>/throughline.git
git branch -M main
git push -u origin main
```
Expected: all build commits pushed with their real timestamps.

- [ ] **Step 3: Re-point local author to the noreply email (so future commits also count)**

```bash
git config user.email "<NOREPLY_EMAIL>"
```
(Name may remain "Giulio". This does not rewrite past commits — honest history preserved.)

### Task 12: Daily digest workflow

**Files:**
- Create: `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/daily-digest.yml`:

```yaml
name: daily-digest

on:
  schedule:
    - cron: "0 12 * * *" # ~daily at 12:00 UTC
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: daily-digest
  cancel-in-progress: false

jobs:
  build:
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

      - name: Run pipeline
        run: python -m pipeline.run

      - name: Commit digest if changed
        env:
          USER_NAME: ${{ vars.GIT_AUTHOR_NAME }}
          USER_EMAIL: ${{ vars.GIT_AUTHOR_EMAIL }}
        run: |
          if [ -z "$(git status --porcelain content)" ]; then
            echo "No content changes; nothing to commit."
            exit 0
          fi
          git config user.name "$USER_NAME"
          git config user.email "$USER_EMAIL"
          git add content
          git commit -m "chore(digest): $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: Set the Action author identity as repo variables**

Set repository **Variables** (not secrets — these are not sensitive):
- `GIT_AUTHOR_NAME` = `Giulio`
- `GIT_AUTHOR_EMAIL` = `<NOREPLY_EMAIL>`

Via the GitHub UI (Settings → Secrets and variables → Actions → Variables) or connector.

- [ ] **Step 3: Commit and push the workflow**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "ci: add honest daily digest workflow"
git push
```

- [ ] **Step 4: Test via manual dispatch**

Trigger `daily-digest` via `workflow_dispatch` (GitHub UI "Run workflow" or connector).
Expected: run succeeds; if today's digest differs from committed, a `chore(digest): <date>`
commit appears authored by the noreply email (verified, counts toward contribution graph).
If no diff, the run logs "nothing to commit" and exits 0 — also success.

### Task 13: Deploy to Vercel

**Files:** none (Vercel project creation)

- [ ] **Step 1: Create the Vercel project from the repo**

Use the Vercel connector / `deploy_to_vercel` to create a project linked to
`<USERNAME>/throughline`, framework preset Next.js, production branch `main`.

- [ ] **Step 2: Confirm production deploy**

Expected: build succeeds; `/`, `/archive`, `/about` render the committed 2026-06-05 digest.
No env vars needed yet (Anthropic/Supabase come in Phases 7–8).

- [ ] **Step 3: Verify the end-to-end loop**

Re-dispatch `daily-digest`. If it commits, Vercel auto-deploys; within ISR `revalidate`
(3600s) the site reflects the new digest. Honest daily loop confirmed live.

- [ ] **Step 4: Update README with the live URL**

Add the deployed URL to the top of `README.md`, then:

```bash
git add README.md
git commit -m "docs: add live deployment URL"
git push
```

---

## Self-review notes

- **Spec coverage (Phases 1–4):** scaffold (T1–2), Item model (T3), arXiv source (T4),
  idempotent digest + index (T5), run.py with `--date`/`--dry-run` (T6), typed loaders
  (T7), cards (T8), home+ISR (T9), archive (T10), public repo (T11), honest daily Action
  authored as user via noreply email, real timestamps, no Claude trailer (T12), Vercel
  deploy (T13). Fault-tolerance: `collect()` try/except per source. Dedupe: `dedupe()`.
- **Deferred to later plans:** HN + GitHub sources (P5), embeddings/clustering (P6), Claude
  summaries (P7), Supabase personalization (P8), weekly synthesis (P9), polish + search +
  frontend-design pass (P10). Item/Digest types already carry optional `summary`, `topic`,
  `repro_difficulty`, `for_you_score`, `topics[]` fields so later phases extend without
  breaking the JSON contract.
- **Type consistency:** Python `Item` fields == TS `Item` fields == digest JSON keys.
  `IndexEntry` keys (`date`, `item_count`, `has_synthesis`) match `_update_index` output.
- **No placeholders** except the explicitly user-supplied `<USERNAME>` / `<NOREPLY_EMAIL>`
  collected at the start of Phase 4.
```
