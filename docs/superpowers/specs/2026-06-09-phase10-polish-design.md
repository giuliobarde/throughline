# Phase 10 — Polish (final) — Design Spec

**Date:** 2026-06-09
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

The finishing pass: dedicated `/topics/[tag]` pages, a frontend-design refinement of the
existing UI (type, spacing, color, focus/a11y, motion, mobile), and a finished README +
deploy verification. Closes out the phased build.

## Decisions locked (2026-06-09)

| Decision | Choice |
|----------|--------|
| Scope | `/topics/[tag]` pages · design refinement pass · README + redeploy verify |
| Dropped | Archive full-text search (fuse.js) — explicitly out this phase |
| Design depth | Refine the existing editorial dark/terminal theme (no redesign) |
| Topic page source | Latest digest only (no cross-digest aggregation) |

## 1. `/topics/[tag]` pages

### `src/lib/content.ts`

- Add `getTopic(tag: string): Promise<{ label: string; items: Item[] } | null>`:
  - `getLatestDigest()`; find `topics[]` entry with `tag`. If none → `null`.
  - Resolve `item_ids` → `Item`s via a `source:id` map; sort by `for_you_score` desc.
  - Return `{ label, items }`.
- Add `getLatestTopics(): Promise<Topic[]>` (for `generateStaticParams`) — latest digest's
  `topics` (empty if none).

### `src/app/topics/[tag]/page.tsx`

- `export const revalidate = 3600`.
- `generateStaticParams` → `getLatestTopics().map(t => ({ tag: t.tag }))`.
- `params` is a `Promise<{ tag }>` (await it). `getTopic(tag)`; if `null` → `notFound()`.
- Render the topic `label` (h1) + a back link to `/`, then the `ItemCard`s (hydrate
  `initialRead` via `getReadStates()`, consistent with home).

### `src/components/ItemCard.tsx`

- The `#topic` metadata span becomes a link to `/topics/{item.topic}` (keep mono styling +
  hover). Server component, so a plain `<a>`.

## 2. Design refinement pass

**Process:** invoke the `frontend-design` skill at build time and apply its guidance. This is
a visual-only pass — no data/behavior changes; `tsc`, `build`, and the 46 pytest tests stay
green.

**Checklist (refine, don't rebuild):**
- **Type:** consistent scale + hierarchy (page title / section label / card title / body /
  mono metadata); tighten leading/measure.
- **Spacing:** consistent vertical rhythm between sections, cards, metadata.
- **Color:** cohesive source-badge treatment, accent usage (emerald code / amber repro+ForYou
  / neutral meta) kept deliberate and restrained; sufficient contrast on `neutral-*` text.
- **Interaction/a11y:** visible `focus-visible` rings on all links/buttons; adequate tap
  targets; semantic landmarks (`<main>`, `<nav>`, headings order); `aria-label`s already on
  ItemActions retained.
- **Motion:** subtle hover transitions; wrap non-essential motion in
  `@media (prefers-reduced-motion: reduce)`.
- **Mobile:** comfortable padding, no overflow, nav wraps/fits at 390px.
- **Surfaces touched:** `layout.tsx`, `page.tsx`, `ItemCard`, `SourceBadge`, `ItemActions`,
  `archive`, `synthesis` (list + reader), `about`, `topics`.

## 3. README + redeploy

- Rewrite `README.md` to reflect the finished system:
  - What it is (one paragraph).
  - Architecture diagram — the full daily pipeline: sources (arXiv · Tavily news · HN ·
    GitHub) → dedupe → embed → cluster → rank (feedback) → summarize + label (Claude) →
    [Sun: synthesize] → write dated JSON/MDX → commit → Vercel.
  - Local setup (frontend `npm run dev`; pipeline venv + `python -m pipeline.run`
    `--dry-run`/`--date`/`--synthesize`).
  - How the daily Action works + the honest-commit principle (author = noreply, real
    timestamps, never backdated).
  - Env table (keep existing rows; ensure Tavily/GitHub/Supabase/Anthropic all listed).
  - Pages overview (`/`, `/archive`, `/topics/[tag]`, `/synthesis`, `/about`).
- Redeploy: pushing to `main` triggers the git-connected Vercel build. Verify the prod URL
  returns 200 and renders the latest digest.

## Testing / verification

- `npx tsc --noEmit` + `npm run build` clean (new topics route compiles, SSG params work with
  the committed latest digest).
- `pytest` 46 green (untouched — no pipeline changes this phase).
- Playwright screenshots: refined home (desktop + 390px mobile), a `/topics/[tag]` page, and
  one already-covered page (synthesis) to confirm no regression. Confirm `#topic` links
  navigate to the topic page.
- Prod URL 200 after push.

No JS unit runner is added (consistent prior decision); verification is tsc/build/Playwright.

## Error handling

- `getTopic` / `getLatestTopics` → `null`/`[]` when no digest or no topics (pages handle:
  `notFound()` for an unknown tag; topics nav only where tags exist).
- Build with an empty/topic-less latest digest: `generateStaticParams` returns `[]`, route
  still compiles.

## Out of scope (YAGNI)

- Archive fuse.js search (dropped this phase).
- `@tailwindcss/typography` plugin (explicit classes).
- Cross-digest topic aggregation (latest digest only).
- JS unit-test harness.
- Visual redesign / new palette system (refinement only).
