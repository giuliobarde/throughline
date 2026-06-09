# Phase 10 — Polish (final) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/topics/[tag]` pages, apply a frontend-design refinement pass (visual + a11y, no behavior change), and finish the README + verify the production deploy.

**Architecture:** Topic pages reuse the existing content loaders + `ItemCard`; the `#topic` tag becomes a link. The design pass refines existing components only (type/spacing/color/focus/motion/mobile) guided by the `frontend-design` skill. README is rewritten to reflect the finished pipeline; pushing redeploys via the git-connected Vercel project.

**Tech Stack:** Next.js App Router + Tailwind; no new deps. Pipeline untouched (46 pytest stay green).

**Verification note:** no JS test runner (consistent prior decision) — tsc + build + Playwright. Visual-only changes must not alter data/behavior.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/src/lib/content.ts                 # MODIFY — getTopic, getLatestTopics
/src/app/topics/[tag]/page.tsx      # NEW — topic filtered page
/src/components/ItemCard.tsx        # MODIFY — #topic becomes a link (+ design refinements)
/src/components/SourceBadge.tsx     # MODIFY (design pass)
/src/components/ItemActions.tsx     # MODIFY (design pass — focus states)
/src/app/layout.tsx                 # MODIFY (design pass — nav focus/mobile)
/src/app/page.tsx                   # MODIFY (design pass)
/src/app/archive/page.tsx           # MODIFY (design pass)
/src/app/about/page.tsx             # MODIFY (design pass)
/src/app/synthesis/page.tsx         # MODIFY (design pass)
/src/app/synthesis/[week]/page.tsx  # MODIFY (design pass)
/src/app/globals.css                # MODIFY (design pass — focus ring, reduced-motion)
/README.md                          # MODIFY — finished docs
```

---

### Task 1: Topic loaders

**Files:**
- Modify: `src/lib/content.ts`

- [ ] **Step 1: Add getLatestTopics + getTopic**

Append to `src/lib/content.ts` (it already imports `Digest, IndexEntry` from `./types` and has
`getLatestDigest`; extend the type import to include `Item, Topic`):

Change the existing import line:
```ts
import type { Digest, IndexEntry } from "./types";
```
to:
```ts
import type { Digest, Item, IndexEntry, Topic } from "./types";
```

Then append:

```ts
export async function getLatestTopics(): Promise<Topic[]> {
  const digest = await getLatestDigest();
  return digest?.topics ?? [];
}

export async function getTopic(
  tag: string,
): Promise<{ label: string; items: Item[] } | null> {
  const digest = await getLatestDigest();
  if (!digest) return null;
  const topic = digest.topics.find((t) => t.tag === tag);
  if (!topic) return null;
  const byKey = new Map(digest.items.map((i) => [`${i.source}:${i.id}`, i]));
  const items = topic.item_ids
    .map((id) => byKey.get(id))
    .filter((i): i is Item => Boolean(i))
    .sort((a, b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0));
  return { label: topic.label, items };
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/content.ts
git commit -m "feat(web): add topic loaders"
```

---

### Task 2: /topics/[tag] page + ItemCard topic link

**Files:**
- Create: `src/app/topics/[tag]/page.tsx`
- Modify: `src/components/ItemCard.tsx`

- [ ] **Step 1: Write the topic page**

Create `src/app/topics/[tag]/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import { ItemCard } from "@/components/ItemCard";
import { getLatestTopics, getTopic } from "@/lib/content";
import { getReadStates } from "@/lib/feedback";
import type { Item } from "@/lib/types";

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
  const topic = await getTopic(tag);
  if (!topic) notFound();
  const readSet = await getReadStates();
  const itemKey = (i: Item) => `${i.source}:${i.id}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <a href="/" className="font-mono text-xs text-neutral-500 hover:text-neutral-300">
        ← all topics
      </a>
      <h1 className="mt-2 text-2xl font-bold">{topic.label}</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">
        {topic.items.length} items
      </p>
      <div className="mt-6">
        {topic.items.map((item) => (
          <ItemCard
            key={itemKey(item)}
            item={item}
            initialRead={readSet.has(itemKey(item))}
          />
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Make the #topic tag a link in ItemCard**

In `src/components/ItemCard.tsx`, replace the topic span:

```tsx
        {item.topic && (
          <span className="font-mono text-xs text-neutral-600">#{item.topic}</span>
        )}
```
with a link:

```tsx
        {item.topic && (
          <a
            href={`/topics/${item.topic}`}
            className="font-mono text-xs text-neutral-600 hover:text-neutral-300"
          >
            #{item.topic}
          </a>
        )}
```

- [ ] **Step 3: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors; `/topics/[tag]` in route list (SSG params from latest digest topics).

- [ ] **Step 4: Commit**

```bash
git add "src/app/topics/[tag]/page.tsx" src/components/ItemCard.tsx
git commit -m "feat(web): add topic pages and link topic tags"
```

---

### Task 3: Design refinement pass

**Files:** `src/app/globals.css`, `src/app/layout.tsx`, `src/components/*.tsx`, `src/app/**/page.tsx`

- [ ] **Step 1: Invoke the frontend-design skill**

Use the `Skill` tool to launch `frontend-design:frontend-design`. Read its guidance before
editing. Apply it as a refinement (not a redesign) of the existing dark/terminal aesthetic.

- [ ] **Step 2: Capture the current baseline**

Start dev and screenshot home + mobile for before/after comparison:
```bash
set -a && . ./.env 2>/dev/null && set +a
(npm run dev > /tmp/tl-dev.log 2>&1 &) && sleep 7 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```
Use Playwright to screenshot `http://localhost:3000` at 1280px and 390px.

- [ ] **Step 3: Apply global a11y + motion primitives**

In `src/app/globals.css`, after the `body` rule, add a visible focus ring and reduced-motion
guard (Tailwind v4 — plain CSS is fine here):

```css
a:focus-visible,
button:focus-visible {
  outline: 2px solid var(--color-amber-400, #fbbf24);
  outline-offset: 2px;
  border-radius: 2px;
}

@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Apply component/page refinements**

Following the frontend-design guidance, refine (visual only — do not change props, data, or
handlers):
- **Type/hierarchy:** consistent title/section/card/body/meta scale; tighten `leading` and
  max line length on reader/about.
- **Spacing rhythm:** even vertical spacing between cards and sections.
- **Color/accents:** keep emerald=code, amber=repro+ForYou+focus, neutral=meta; verify text
  contrast (bump `neutral-600` → `neutral-500` where it reads too dim on labels).
- **Hover/transition:** add `transition-colors` to interactive elements lacking it.
- **Mobile:** confirm nav + cards fit at 390px; adjust `px`/gap if cramped.
- **Semantics:** ensure one `<h1>` per page and logical heading order; `<nav>`/`<main>` already
  present in layout.

Keep each edit small; re-run `npx tsc --noEmit` after edits.

- [ ] **Step 5: Verify build + screenshots (desktop + mobile)**

Run: `npm run build`
Expected: Compiled successfully.
Playwright: re-screenshot home at 1280px and 390px; confirm the refinements render and nothing
regressed (cards, badges, For You strip, actions still present).

- [ ] **Step 6: Stop dev + commit**

```bash
pkill -f "next dev"; pkill -f "next-server"
git add src/app/globals.css src/app/layout.tsx src/components src/app/page.tsx src/app/archive/page.tsx src/app/about/page.tsx src/app/synthesis
git commit -m "style(web): frontend-design refinement pass (type, spacing, focus, motion, mobile)"
```

---

### Task 4: Finish the README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README**

Replace `README.md` with finished docs covering: what it is; the architecture diagram (full
pipeline: sources arXiv·Tavily·HN·GitHub → dedupe → embed → cluster → rank(feedback) →
summarize+label(Claude) → [Sun: synthesize] → write dated JSON/MDX → commit → Vercel);
local setup (frontend `npm install` + `npm run dev`; pipeline venv + `pip install -r
pipeline/requirements.txt` + `python -m pipeline.run --dry-run|--date|--synthesize`); how the
daily Action works + honest-commit principle (author = GitHub noreply, real timestamps, never
backdated, no Claude trailer); the env table (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, SUPABASE_*,
TAVILY_API_KEY, GITHUB_TOKEN); pages overview (`/`, `/archive`, `/topics/[tag]`, `/synthesis`,
`/about`). Keep the live URL line at the top.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: finish README for the completed build"
```

---

### Task 5: Verify + redeploy

**Files:** none

- [ ] **Step 1: Final local verification**

```bash
npx tsc --noEmit && npm run build
.venv/bin/python -m pytest tests/ -q   # 46 passed
git status --short                      # clean
```

- [ ] **Step 2: Push (triggers Vercel auto-deploy)**

```bash
git push
```

- [ ] **Step 3: Topic-page live check (local, with a digest that has topics)**

If no committed latest digest has topics, generate one locally to exercise the route:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-09
(npm run dev > /tmp/tl-dev.log 2>&1 &) && sleep 7
```
Playwright: on `http://localhost:3000`, click a `#topic` tag → lands on `/topics/{tag}` showing
that topic's items. Screenshot. Then restore + stop:
```bash
git checkout content/index.json 2>/dev/null
rm -f content/digests/2026-06-09.json data/summaries/cache.json data/embeddings/cache.json
git checkout data content/digests/2026-06-09.json 2>/dev/null
pkill -f "next dev"; pkill -f "next-server"
```
(If `2026-06-09.json` is a committed Action digest, `git checkout` restores it; otherwise the
`rm` removes the hand-run file.)

- [ ] **Step 4: Confirm production**

After the push deploys, fetch the prod URL and confirm 200 + the digest renders:
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://throughline-theta.vercel.app
```
Expected: `200`. (If still `401`, deployment protection was re-enabled — tell the user.)

- [ ] **Step 5: Final commit (if any README/URL tweak) + done**

Working tree should be clean; the build is complete.

---

## Self-review notes

- **Spec coverage:** topic loaders (T1), `/topics/[tag]` + tag link (T2), frontend-design
  refinement incl. a11y/motion/mobile (T3), README (T4), verify + redeploy + topic live check
  (T5). All spec sections mapped. Archive search correctly absent (dropped).
- **Type consistency:** `getTopic(tag) -> {label, items} | null`, `getLatestTopics() -> Topic[]`;
  `Item`/`Topic` imported from `./types`; `source:id` key matches the rest of the app; topics
  page awaits `params` Promise (Next route-param convention, as in synthesis reader).
- **Placeholder scan:** none. The design pass (T3) is necessarily descriptive (visual
  judgment), but each refinement is concrete and gated by `tsc`/`build`/screenshots; the
  `frontend-design` skill supplies the specifics at execution.
- **No pipeline changes:** pytest count stays 46; only TS/CSS/README touched.
- **No backdating / no Claude trailer** on commits.
```
