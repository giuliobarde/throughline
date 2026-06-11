# Public-Launch Hardening — Design Spec (P4)

**Date:** 2026-06-11
**Status:** Approved
**Series:** P4 of 4 (final pre-launch wave)

## Problem

The site is about to be advertised publicly. Today: `POST /api/feedback` accepts unlimited anonymous writes (vote/row flooding), `GET /api/search` scans the whole archive per request with no throttle, no security headers, no OG/social cards, no robots/sitemap, default unstyled 404/error pages.

## 1. Rate limiting (in-memory, per instance)

Chosen approach: in-memory sliding window. Zero dependencies; Vercel Fluid Compute reuses function instances across requests, so the limiter has real effect. Distributed enforcement (WAF rules or Upstash) is a documented optional upgrade, not in this pass.

### `src/lib/ratelimit.ts` (pure core + tiny stateful wrapper, vitest-covered)

```ts
export type RateLimiter = { allow(key: string): boolean };
export function createRateLimiter(limit: number, windowMs: number, now: () => number = Date.now): RateLimiter
```

- Sliding window: per key, keep timestamps within `windowMs`; `allow` returns false once `limit` reached; old entries pruned on access; whole-map prune when size exceeds 10k keys (drop expired).
- Injectable `now` for tests.

### `src/lib/clientip.ts` helper (or inline in routes)

`clientIp(request: Request): string` — first hop of `x-forwarded-for`, else `x-real-ip`, else `"unknown"`.

### Route wiring

- `POST /api/feedback`: module-level `createRateLimiter(10, 60_000)`; over limit → `429 {error:"rate limited"}` with `Retry-After: 60`.
- `GET /api/search`: module-level `createRateLimiter(30, 60_000)`; over limit → 429 + `Retry-After: 60`.
- Clients already treat non-OK as failure (VoteRail reverts, SearchBox stays quiet) — no client changes.

### Input tightening (`/api/feedback`)

`item_id` must be ≤120 chars AND match `/^[a-z]+:[A-Za-z0-9._:\/-]+$/` (source prefix + key chars; covers `arxiv:2606.07515`, `hackernews:hn:48443258`, `github:gh:owner/repo`, `blog:blog:sha`, `news:news:sha`). Reject → 400. Stops junk-row flooding beyond the rate cap.

## 2. Security headers (`next.config.ts`)

```ts
async headers() {
  return [{
    source: "/(.*)",
    headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ],
  }];
}
```

**Deliberately no CSP**: App Router inline scripts require nonce middleware for a correct CSP; a wrong one breaks hydration silently. Follow-up item, documented here.

## 3. SEO / OG

- `src/app/layout.tsx` metadata: add `metadataBase: new URL("https://throughline-theta.vercel.app")`, `openGraph: {title, description, siteName: "Throughline", type: "website"}`, `twitter: {card: "summary_large_image", title, description}`.
- `src/app/opengraph-image.tsx`: `ImageResponse` 1200×630 — neutral-950 background, mono "through**line**" with amber accent, tagline "the tech wire, ranked daily". `export const runtime = "nodejs"` default fine; alt text export.
- `src/app/robots.ts`: allow all agents, `sitemap: <base>/sitemap.xml`.
- `src/app/sitemap.ts`: static routes (/, /topics, /archive, /synthesis, /about) + `getLatestTopics()` t/ pages, `changeFrequency` hourly for `/`, daily otherwise.
- Page `metadata` exports: `/topics` ("Topics — Throughline"), `/archive`, `/saved` ("Saved — Throughline"), `/search` (generateMetadata from q: `results for "q" — Throughline`).

## 4. Error pages

- `src/app/not-found.tsx` (server): big mono "404", "this thread doesn't exist." + Link home. Board styling (neutral-950, amber accent).
- `src/app/error.tsx` (client, receives `error`/`reset`): "something broke." + retry button calling `reset()` + Link home. No error details leaked to UI.

## Error handling

Limiter failures cannot 500 routes (pure in-memory; no IO). 429 responses include `Retry-After`. All other behavior unchanged.

## Testing

- **vitest** `tests/web/ratelimit.test.ts`: under-limit allows, over-limit blocks, window expiry re-allows (fake clock), key isolation, prune at cap.
- **vitest** validation: the `item_id` pattern lives in a new `src/lib/validate.ts` (`ITEM_ID_RE` + `isValidItemId(s)`), imported by the feedback route; `tests/web/validate.test.ts` covers valid shapes for all five sources and rejects >120 chars, spaces, `<script>`, empty.
- **curl**: 11 rapid POSTs → 11th 429; headers present on `/`; `/robots.txt`, `/sitemap.xml`, `/opengraph-image` 200; 404 page styled.
- Suites: vitest grows from 26, pytest 67 untouched, lint/tsc/build green.

## Out of scope

CSP with nonces, Vercel WAF rules (optional dashboard step, post-launch), analytics, error tracking (Sentry), custom domain.
