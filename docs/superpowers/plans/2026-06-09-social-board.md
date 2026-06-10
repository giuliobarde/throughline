# Throughline Social Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Throughline frontend into a Reddit-style social board (ranked tabs, votes, saves, density toggle, infinite scroll) over the unchanged Python pipeline.

**Architecture:** All changes in the Next.js layer. Pure feed/ranking functions live in client-safe libs (`src/lib/feed.ts`, `trending.ts`, `local.ts`) tested with Vitest; server glue (digest loaders, Supabase vote counts) follows the existing null-safe loader pattern; UI is a client `Feed` component fed server-rendered initial data. Votes reuse the existing `feedback` table so the phase-8b ranker keeps learning.

**Tech Stack:** Next.js 16 App Router · TS strict · Tailwind v4 · Supabase JS · Vitest (new) + jsdom · existing pytest suite untouched.

**Spec:** `docs/superpowers/specs/2026-06-09-social-board-design.md`

**Commit rules (repo non-negotiable):** author is the already-configured `Giulio <giuliobarde@users.noreply.github.com>` (plain `git commit` is fine), real timestamps, **NO Co-Authored-By / Claude trailer of any kind**.

**Key existing facts:**
- `content/index.json` = `IndexEntry[]` sorted newest-first; digests at `content/digests/YYYY-MM-DD.json`.
- `feedback` table rows: `{item_id: "source:id", signal: 1 | -1}`; `POST /api/feedback` already validates this.
- `src/lib/supabase.ts` imports `server-only` — **never import it (directly or transitively) from a Vitest-tested or client file**.
- Item keys are `` `${source}:${id}` `` everywhere.

---

### Task 1: Vitest harness

**Files:**
- Modify: `package.json`
- Create: `vitest.config.ts`

- [ ] **Step 1: Install dev deps**

Run: `npm install -D vitest jsdom`

- [ ] **Step 2: Create `vitest.config.ts`**

```ts
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/web/**/*.test.ts"],
    passWithNoTests: true,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
```

- [ ] **Step 3: Add script to `package.json`**

In `"scripts"`, after `"lint": "eslint"` add:

```json
"test": "vitest run"
```

- [ ] **Step 4: Verify**

Run: `npm test`
Expected: exits 0 with "No test files found" (passWithNoTests).

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json vitest.config.ts
git commit -m "chore(web): add Vitest test harness"
```

---

### Task 2: Feed engine (`src/lib/feed.ts`)

Pure, client-safe (no fs, no server-only). Powers server initial sort AND client tab re-sorts.

**Files:**
- Create: `src/lib/feed.ts`
- Test: `tests/web/feed.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
import { describe, expect, it } from "vitest";
import type { Digest, Item } from "@/lib/types";
import { hotScore, itemKey, mergeDigests, sortFeed } from "@/lib/feed";

const base: Omit<Item, "id" | "source"> = {
  title: "t",
  url: "https://example.com/x",
  abstract: "a",
  authors: [],
  published_at: "2026-06-08T00:00:00+00:00",
  has_code: false,
  code_url: null,
};

function item(id: string, source: Item["source"], extra: Partial<Item> = {}): Item {
  return { ...base, id, source, ...extra };
}

function digest(date: string, items: Item[]): Digest {
  return { date, generated_at: `${date}T12:00:00+00:00`, items, topics: [] };
}

describe("itemKey", () => {
  it("joins source and id", () => {
    expect(itemKey(item("1", "arxiv"))).toBe("arxiv:1");
  });
});

describe("mergeDigests", () => {
  it("dedupes across digests keeping the newest occurrence and tags digestDate", () => {
    const newest = digest("2026-06-08", [item("1", "arxiv", { summary: "new" })]);
    const older = digest("2026-06-07", [item("1", "arxiv", { summary: "old" }), item("2", "github")]);
    const merged = mergeDigests([newest, older]); // newest first, as loaded
    expect(merged).toHaveLength(2);
    expect(merged[0]).toMatchObject({ id: "1", summary: "new", digestDate: "2026-06-08" });
    expect(merged[1]).toMatchObject({ id: "2", digestDate: "2026-06-07" });
  });
});

describe("hotScore", () => {
  it("decays with age and grows with net votes", () => {
    expect(hotScore(10, 1)).toBeGreaterThan(hotScore(10, 24));
    expect(hotScore(10, 5)).toBeGreaterThan(hotScore(0, 5));
  });
});

describe("sortFeed", () => {
  const now = new Date("2026-06-09T00:00:00+00:00");
  const fresh = { ...item("f", "github", { published_at: "2026-06-08T20:00:00+00:00" }), digestDate: "2026-06-08" };
  const popular = { ...item("p", "arxiv", { published_at: "2026-06-06T00:00:00+00:00" }), digestDate: "2026-06-06" };
  const stale = { ...item("s", "news", { published_at: "2026-05-01T00:00:00+00:00", for_you_score: 0.9 }), digestDate: "2026-05-02" };

  it("hot: heavy votes beat freshness with zero votes", () => {
    const out = sortFeed([fresh, popular], "hot", { "arxiv:p": 50 }, now);
    expect(out.map((i) => i.id)).toEqual(["p", "f"]);
  });

  it("new: newest published first", () => {
    const out = sortFeed([popular, fresh], "new", {}, now);
    expect(out[0].id).toBe("f");
  });

  it("foryou: for_you_score desc", () => {
    const out = sortFeed([fresh, stale], "foryou", {}, now);
    expect(out[0].id).toBe("s");
  });

  it("top: net votes desc, excludes items older than 7 days", () => {
    const out = sortFeed([fresh, popular, stale], "top", { "news:s": 100, "arxiv:p": 5 }, now);
    expect(out.map((i) => i.id)).toEqual(["p", "f"]); // stale excluded despite 100 votes
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `npm test`
Expected: FAIL — cannot resolve `@/lib/feed`.

- [ ] **Step 3: Implement `src/lib/feed.ts`**

```ts
import type { Digest, Item } from "./types";

export type FeedItem = Item & { digestDate: string };
export type FeedSort = "hot" | "new" | "foryou" | "top";
export type VoteCounts = Record<string, number>;

export function itemKey(i: Pick<Item, "source" | "id">): string {
  return `${i.source}:${i.id}`;
}

/** Digests must be ordered newest-first; first occurrence of a key wins. */
export function mergeDigests(digests: Digest[]): FeedItem[] {
  const seen = new Set<string>();
  const out: FeedItem[] = [];
  for (const d of digests) {
    for (const item of d.items) {
      const key = itemKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ ...item, digestDate: d.date });
    }
  }
  return out;
}

/** Gravity-style: votes push up, age pulls down. */
export function hotScore(net: number, ageHours: number): number {
  return (1 + net) / Math.pow(ageHours + 2, 1.5);
}

function effectiveDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

function ageHours(i: FeedItem, now: Date): number {
  return Math.max(0, (now.getTime() - effectiveDate(i)) / 3_600_000);
}

const WEEK_MS = 7 * 24 * 3_600_000;

export function sortFeed(
  items: FeedItem[],
  sort: FeedSort,
  votes: VoteCounts,
  now: Date,
): FeedItem[] {
  const net = (i: FeedItem) => votes[itemKey(i)] ?? 0;
  switch (sort) {
    case "hot":
      return [...items].sort(
        (a, b) => hotScore(net(b), ageHours(b, now)) - hotScore(net(a), ageHours(a, now)),
      );
    case "new":
      return [...items].sort((a, b) => effectiveDate(b) - effectiveDate(a));
    case "foryou":
      return [...items].sort((a, b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0));
    case "top":
      return items
        .filter((i) => now.getTime() - effectiveDate(i) <= WEEK_MS)
        .sort((a, b) => net(b) - net(a) || effectiveDate(b) - effectiveDate(a));
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `npm test`
Expected: all feed tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/feed.ts tests/web/feed.test.ts
git commit -m "feat(web): add feed engine with hot/new/foryou/top sorts"
```

---

### Task 3: Vote aggregation + trending (pure)

**Files:**
- Create: `src/lib/trending.ts`
- Modify: `src/lib/feed.ts` (append `aggregateVotes`)
- Test: `tests/web/trending.test.ts`, append to `tests/web/feed.test.ts`

- [ ] **Step 1: Write failing tests**

Append to `tests/web/feed.test.ts` (add `aggregateVotes` to the existing import from `@/lib/feed`):

```ts
import { aggregateVotes } from "@/lib/feed";

describe("aggregateVotes", () => {
  it("sums signals per item", () => {
    const rows = [
      { item_id: "arxiv:1", signal: 1 },
      { item_id: "arxiv:1", signal: 1 },
      { item_id: "arxiv:1", signal: -1 },
      { item_id: "github:2", signal: -1 },
    ];
    expect(aggregateVotes(rows)).toEqual({ "arxiv:1": 1, "github:2": -1 });
  });
});
```

Create `tests/web/trending.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { Digest } from "@/lib/types";
import { trendingTopics } from "@/lib/trending";

function digest(date: string, topics: Digest["topics"]): Digest {
  return { date, generated_at: `${date}T12:00:00+00:00`, items: [], topics };
}

describe("trendingTopics", () => {
  it("ranks by count with delta vs previous digest", () => {
    const latest = digest("2026-06-08", [
      { tag: "agents", label: "Agents", item_ids: ["a", "b", "c"] },
      { tag: "training", label: "Training", item_ids: ["d"] },
    ]);
    const previous = digest("2026-06-07", [
      { tag: "agents", label: "Agents", item_ids: ["a"] },
    ]);
    expect(trendingTopics(latest, previous)).toEqual([
      { tag: "agents", label: "Agents", count: 3, delta: 2 },
      { tag: "training", label: "Training", count: 1, delta: 1 },
    ]);
  });

  it("handles null inputs", () => {
    expect(trendingTopics(null, null)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `npm test`
Expected: FAIL — `aggregateVotes` not exported; `@/lib/trending` unresolved.

- [ ] **Step 3: Implement**

Append to `src/lib/feed.ts`:

```ts
export function aggregateVotes(rows: { item_id: string; signal: number }[]): VoteCounts {
  const out: VoteCounts = {};
  for (const r of rows) out[r.item_id] = (out[r.item_id] ?? 0) + r.signal;
  return out;
}
```

Create `src/lib/trending.ts`:

```ts
import type { Digest } from "./types";

export type TrendingTopic = { tag: string; label: string; count: number; delta: number };

export function trendingTopics(
  latest: Digest | null,
  previous: Digest | null,
  limit = 5,
): TrendingTopic[] {
  if (!latest) return [];
  const prev = new Map((previous?.topics ?? []).map((t) => [t.tag, t.item_ids.length]));
  return latest.topics
    .map((t) => ({
      tag: t.tag,
      label: t.label,
      count: t.item_ids.length,
      delta: t.item_ids.length - (prev.get(t.tag) ?? 0),
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `npm test` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/feed.ts src/lib/trending.ts tests/web/feed.test.ts tests/web/trending.test.ts
git commit -m "feat(web): add vote aggregation and trending topics"
```

---

### Task 4: Local state utils (`src/lib/local.ts`)

Client-only localStorage helpers: density pref, one-vote-per-browser guard, saves.

**Files:**
- Create: `src/lib/local.ts`
- Test: `tests/web/local.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import {
  getDensity,
  getSaves,
  getVote,
  setDensity,
  setVote,
  toggleSave,
  type SavedItem,
} from "@/lib/local";

const saved: SavedItem = {
  key: "arxiv:1",
  title: "Paper",
  url: "https://arxiv.org/abs/1",
  source: "arxiv",
  date: "2026-06-08",
};

beforeEach(() => localStorage.clear());

describe("density", () => {
  it("defaults to cards and persists", () => {
    expect(getDensity()).toBe("cards");
    setDensity("compact");
    expect(getDensity()).toBe("compact");
  });
});

describe("votes", () => {
  it("defaults to 0, persists, and clears", () => {
    expect(getVote("arxiv:1")).toBe(0);
    setVote("arxiv:1", 1);
    expect(getVote("arxiv:1")).toBe(1);
    setVote("arxiv:1", 0);
    expect(getVote("arxiv:1")).toBe(0);
  });
});

describe("saves", () => {
  it("toggles on and off", () => {
    expect(toggleSave(saved)).toBe(true);
    expect(getSaves()).toEqual([saved]);
    expect(toggleSave(saved)).toBe(false);
    expect(getSaves()).toEqual([]);
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `npm test`
Expected: FAIL — `@/lib/local` unresolved.

- [ ] **Step 3: Implement `src/lib/local.ts`**

```ts
export type Density = "cards" | "compact";
export type SavedItem = {
  key: string;
  title: string;
  url: string;
  source: string;
  date: string;
};

const DENSITY = "tl:density";
const VOTES = "tl:votes";
const SAVES = "tl:saves";

function read<T>(key: string, fallback: T): T {
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage full or blocked — degrade silently
  }
}

export function getDensity(): Density {
  return read<Density>(DENSITY, "cards");
}

export function setDensity(d: Density): void {
  write(DENSITY, d);
}

export function getVote(key: string): 1 | -1 | 0 {
  return read<Record<string, 1 | -1>>(VOTES, {})[key] ?? 0;
}

export function setVote(key: string, value: 1 | -1 | 0): void {
  const votes = read<Record<string, 1 | -1>>(VOTES, {});
  if (value === 0) delete votes[key];
  else votes[key] = value;
  write(VOTES, votes);
}

export function getSaves(): SavedItem[] {
  return read<SavedItem[]>(SAVES, []);
}

/** Returns the new saved state for this item. */
export function toggleSave(item: SavedItem): boolean {
  const saves = getSaves();
  const idx = saves.findIndex((s) => s.key === item.key);
  if (idx >= 0) {
    saves.splice(idx, 1);
    write(SAVES, saves);
    return false;
  }
  write(SAVES, [item, ...saves]);
  return true;
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `npm test` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/local.ts tests/web/local.test.ts
git commit -m "feat(web): add localStorage density, vote-guard, and saves utils"
```

---

### Task 5: Server loaders — digest pool + vote counts

Follows the existing null-safe loader pattern in `content.ts` (fs glue, no unit tests; exercised by build + live verification).

**Files:**
- Modify: `src/lib/content.ts` (append two loaders)
- Create: `src/lib/votes.ts`

- [ ] **Step 1: Append to `src/lib/content.ts`**

```ts
export async function getRecentDigests(count = 7): Promise<Digest[]> {
  const index = await getIndex();
  const digests = await Promise.all(index.slice(0, count).map((e) => getDigest(e.date)));
  return digests.filter((d): d is Digest => Boolean(d));
}

export async function getDigestsBefore(
  date: string,
  count = 7,
): Promise<{ digests: Digest[]; nextBefore: string | null }> {
  const index = await getIndex();
  const older = index.filter((e) => e.date < date);
  const page = older.slice(0, count);
  const digests = (
    await Promise.all(page.map((e) => getDigest(e.date)))
  ).filter((d): d is Digest => Boolean(d));
  const nextBefore = older.length > count ? page[page.length - 1].date : null;
  return { digests, nextBefore };
}
```

- [ ] **Step 2: Create `src/lib/votes.ts`**

```ts
import "server-only";
import { aggregateVotes, type VoteCounts } from "./feed";
import { getServiceClient } from "./supabase";

export async function getVoteCounts(): Promise<VoteCounts> {
  const client = getServiceClient();
  if (!client) return {};
  try {
    const { data, error } = await client
      .from("feedback")
      .select("item_id, signal")
      .range(0, 9999);
    if (error || !data) return {};
    return aggregateVotes(data as { item_id: string; signal: number }[]);
  } catch {
    return {};
  }
}
```

- [ ] **Step 3: Verify it compiles**

Run: `npx tsc --noEmit`
Expected: no errors. (`npm test` must also still pass.)

- [ ] **Step 4: Commit**

```bash
git add src/lib/content.ts src/lib/votes.ts
git commit -m "feat(web): add digest pool loaders and Supabase vote counts"
```

---

### Task 6: API routes — `GET /api/votes`, `GET /api/feed`

**Files:**
- Create: `src/app/api/votes/route.ts`
- Create: `src/app/api/feed/route.ts`

- [ ] **Step 1: Create `src/app/api/votes/route.ts`**

```ts
import { NextResponse } from "next/server";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 60;

export async function GET() {
  const counts = await getVoteCounts();
  return NextResponse.json({ counts });
}
```

- [ ] **Step 2: Create `src/app/api/feed/route.ts`**

```ts
import { NextResponse } from "next/server";
import { getDigestsBefore } from "@/lib/content";
import { mergeDigests } from "@/lib/feed";

export async function GET(request: Request) {
  const before = new URL(request.url).searchParams.get("before");
  if (!before || !/^\d{4}-\d{2}-\d{2}$/.test(before)) {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
  const { digests, nextBefore } = await getDigestsBefore(before);
  return NextResponse.json({ items: mergeDigests(digests), nextBefore });
}
```

- [ ] **Step 3: Verify against the dev server**

Run: `npm run dev` (background), then:

```bash
curl -s "http://localhost:3000/api/feed?before=2026-06-08" | head -c 300
curl -s "http://localhost:3000/api/feed?before=bogus" -o /dev/null -w "%{http_code}\n"
curl -s "http://localhost:3000/api/votes" | head -c 200
```

Expected: items JSON from 2026-06-07 and older; `400`; `{"counts":{...}}` (or `{"counts":{}}` without Supabase env).

- [ ] **Step 4: Commit**

```bash
git add src/app/api/votes/route.ts src/app/api/feed/route.ts
git commit -m "feat(web): add votes and feed pagination API routes"
```

---

### Task 7: `VoteRail`, `SaveButton`, `ShareButton` (client)

**Files:**
- Create: `src/components/VoteRail.tsx`
- Create: `src/components/SaveButton.tsx`
- Create: `src/components/ShareButton.tsx`

- [ ] **Step 1: Create `src/components/VoteRail.tsx`**

Note: `initialNet` is the server-side aggregate (may already include this browser's historical vote), so optimistic display uses a session `delta`, not the stored vote.

```tsx
"use client";

import { useEffect, useState } from "react";
import { getVote, setVote } from "@/lib/local";

export function VoteRail({
  itemKey,
  initialNet,
}: {
  itemKey: string;
  initialNet: number;
}) {
  const [mine, setMine] = useState<1 | -1 | 0>(0);
  const [delta, setDelta] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMine(getVote(itemKey));
  }, [itemKey]);

  async function vote(next: 1 | -1) {
    if (busy) return;
    const prevMine = mine;
    const prevDelta = delta;
    const value = mine === next ? 0 : next;
    setMine(value);
    setVote(itemKey, value);
    setDelta(delta + value - prevMine);
    if (value === 0) return; // clearing is local-only, like ItemActions did
    setBusy(true);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemKey, signal: value }),
      });
      if (!res.ok && res.status !== 503) {
        setMine(prevMine);
        setVote(itemKey, prevMine);
        setDelta(prevDelta);
      }
    } catch {
      setMine(prevMine);
      setVote(itemKey, prevMine);
      setDelta(prevDelta);
    } finally {
      setBusy(false);
    }
  }

  const btn = "leading-none transition-colors disabled:opacity-50";
  return (
    <div className="flex w-8 shrink-0 flex-col items-center gap-0.5 pt-0.5 font-mono text-xs">
      <button
        type="button"
        aria-label="Upvote"
        disabled={busy}
        onClick={() => vote(1)}
        className={`${btn} ${mine === 1 ? "text-amber-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▲
      </button>
      <span className="font-semibold text-neutral-300">{initialNet + delta}</span>
      <button
        type="button"
        aria-label="Downvote"
        disabled={busy}
        onClick={() => vote(-1)}
        className={`${btn} ${mine === -1 ? "text-rose-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▼
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Create `src/components/SaveButton.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { getSaves, toggleSave, type SavedItem } from "@/lib/local";

export function SaveButton({ item }: { item: SavedItem }) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSaved(getSaves().some((s) => s.key === item.key));
  }, [item.key]);

  return (
    <button
      type="button"
      aria-label={saved ? "Unsave" : "Save"}
      onClick={() => setSaved(toggleSave(item))}
      className={`font-mono text-xs transition-colors ${saved ? "text-amber-400" : "text-neutral-500 hover:text-neutral-300"}`}
    >
      {saved ? "✓ saved" : "save"}
    </button>
  );
}
```

- [ ] **Step 3: Create `src/components/ShareButton.tsx`**

```tsx
"use client";

import { useState } from "react";

export function ShareButton({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ url, title });
        return;
      } catch {
        // user cancelled or unsupported payload — fall through to copy
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked — nothing sensible to do
    }
  }

  return (
    <button
      type="button"
      aria-label="Share"
      onClick={share}
      className="font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"
    >
      {copied ? "copied!" : "share"}
    </button>
  );
}
```

- [ ] **Step 4: Verify compile + tests**

Run: `npx tsc --noEmit && npm test`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/components/VoteRail.tsx src/components/SaveButton.tsx src/components/ShareButton.tsx
git commit -m "feat(web): add vote rail, save, and share controls"
```

---

### Task 8: `PostCard` (rich) + `PostRow` (compact)

**Files:**
- Create: `src/components/PostCard.tsx`
- Create: `src/components/PostRow.tsx`

- [ ] **Step 1: Create `src/components/PostCard.tsx`**

```tsx
import { itemKey, type FeedItem } from "@/lib/feed";
import { SaveButton } from "./SaveButton";
import { ShareButton } from "./ShareButton";
import { SourceBadge } from "./SourceBadge";
import { VoteRail } from "./VoteRail";

export function postDate(item: FeedItem): string {
  return (item.published_at || item.digestDate).slice(0, 10);
}

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function PostCard({ item, initialNet }: { item: FeedItem; initialNet: number }) {
  const key = itemKey(item);
  return (
    <article className="flex gap-3 rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700">
      <VoteRail itemKey={key} initialNet={initialNet} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.topic && (
            <a
              href={`/topics/${item.topic}`}
              className="font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
            >
              t/{item.topic}
            </a>
          )}
          <SourceBadge source={item.source} />
          <span className="font-mono text-xs text-neutral-500">{domain(item.url)}</span>
          <time className="font-mono text-xs text-neutral-500">{postDate(item)}</time>
        </div>
        <h2 className="mt-1.5 text-base font-semibold leading-snug tracking-tight">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="decoration-amber-400/60 underline-offset-4 hover:underline"
          >
            {item.title}
          </a>
        </h2>
        <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-neutral-400">
          {item.summary ?? item.abstract}
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-4">
          {item.source === "hackernews" && (
            <a
              href={`https://news.ycombinator.com/item?id=${item.id}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"
            >
              discuss
            </a>
          )}
          <SaveButton
            item={{ key, title: item.title, url: item.url, source: item.source, date: postDate(item) }}
          />
          <ShareButton url={item.url} title={item.title} />
          {item.repro_difficulty && (
            <span className="font-mono text-xs text-amber-500">repro: {item.repro_difficulty}</span>
          )}
          {item.has_code && <span className="font-mono text-xs text-emerald-500">code</span>}
        </div>
      </div>
    </article>
  );
}
```

- [ ] **Step 2: Create `src/components/PostRow.tsx`**

```tsx
import { itemKey, type FeedItem } from "@/lib/feed";
import { domain, postDate } from "./PostCard";
import { SaveButton } from "./SaveButton";
import { SourceBadge } from "./SourceBadge";
import { VoteRail } from "./VoteRail";

export function PostRow({ item, initialNet }: { item: FeedItem; initialNet: number }) {
  const key = itemKey(item);
  return (
    <article className="flex gap-3 border-b border-neutral-800/80 py-2.5">
      <VoteRail itemKey={key} initialNet={initialNet} />
      <div className="min-w-0 flex-1">
        <h2 className="text-sm font-semibold leading-snug">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="decoration-amber-400/60 underline-offset-4 hover:underline"
          >
            {item.title}
          </a>{" "}
          <span className="font-mono text-xs font-normal text-neutral-500">({domain(item.url)})</span>
        </h2>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.topic && (
            <a
              href={`/topics/${item.topic}`}
              className="font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
            >
              t/{item.topic}
            </a>
          )}
          <SourceBadge source={item.source} />
          <time className="font-mono text-xs text-neutral-500">{postDate(item)}</time>
          <SaveButton
            item={{ key, title: item.title, url: item.url, source: item.source, date: postDate(item) }}
          />
        </div>
      </div>
    </article>
  );
}
```

- [ ] **Step 3: Verify compile**

Run: `npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add src/components/PostCard.tsx src/components/PostRow.tsx
git commit -m "feat(web): add rich post card and compact post row"
```

---

### Task 9: `Feed` client component (tabs, density toggle, infinite scroll)

**Files:**
- Create: `src/components/Feed.tsx`

- [ ] **Step 1: Create `src/components/Feed.tsx`**

`nowMs` comes from the server page so SSR and hydration sort identically (no `Date.now()` drift → no hydration mismatch).

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { itemKey, sortFeed, type FeedItem, type FeedSort, type VoteCounts } from "@/lib/feed";
import { getDensity, setDensity, type Density } from "@/lib/local";
import { PostCard } from "./PostCard";
import { PostRow } from "./PostRow";

const TABS: { id: FeedSort; label: string }[] = [
  { id: "hot", label: "Hot" },
  { id: "new", label: "New" },
  { id: "foryou", label: "For You" },
  { id: "top", label: "Top" },
];

export function Feed({
  initialItems,
  votes,
  initialBefore,
  nowMs,
}: {
  initialItems: FeedItem[];
  votes: VoteCounts;
  initialBefore: string | null;
  nowMs: number;
}) {
  const [sort, setSort] = useState<FeedSort>("hot");
  const [density, setDens] = useState<Density>("cards");
  const [pool, setPool] = useState<FeedItem[]>(initialItems);
  const [before, setBefore] = useState<string | null>(initialBefore);
  const [loading, setLoading] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => setDens(getDensity()), []);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || !before) return;
    const io = new IntersectionObserver(async (entries) => {
      if (!entries[0].isIntersecting || loading) return;
      setLoading(true);
      try {
        const res = await fetch(`/api/feed?before=${before}`);
        if (!res.ok) {
          setBefore(null);
          return;
        }
        const data = (await res.json()) as { items: FeedItem[]; nextBefore: string | null };
        setPool((p) => {
          const seen = new Set(p.map(itemKey));
          return [...p, ...data.items.filter((i) => !seen.has(itemKey(i)))];
        });
        setBefore(data.nextBefore);
      } catch {
        setBefore(null);
      } finally {
        setLoading(false);
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, [before, loading]);

  function pickDensity(d: Density) {
    setDens(d);
    setDensity(d);
  }

  const items = sortFeed(pool, sort, votes, new Date(nowMs));
  const toggle = (active: boolean) =>
    `px-2.5 py-1 font-mono text-xs transition-colors ${active ? "bg-neutral-800 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`;

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <div className="flex gap-1" role="tablist" aria-label="Sort feed">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={sort === t.id}
              onClick={() => setSort(t.id)}
              className={`rounded-full px-3 py-1 font-mono text-xs transition-colors ${
                sort === t.id
                  ? "bg-amber-500 font-bold text-neutral-950"
                  : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex overflow-hidden rounded-md border border-neutral-800">
          <button type="button" onClick={() => pickDensity("cards")} className={toggle(density === "cards")}>
            cards
          </button>
          <button type="button" onClick={() => pickDensity("compact")} className={toggle(density === "compact")}>
            compact
          </button>
        </div>
      </div>

      {sort === "top" && items.length === 0 ? (
        <p className="py-8 text-sm text-neutral-500">Nothing voted up in the last 7 days yet.</p>
      ) : density === "cards" ? (
        <div className="space-y-3">
          {items.map((item) => (
            <PostCard key={itemKey(item)} item={item} initialNet={votes[itemKey(item)] ?? 0} />
          ))}
        </div>
      ) : (
        <div>
          {items.map((item) => (
            <PostRow key={itemKey(item)} item={item} initialNet={votes[itemKey(item)] ?? 0} />
          ))}
        </div>
      )}

      <div ref={sentinel} className="h-8" aria-hidden="true" />
      {loading && <p className="pb-6 text-center font-mono text-xs text-neutral-500">loading…</p>}
    </div>
  );
}
```

- [ ] **Step 2: Verify compile + tests**

Run: `npx tsc --noEmit && npm test`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add src/components/Feed.tsx
git commit -m "feat(web): add Feed with sort tabs, density toggle, infinite scroll"
```

---

### Task 10: Sidebar (`WeeklyCard` pinned synthesis, trending, saves)

**Files:**
- Create: `src/components/Sidebar.tsx` (server component)
- Create: `src/components/SavesCard.tsx` (client)

- [ ] **Step 1: Create `src/components/SavesCard.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { getSaves } from "@/lib/local";

export function SavesCard() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    setCount(getSaves().length);
  }, []);

  return (
    <a
      href="/saved"
      className="block rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700"
    >
      <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">your saves</p>
      <p className="mt-1.5 text-sm text-neutral-300">
        {count} item{count === 1 ? "" : "s"}
      </p>
      <p className="mt-1 font-mono text-[10px] text-neutral-600">stored locally · no account needed</p>
    </a>
  );
}
```

- [ ] **Step 2: Create `src/components/Sidebar.tsx`**

```tsx
import type { Digest } from "@/lib/types";
import { getSyntheses } from "@/lib/synthesis";
import { trendingTopics } from "@/lib/trending";
import { SavesCard } from "./SavesCard";

export async function Sidebar({
  latest,
  previous,
}: {
  latest: Digest | null;
  previous: Digest | null;
}) {
  const [synthesis] = await getSyntheses();
  const trending = trendingTopics(latest, previous);

  return (
    <aside className="space-y-4">
      {synthesis && (
        <a
          href={`/synthesis/${synthesis.week}`}
          className="block rounded-xl border border-amber-500/30 bg-neutral-900/40 p-4 transition-colors hover:border-amber-500/60"
        >
          <p className="font-mono text-[10px] uppercase tracking-widest text-amber-500">📌 this week</p>
          <p className="mt-1.5 text-sm font-semibold leading-snug">{synthesis.title}</p>
          <p className="mt-1 font-mono text-[10px] text-neutral-500">weekly synthesis · {synthesis.date}</p>
        </a>
      )}

      {trending.length > 0 && (
        <div className="rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">trending topics</p>
          <ul className="mt-2 space-y-1.5">
            {trending.map((t) => (
              <li key={t.tag} className="flex items-baseline justify-between gap-2">
                <a
                  href={`/topics/${t.tag}`}
                  className="truncate font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
                >
                  t/{t.tag}
                </a>
                <span className="font-mono text-[10px] text-neutral-500">
                  {t.count}
                  {t.delta > 0 ? ` ↑${t.delta}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <SavesCard />
    </aside>
  );
}
```

- [ ] **Step 3: Verify compile**

Run: `npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add src/components/Sidebar.tsx src/components/SavesCard.tsx
git commit -m "feat(web): add sidebar with pinned weekly, trending, saves"
```

---

### Task 11: Home page rewrite + nav/branding + `/topics` index

**Files:**
- Rewrite: `src/app/page.tsx`
- Modify: `src/app/layout.tsx` (nav links, tagline, metadata)
- Create: `src/app/topics/page.tsx`

- [ ] **Step 1: Rewrite `src/app/page.tsx`**

Replace the entire file:

```tsx
import { Feed } from "@/components/Feed";
import { Sidebar } from "@/components/Sidebar";
import { getIndex, getRecentDigests } from "@/lib/content";
import { mergeDigests, sortFeed } from "@/lib/feed";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 3600; // ISR: rebuild hourly

const POOL_DIGESTS = 7;

export default async function HomePage() {
  const [index, digests, votes] = await Promise.all([
    getIndex(),
    getRecentDigests(POOL_DIGESTS),
    getVoteCounts(),
  ]);
  const nowMs = Date.now();
  const pool = mergeDigests(digests);
  const initialItems = sortFeed(pool, "hot", votes, new Date(nowMs));
  const initialBefore =
    index.length > POOL_DIGESTS && digests.length > 0
      ? digests[digests.length - 1].date
      : null;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {initialItems.length === 0 ? (
        <p className="text-neutral-500">No posts yet. The pipeline runs daily.</p>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px]">
          <Feed
            initialItems={initialItems}
            votes={votes}
            initialBefore={initialBefore}
            nowMs={nowMs}
          />
          <Sidebar latest={digests[0] ?? null} previous={digests[1] ?? null} />
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Update `src/app/layout.tsx`**

Change the metadata description:

```ts
export const metadata: Metadata = {
  title: "Throughline",
  description: "The tech wire, ranked daily — AI research & engineering, voted and ranked.",
};
```

Change the tagline span text from `the daily AI throughline` to `the tech wire, ranked daily`.

Widen the nav container to match the board page: in the nav's inner `div`, change `max-w-3xl` to `max-w-5xl`.

Replace the nav links block (the `div` with `archive`/`synthesis`/`about`) with:

```tsx
<div className="flex gap-6 font-mono text-xs text-neutral-400">
  <a href="/topics" className="transition-colors hover:text-neutral-100">
    topics
  </a>
  <a href="/archive" className="transition-colors hover:text-neutral-100">
    archive
  </a>
  <a href="/synthesis" className="transition-colors hover:text-neutral-100">
    weekly
  </a>
  <a href="/about" className="transition-colors hover:text-neutral-100">
    about
  </a>
</div>
```

- [ ] **Step 3: Create `src/app/topics/page.tsx`**

```tsx
import { getLatestTopics } from "@/lib/content";

export const revalidate = 3600;

export default async function TopicsPage() {
  const topics = await getLatestTopics();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Topics</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">communities from today&rsquo;s board</p>
      {topics.length === 0 ? (
        <p className="mt-6 text-neutral-500">No topics yet.</p>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {topics.map((t) => (
            <a
              key={t.tag}
              href={`/topics/${t.tag}`}
              className="rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700"
            >
              <p className="font-mono text-xs text-sky-400">t/{t.tag}</p>
              <p className="mt-1 text-sm font-semibold">{t.label}</p>
              <p className="mt-1 font-mono text-[10px] text-neutral-500">{t.item_ids.length} posts</p>
            </a>
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Verify in dev**

Run: `npm run dev`, open http://localhost:3000 — board renders with tabs, vote rails, sidebar; `/topics` lists communities; nav shows topics·archive·weekly·about.

- [ ] **Step 5: Commit**

```bash
git add src/app/page.tsx src/app/layout.tsx src/app/topics/page.tsx
git commit -m "feat(web): replace digest home with social board and topics index"
```

---

### Task 12: t/ topic page restyle + `/saved` page

**Files:**
- Rewrite: `src/app/topics/[tag]/page.tsx`
- Create: `src/app/saved/page.tsx`

- [ ] **Step 1: Rewrite `src/app/topics/[tag]/page.tsx`**

Replace the entire file (drops ItemCard/read-state; uses Feed scoped to the topic, no pagination):

```tsx
import { notFound } from "next/navigation";
import { Feed } from "@/components/Feed";
import { getLatestDigest, getLatestTopics, getTopic } from "@/lib/content";
import type { FeedItem } from "@/lib/feed";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 3600;

export async function generateStaticParams() {
  const topics = await getLatestTopics();
  return topics.map((t) => ({ tag: t.tag }));
}

export default async function TopicPage({
  params,
}: {
  params: Promise<{ tag: string }>;
}) {
  const { tag } = await params;
  const [topic, digest, votes] = await Promise.all([
    getTopic(tag),
    getLatestDigest(),
    getVoteCounts(),
  ]);
  if (!topic || !digest) notFound();
  const items: FeedItem[] = topic.items.map((i) => ({ ...i, digestDate: digest.date }));

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <a href="/topics" className="font-mono text-xs text-neutral-500 hover:text-neutral-300">
        ← all topics
      </a>
      <h1 className="mt-2 text-2xl font-bold">
        <span className="font-mono text-lg text-sky-400">t/{tag}</span> · {topic.label}
      </h1>
      <p className="mb-6 mt-1 font-mono text-xs text-neutral-500">{items.length} posts</p>
      <Feed initialItems={items} votes={votes} initialBefore={null} nowMs={Date.now()} />
    </main>
  );
}
```

- [ ] **Step 2: Create `src/app/saved/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { getSaves, toggleSave, type SavedItem } from "@/lib/local";

export default function SavedPage() {
  const [saves, setSaves] = useState<SavedItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setSaves(getSaves());
    setLoaded(true);
  }, []);

  function unsave(item: SavedItem) {
    toggleSave(item);
    setSaves(getSaves());
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Saved</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">stored in this browser only</p>
      {loaded && saves.length === 0 ? (
        <p className="mt-6 text-neutral-500">Nothing saved yet. Hit “save” on any post.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {saves.map((s) => (
            <li key={s.key} className="flex items-baseline justify-between gap-4 py-3">
              <div className="min-w-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-semibold decoration-amber-400/60 underline-offset-4 hover:underline"
                >
                  {s.title}
                </a>
                <p className="mt-0.5 font-mono text-[10px] text-neutral-500">
                  {s.source} · {s.date}
                </p>
              </div>
              <button
                type="button"
                onClick={() => unsave(s)}
                className="shrink-0 font-mono text-xs text-neutral-500 transition-colors hover:text-rose-400"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Verify in dev**

`/topics/<existing-tag>` renders scoped board; saving a post on `/` then visiting `/saved` shows it; remove works.

- [ ] **Step 4: Commit**

```bash
git add src/app/topics/[tag]/page.tsx src/app/saved/page.tsx
git commit -m "feat(web): restyle topic pages as t/ communities and add saved page"
```

---

### Task 13: Retire digest-era components

`ItemCard`/`ItemActions` are no longer imported (home + topic pages rewritten). Read-state UI has no place in the board paradigm — remove its API and lib too. The Supabase `read_state` table stays (harmless, no migration).

**Files:**
- Delete: `src/components/ItemCard.tsx`, `src/components/ItemActions.tsx`, `src/lib/feedback.ts`, `src/app/api/read/route.ts`

- [ ] **Step 1: Confirm nothing imports them**

Run: `grep -rn "ItemCard\|ItemActions\|getReadStates\|api/read" src/`
Expected: no matches outside the four files being deleted.

- [ ] **Step 2: Delete**

```bash
git rm src/components/ItemCard.tsx src/components/ItemActions.tsx src/lib/feedback.ts src/app/api/read/route.ts
```

- [ ] **Step 3: Verify**

Run: `npx tsc --noEmit && npm test`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(web): retire digest-era item card and read-state"
```

---

### Task 14: Full verification + docs touch-up

**Files:**
- Modify: `README.md` (screenshots/copy mention digest hub — update the elevator pitch to the board)

- [ ] **Step 1: Run everything**

```bash
npm run lint
npm test
npx tsc --noEmit
npm run build
.venv/bin/python -m pytest -q
```

Expected: lint clean, all Vitest suites pass, build succeeds, **46/46 pytest pass** (pipeline untouched).

- [ ] **Step 2: Live walkthrough (Playwright or manual)**

With `npm run dev`:
1. `/` — Hot tab active, posts show vote rails with counts.
2. Upvote a post → count bumps instantly; check Supabase `feedback` for the new row (or 503-tolerant if env missing); reload → ▲ still highlighted (localStorage guard).
3. Switch tabs New / For You / Top — order changes, no errors.
4. Toggle compact → rows; reload → preference persisted.
5. Scroll to bottom → older items append (sentinel fetch), until `nextBefore` exhausts.
6. Save a post → `/saved` lists it; remove works.
7. Sidebar: weekly card links to synthesis (if any exists locally), trending t/ links work, saves count correct.
8. `/topics` and `/topics/[tag]` render; mobile width (~390px): sidebar drops below feed, layout sane.

- [ ] **Step 3: Update `README.md` pitch**

Rewrite the opening description: Throughline is a self-updating social board for AI/tech — sources post daily (arXiv, HN, GitHub, news), Claude summarizes and labels, anonymous votes rank Hot/Top and feed the personalization ranker. Keep pipeline/architecture sections; adjust feature list (tabs, votes, saves, density toggle, t/ pages, weekly pin).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: reposition README for the social board"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```

Vercel auto-deploys from main. Spot-check production URL after deploy.
