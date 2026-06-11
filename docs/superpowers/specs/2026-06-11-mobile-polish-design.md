# Mobile Polish — Design Spec (P3)

**Date:** 2026-06-11
**Status:** Approved
**Series:** P3 of 4 (P4 public hardening pending)

## Problem (audited live at 390×844, dev)

1. **Nav overflows**: brand + search box + topics/archive/weekly/about ≈ 405px on a 390px viewport; trailing links clipped. Affects every page.
2. **Home feed column blowout**: the Feed controls row (4 sort pills + `ml-auto` density toggle) cannot shrink below ~430px and doesn't wrap, so the grid column stretches past the viewport — card text/dates clip at the right edge, the density toggle truncates. On `max-w-3xl` pages (topic/search) it instead wraps badly ("For You" renders as a two-line pill).
3. **Touch targets**: VoteRail ▲/▼ and the save/share/discuss row are `text-xs` with no padding — far below comfortable tap size.
4. **Long unbroken words/URLs in titles** can overflow card bounds (`break-words` missing).

## Fixes (Tailwind class changes only — no logic, no new components)

### `src/app/layout.tsx` — responsive two-row nav
- Nav inner container: add `flex-wrap gap-y-2`.
- Links container (`<SearchBox />` stays where it is, before the links): becomes full-width second row on mobile, inline on `sm+`:
  `order-last flex w-full items-center justify-between font-mono text-xs text-neutral-400 sm:order-none sm:w-auto sm:justify-start sm:gap-6` (drop the old `gap-6`; mobile spacing comes from `justify-between`).
- SearchBox stays on row 1 right side: wrap site title + SearchBox spacing via `ml-auto` on the SearchBox's wrapper position in the flex (achieved by the links wrapping away; add `ml-auto sm:ml-0` to SearchBox's outer div via a `className` prop OR place SearchBox inside a `ml-auto sm:ml-0` wrapper div in layout — choose the wrapper div, no SearchBox API change).

### `src/components/Feed.tsx` — controls row fits 390px
- Controls row: `mb-4 flex flex-wrap items-center gap-y-2 gap-x-2`.
- Sort pills: `whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[11px] sm:px-3 sm:text-xs ...` (keep color/active classes).
- Density toggle buttons: `px-2 py-1 text-[11px] sm:px-2.5 sm:text-xs`, container keeps `ml-auto`.
- Root wrapper `<div>` of Feed: add `min-w-0` (kills any residual grid blowout at the source).

### `src/app/page.tsx` — grid hardening
- Mobile single-column grid: `grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_240px]` (add `min-w-0`).

### `src/components/VoteRail.tsx` — tap targets
- Up/Down buttons: add `px-2 py-1 -mx-2 -my-0.5` styling-neutral hit padding (rail width stays w-8 visually; negative margins keep layout). Simpler accepted alternative if negative margins fight the rail layout: `p-1` and widen rail to `w-9`.

### `src/components/PostCard.tsx` + `src/components/PostRow.tsx`
- Headings: add `break-words` to the `<h2>` classes.
- Action row buttons/links (save/share/discuss): add `py-1` for tap height (visual rhythm preserved by existing margins).

## Verification

- Playwright at 390×844: home cards + compact (no horizontal overflow — assert `document.documentElement.scrollWidth <= 390`), nav shows all 4 links + search, density toggle fully visible; t/ page tabs single-line; /search, /saved sane. Repeat spot-check at 768 and 1380 (no regressions).
- Before/after screenshots.
- Suites: vitest 26, pytest 67, lint 0, tsc clean, build green (classes only — suites must be untouched).

## Out of scope

Arrow-key dropdown nav, hamburger menu, sticky bottom nav, PWA/meta-theme polish (P4 territory), any markup restructuring beyond the nav wrapper div.
