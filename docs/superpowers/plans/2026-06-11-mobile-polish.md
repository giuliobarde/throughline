# Mobile Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the audited 390px failures — nav overflow, home feed column blowout, tiny touch targets, unbroken-word overflow — with Tailwind-class-only edits.

**Architecture:** Three small tasks: (1) layout/grid/Feed-controls responsive classes (the overflow killers), (2) tap-target padding + `break-words`, (3) Playwright viewport verification with a `scrollWidth ≤ 390` assertion. No logic, markup restructure limited to one wrapper div in the nav, no new tests in suites (visual verification is the test).

**Tech Stack:** Tailwind v4 · Next.js 16 · Playwright (verification only).

**Spec:** `docs/superpowers/specs/2026-06-11-mobile-polish-design.md`

**Commit rules (repo non-negotiable):** plain `git commit`, exact messages, NO Co-Authored-By/Claude trailer.

**Baselines:** vitest 26, pytest 67, lint 0, tsc clean — all must be unchanged at the end (class-only changes).

---

### Task 1: Overflow killers — nav, grid, Feed controls

**Files:**
- Modify: `src/app/layout.tsx`
- Modify: `src/app/page.tsx:31`
- Modify: `src/components/Feed.tsx:73-103`

- [ ] **Step 1: layout.tsx nav.** Replace the nav inner container line

```tsx
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
```

with

```tsx
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-y-2 px-4 py-3 sm:px-6 sm:py-4">
```

Then replace the links container opening tag

```tsx
            <div className="flex items-center gap-5 font-mono text-xs text-neutral-400">
              <SearchBox />
```

with (SearchBox moves out, links become a full-width second row on mobile):

```tsx
            <div className="ml-auto sm:order-last sm:ml-0">
              <SearchBox />
            </div>
            <div className="order-last flex w-full items-center justify-between font-mono text-xs text-neutral-400 sm:order-none sm:w-auto sm:justify-start sm:gap-6">
```

(The four `<Link>`s stay inside the second div, unchanged. Result: mobile row 1 = brand + search (right-aligned), row 2 = the four links spread full-width; `sm:` and up = brand left, links + search right in one row with search last.)

- [ ] **Step 2: page.tsx grid.** Replace

```tsx
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px]">
```

with

```tsx
        <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_240px]">
```

- [ ] **Step 3: Feed.tsx controls.** Replace the controls row opener

```tsx
      <div className="mb-4 flex items-center gap-2">
```

with

```tsx
      <div className="mb-4 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2">
```

Replace the sort-pill className template

```tsx
              className={`rounded-full px-3 py-1 font-mono text-xs transition-colors ${
```

with

```tsx
              className={`whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[11px] transition-colors sm:px-3 sm:text-xs ${
```

Replace the `toggle` helper

```tsx
  const toggle = (active: boolean) =>
    `px-2.5 py-1 font-mono text-xs transition-colors ${active ? "bg-neutral-800 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`;
```

with

```tsx
  const toggle = (active: boolean) =>
    `px-2 py-1 font-mono text-[11px] transition-colors sm:px-2.5 sm:text-xs ${active ? "bg-neutral-800 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`;
```

And the Feed root wrapper: replace `return (\n    <div>` opening element

```tsx
    <div>
      <div className="mb-4 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2">
```

so the root div becomes

```tsx
    <div className="min-w-0">
```

(i.e. the outermost `<div>` returned by Feed gains `className="min-w-0"`.)

- [ ] **Step 4: Verify** `npx tsc --noEmit` clean; `npm run lint` 0; `npm test` 26.

- [ ] **Step 5: Commit**

```bash
git add src/app/layout.tsx src/app/page.tsx src/components/Feed.tsx
git commit -m "fix(web): responsive nav and feed controls for small screens"
```

---

### Task 2: Tap targets + word breaking

**Files:**
- Modify: `src/components/VoteRail.tsx:52`
- Modify: `src/components/PostCard.tsx:39,58`
- Modify: `src/components/PostRow.tsx:14`
- Modify: `src/components/SaveButton.tsx:19`
- Modify: `src/components/ShareButton.tsx:31`

- [ ] **Step 1: VoteRail.** Replace

```tsx
  const btn = "leading-none transition-colors disabled:opacity-50";
```

with

```tsx
  const btn = "px-2 py-1 leading-none transition-colors disabled:opacity-50";
```

and widen the rail to absorb the padding: replace

```tsx
    <div className="flex w-8 shrink-0 flex-col items-center gap-0.5 pt-0.5 font-mono text-xs">
```

with

```tsx
    <div className="flex w-9 shrink-0 flex-col items-center pt-0.5 font-mono text-xs">
```

(`gap-0.5` dropped — the new button padding supplies the rhythm.)

- [ ] **Step 2: PostCard.** Heading line 39: `"mt-1.5 text-base font-semibold leading-snug tracking-tight"` → add `break-words` (final: `"mt-1.5 break-words text-base font-semibold leading-snug tracking-tight"`). Discuss link line 58: `"font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"` → add `py-1` (final: `"py-1 font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"`).

- [ ] **Step 3: PostRow.** Heading line 14: `"text-sm font-semibold leading-snug"` → `"break-words text-sm font-semibold leading-snug"`.

- [ ] **Step 4: SaveButton.** Line 19 template: prefix `py-1 ` (final: `` `py-1 font-mono text-xs transition-colors ${saved ? ...}` ``).

- [ ] **Step 5: ShareButton.** Line 31: `"font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"` → `"py-1 font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"`.

- [ ] **Step 6: Verify** `npx tsc --noEmit` clean; `npm run lint` 0; `npm test` 26.

- [ ] **Step 7: Commit**

```bash
git add src/components/VoteRail.tsx src/components/PostCard.tsx src/components/PostRow.tsx src/components/SaveButton.tsx src/components/ShareButton.tsx
git commit -m "fix(web): thumb-sized tap targets and title word breaking"
```

---

### Task 3: Viewport verification

No file changes — evidence gathering. Dev server assumed running on :3000 (controller keeps one alive).

- [ ] **Step 1:** With Playwright (or browser MCP) at **390×844**: load `/`, assert no horizontal overflow via `document.documentElement.scrollWidth <= 390`; visually confirm nav shows brand + search + all four links (two rows), density toggle fully visible; switch to compact, re-assert scrollWidth; screenshot both.
- [ ] **Step 2:** Same scrollWidth assertion on `/search?q=claude`, `/topics`, first t/ page, `/saved`. Confirm t/ page sort pills render on one line.
- [ ] **Step 3:** Spot-check **768×1024** and **1380×900** on `/` — single-row nav, sidebar right at 1380, no regressions. Screenshot 1380 cards view.
- [ ] **Step 4:** Report findings (controller reviews screenshots before push). If any overflow remains, fix the offending class and re-run before reporting done.
