# Public-Launch Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rate-limit and validate the write/scan APIs, add security headers, full SEO/OG surface, and branded error pages before public launch.

**Architecture:** A pure sliding-window limiter (`src/lib/ratelimit.ts`, injectable clock) and an `item_id` validator (`src/lib/validate.ts`) — both vitest-covered — wire into the two API routes as module-level singletons. Headers go in `next.config.ts`. SEO is all Next conventions: layout metadata, `opengraph-image.tsx` via ImageResponse, `robots.ts`, `sitemap.ts`, per-page titles. 404/error pages match board styling.

**Tech Stack:** Next.js 16 App Router · TS strict · Vitest · next/og ImageResponse.

**Spec:** `docs/superpowers/specs/2026-06-11-public-hardening-design.md`

**Commit rules (repo non-negotiable):** plain `git commit`, exact messages, NO Co-Authored-By/Claude trailer.

**Baselines:** vitest 26, pytest 67, lint 0, tsc clean. `/api/feedback` currently validates `typeof item_id === "string" && item_id` + `signal === 1|-1`. `/api/search` validates q length ≤100. `next.config.ts` is empty. `/saved` is a client page — it CANNOT export `metadata` (skip it; documented). Base URL: `https://throughline-theta.vercel.app`.

---

### Task 1: Rate limiter + validator libs (TDD)

**Files:**
- Create: `src/lib/ratelimit.ts`, `src/lib/validate.ts`
- Test: `tests/web/ratelimit.test.ts`, `tests/web/validate.test.ts`

- [ ] **Step 1: Write failing tests.**

`tests/web/ratelimit.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { clientIp, createRateLimiter } from "@/lib/ratelimit";

describe("createRateLimiter", () => {
  it("allows up to limit within window, then blocks", () => {
    let t = 0;
    const rl = createRateLimiter(2, 1000, () => t);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
  });

  it("re-allows after the window slides past old hits", () => {
    let t = 0;
    const rl = createRateLimiter(2, 1000, () => t);
    rl.allow("a");
    rl.allow("a");
    t = 1001;
    expect(rl.allow("a")).toBe(true);
  });

  it("isolates keys", () => {
    let t = 0;
    const rl = createRateLimiter(1, 1000, () => t);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
    expect(rl.allow("b")).toBe(true);
  });
});

describe("clientIp", () => {
  it("takes the first x-forwarded-for hop", () => {
    const req = new Request("http://x", {
      headers: { "x-forwarded-for": "1.2.3.4, 5.6.7.8" },
    });
    expect(clientIp(req)).toBe("1.2.3.4");
  });

  it("falls back to x-real-ip then unknown", () => {
    expect(clientIp(new Request("http://x", { headers: { "x-real-ip": "9.9.9.9" } }))).toBe("9.9.9.9");
    expect(clientIp(new Request("http://x"))).toBe("unknown");
  });
});
```

`tests/web/validate.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isValidItemId } from "@/lib/validate";

describe("isValidItemId", () => {
  it("accepts real key shapes from all five sources", () => {
    for (const id of [
      "arxiv:2606.07515",
      "hackernews:hn:48443258",
      "github:gh:owner/repo-name.py",
      "blog:blog:2be94cf79940",
      "news:news:abc123def456",
    ]) {
      expect(isValidItemId(id)).toBe(true);
    }
  });

  it("rejects junk", () => {
    for (const id of [
      "",
      "noprefix",
      "arxiv:has space",
      "UPPER:abc",
      "<script>alert(1)</script>",
      "arxiv:" + "x".repeat(120),
    ]) {
      expect(isValidItemId(id)).toBe(false);
    }
  });
});
```

- [ ] **Step 2: Run `npm test`** — FAIL (modules unresolved).

- [ ] **Step 3: Implement.**

`src/lib/ratelimit.ts`:

```ts
export type RateLimiter = { allow(key: string): boolean };

const MAX_KEYS = 10_000;

/** Sliding-window in-memory limiter. Per-instance only (Fluid Compute reuses
 *  instances, so this is a real but not distributed guard). */
export function createRateLimiter(
  limit: number,
  windowMs: number,
  now: () => number = Date.now,
): RateLimiter {
  const hits = new Map<string, number[]>();
  return {
    allow(key: string): boolean {
      const t = now();
      const cutoff = t - windowMs;
      if (hits.size > MAX_KEYS) {
        for (const [k, ts] of hits) {
          if (ts[ts.length - 1] <= cutoff) hits.delete(k);
        }
      }
      const ts = (hits.get(key) ?? []).filter((x) => x > cutoff);
      if (ts.length >= limit) {
        hits.set(key, ts);
        return false;
      }
      ts.push(t);
      hits.set(key, ts);
      return true;
    },
  };
}

export function clientIp(request: Request): string {
  const fwd = request.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return request.headers.get("x-real-ip") ?? "unknown";
}
```

`src/lib/validate.ts`:

```ts
/** source-prefixed item key, e.g. "hackernews:hn:48443258". */
export const ITEM_ID_RE = /^[a-z]+:[A-Za-z0-9._:/-]+$/;

export function isValidItemId(s: string): boolean {
  return s.length > 0 && s.length <= 120 && ITEM_ID_RE.test(s);
}
```

- [ ] **Step 4: Run `npm test`** — all pass (33 = 26 + 7). `npx tsc --noEmit` clean.

- [ ] **Step 5: Commit**

```bash
git add src/lib/ratelimit.ts src/lib/validate.ts tests/web/ratelimit.test.ts tests/web/validate.test.ts
git commit -m "feat(web): add rate limiter and item id validator"
```

---

### Task 2: Wire limits + validation into API routes

**Files:**
- Modify: `src/app/api/feedback/route.ts`
- Modify: `src/app/api/search/route.ts`

- [ ] **Step 1: Rewrite `src/app/api/feedback/route.ts`:**

```ts
import { NextResponse } from "next/server";
import { clientIp, createRateLimiter } from "@/lib/ratelimit";
import { getServiceClient } from "@/lib/supabase";
import { isValidItemId } from "@/lib/validate";

const limiter = createRateLimiter(10, 60_000);

export async function POST(request: Request) {
  if (!limiter.allow(clientIp(request))) {
    return NextResponse.json(
      { error: "rate limited" },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const { item_id, signal } = (body ?? {}) as {
    item_id?: unknown;
    signal?: unknown;
  };
  if (
    typeof item_id !== "string" ||
    !isValidItemId(item_id) ||
    (signal !== 1 && signal !== -1)
  ) {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }

  const client = getServiceClient();
  if (!client) {
    return NextResponse.json({ error: "supabase not configured" }, { status: 503 });
  }

  const { error } = await client.from("feedback").insert({ item_id, signal });
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 2: Add limiter to `src/app/api/search/route.ts`.** Add imports `import { clientIp, createRateLimiter } from "@/lib/ratelimit";`, module-level `const limiter = createRateLimiter(30, 60_000);`, and as the FIRST statement inside `GET`:

```ts
  if (!limiter.allow(clientIp(request))) {
    return NextResponse.json(
      { error: "rate limited" },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  }
```

- [ ] **Step 3: Verify live.** `npx tsc --noEmit` clean; `npm test` 33. Dev server (background, kill after):

```bash
for i in $(seq 1 11); do curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:3000/api/feedback -H "content-type: application/json" -d '{"item_id":"arxiv:test123","signal":1}'; done; echo
curl -s -X POST http://localhost:3000/api/feedback -H "content-type: application/json" -d '{"item_id":"<script>","signal":1}' -o /dev/null -w "%{http_code}\n"
```

Expected: ten non-429 codes (503 without Supabase env is fine, 200 with) then `429`; second command `400`.

- [ ] **Step 4: Commit**

```bash
git add src/app/api/feedback/route.ts src/app/api/search/route.ts
git commit -m "feat(web): rate limit and validate public API routes"
```

---

### Task 3: Security headers

**Files:**
- Modify: `next.config.ts`

- [ ] **Step 1: Replace `next.config.ts` contents:**

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

(No CSP — App Router needs nonce middleware for a correct one; documented in the spec as a follow-up.)

- [ ] **Step 2: Verify.** `npm run build` succeeds. Dev server: `curl -sI http://localhost:3000/ | grep -i "x-content-type-options\|x-frame-options\|referrer-policy\|permissions-policy"` → all four present. Kill server.

- [ ] **Step 3: Commit**

```bash
git add next.config.ts
git commit -m "feat(web): add security headers"
```

---

### Task 4: SEO/OG surface

**Files:**
- Modify: `src/app/layout.tsx` (metadata only)
- Create: `src/app/opengraph-image.tsx`, `src/app/robots.ts`, `src/app/sitemap.ts`
- Modify: `src/app/topics/page.tsx`, `src/app/archive/page.tsx`, `src/app/search/page.tsx` (titles)

- [ ] **Step 1: layout metadata.** Replace the `metadata` export in `src/app/layout.tsx` with:

```ts
const DESCRIPTION =
  "The tech wire, ranked daily — AI research & engineering, voted and ranked.";

export const metadata: Metadata = {
  metadataBase: new URL("https://throughline-theta.vercel.app"),
  title: "Throughline",
  description: DESCRIPTION,
  openGraph: {
    title: "Throughline",
    description: DESCRIPTION,
    siteName: "Throughline",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Throughline",
    description: DESCRIPTION,
  },
};
```

- [ ] **Step 2: Create `src/app/opengraph-image.tsx`:**

```tsx
import { ImageResponse } from "next/og";

export const alt = "Throughline — the tech wire, ranked daily";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0a0a0a",
        }}
      >
        <div style={{ display: "flex", fontSize: 96, fontWeight: 700 }}>
          <span style={{ color: "#fafafa" }}>through</span>
          <span style={{ color: "#f59e0b" }}>line</span>
        </div>
        <div
          style={{
            marginTop: 24,
            fontSize: 30,
            color: "#f59e0b",
            textTransform: "uppercase",
            letterSpacing: 10,
          }}
        >
          the tech wire, ranked daily
        </div>
      </div>
    ),
    size,
  );
}
```

- [ ] **Step 3: Create `src/app/robots.ts`:**

```ts
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: "https://throughline-theta.vercel.app/sitemap.xml",
  };
}
```

- [ ] **Step 4: Create `src/app/sitemap.ts`:**

```ts
import type { MetadataRoute } from "next";
import { getLatestTopics } from "@/lib/content";

const BASE = "https://throughline-theta.vercel.app";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const topics = await getLatestTopics();
  const now = new Date();
  return [
    { url: `${BASE}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${BASE}/topics`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE}/archive`, lastModified: now, changeFrequency: "daily", priority: 0.5 },
    { url: `${BASE}/synthesis`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.3 },
    ...topics.map((t) => ({
      url: `${BASE}/topics/${t.tag}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];
}
```

- [ ] **Step 5: Page titles.**
- `src/app/topics/page.tsx`: add `export const metadata = { title: "Topics — Throughline" };` after the imports.
- `src/app/archive/page.tsx`: add `export const metadata = { title: "Archive — Throughline" };` after the imports.
- `src/app/search/page.tsx`: add after the imports:

```ts
export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();
  return { title: query ? `“${query}” — Throughline` : "Search — Throughline" };
}
```

(`/saved` is a client page — cannot export metadata; intentionally skipped.)

- [ ] **Step 6: Verify.** `npx tsc --noEmit` clean; `npm run lint` 0; dev server: `/robots.txt` 200 + mentions sitemap; `/sitemap.xml` 200 + contains `/topics/`; `/opengraph-image` 200 `image/png`; `curl -s http://localhost:3000/ | grep -o 'og:image' | head -1` present. Kill server.

- [ ] **Step 7: Commit**

```bash
git add src/app/layout.tsx src/app/opengraph-image.tsx src/app/robots.ts src/app/sitemap.ts src/app/topics/page.tsx src/app/archive/page.tsx src/app/search/page.tsx
git commit -m "feat(web): OG image, robots, sitemap, and page metadata"
```

---

### Task 5: Error pages

**Files:**
- Create: `src/app/not-found.tsx`, `src/app/error.tsx`

- [ ] **Step 1: Create `src/app/not-found.tsx`:**

```tsx
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 px-6 py-24">
      <p className="font-mono text-6xl font-bold text-amber-400">404</p>
      <p className="text-neutral-400">this thread doesn&rsquo;t exist.</p>
      <Link
        href="/"
        className="font-mono text-xs text-neutral-500 underline-offset-4 transition-colors hover:text-neutral-200 hover:underline"
      >
        ← back to the board
      </Link>
    </main>
  );
}
```

- [ ] **Step 2: Create `src/app/error.tsx`:**

```tsx
"use client";

import Link from "next/link";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 px-6 py-24">
      <p className="font-mono text-6xl font-bold text-rose-400">500</p>
      <p className="text-neutral-400">something broke. it&rsquo;s not you.</p>
      <div className="flex gap-4">
        <button
          type="button"
          onClick={reset}
          className="font-mono text-xs text-amber-400 underline-offset-4 hover:underline"
        >
          try again
        </button>
        <Link
          href="/"
          className="font-mono text-xs text-neutral-500 underline-offset-4 transition-colors hover:text-neutral-200 hover:underline"
        >
          ← back to the board
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Verify.** `npx tsc --noEmit`; `npm run lint` 0; dev server: `/topics/nonexistent-tag` renders branded 404 (curl body contains "this thread doesn"). Kill server.

- [ ] **Step 4: Commit**

```bash
git add src/app/not-found.tsx src/app/error.tsx
git commit -m "feat(web): branded 404 and error pages"
```

---

### Task 6: Full verification

- [ ] **Step 1:** `npm run lint` 0; `npm test` 33; `npx tsc --noEmit` clean; `npm run build` succeeds; `.venv/bin/python -m pytest -q` 67.
- [ ] **Step 2:** Dev smoke recap: 429 on 11th vote, 400 on junk item_id, four security headers on `/`, robots/sitemap/og-image 200, branded 404.
- [ ] **Step 3:** Hand to controller: push, verify production headers + robots + og:image + a 429 burst test against prod `/api/search`.
