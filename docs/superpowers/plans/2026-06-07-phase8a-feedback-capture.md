# Phase 8a — Feedback Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture 👍/👎 interest and read/unread state per item, persisted to Supabase through server-side Next.js route handlers.

**Architecture:** A server-only `supabase.ts` exposes a service_role client (null when env is missing). Two route handlers (`/api/feedback`, `/api/read`) validate input and write to Supabase. A client component `ItemActions` does optimistic 👍/👎/read with `fetch`. The home loader reads `read_state` to hydrate the read flag per card. Site stays fully functional if Supabase is unconfigured.

**Tech Stack:** Next.js App Router route handlers + client components, `@supabase/supabase-js`, Supabase (Postgres) via the connector.

**Verification note:** no JS test runner exists (deferred to P10). Each task verifies with `tsc`/`build`; final tasks use Playwright + the Supabase connector. The Python pipeline suite (34 tests) must stay green and is untouched.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/package.json                       # MODIFY — add @supabase/supabase-js
/src/lib/supabase.ts                # NEW — server-only service_role client (nullable)
/src/lib/feedback.ts                # NEW — getReadStates() loader
/src/app/api/feedback/route.ts      # NEW — POST insert feedback
/src/app/api/read/route.ts          # NEW — POST upsert read_state
/src/components/ItemActions.tsx     # NEW — "use client" thumbs + read toggle
/src/components/ItemCard.tsx        # MODIFY — render ItemActions + dim read cards
/src/app/page.tsx                   # MODIFY — hydrate initialRead per card
/.env                               # MODIFY (user) — SUPABASE_SERVICE_ROLE_KEY
```

---

### Task 1: Provision Supabase tables (connector)

**Files:** none (remote schema)

- [ ] **Step 1: Confirm the project**

Use the Supabase MCP tool `list_projects` (or `get_project` with `id=rbvuzuthykisxzgwdxqh`) to
confirm the `throughline` project ref `rbvuzuthykisxzgwdxqh` is active.

- [ ] **Step 2: Apply the migration**

Use `apply_migration` with `project_id=rbvuzuthykisxzgwdxqh`, name `feedback_and_read_state`,
and this SQL:

```sql
create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  item_id text not null,
  signal smallint not null,
  created_at timestamptz default now()
);
alter table feedback enable row level security;

create table if not exists read_state (
  item_id text primary key,
  read boolean default false,
  updated_at timestamptz default now()
);
alter table read_state enable row level security;
```

- [ ] **Step 3: Verify**

Use `list_tables` (`project_id=rbvuzuthykisxzgwdxqh`) and confirm `feedback` + `read_state`
exist with RLS enabled and no policies. (No commit — schema is remote.)

---

### Task 2: Add the Supabase client dependency

**Files:**
- Modify: `package.json` (via npm)

- [ ] **Step 1: Install**

Run: `npm install @supabase/supabase-js`
Expected: adds `@supabase/supabase-js` to `dependencies` in `package.json`.

- [ ] **Step 2: Verify build still works**

Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore(web): add @supabase/supabase-js"
```

---

### Task 3: Server-only Supabase client

**Files:**
- Create: `src/lib/supabase.ts`

- [ ] **Step 1: Write the client factory**

Create `src/lib/supabase.ts`:

```ts
import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export function getServiceClient(): SupabaseClient | null {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}
```

- [ ] **Step 2: Add the server-only guard package**

Run: `npm install server-only`
(The `server-only` package makes the build fail loudly if this module is ever imported into a
client component — a safety rail for the service_role key.)

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/supabase.ts package.json package-lock.json
git commit -m "feat(web): add server-only Supabase service client"
```

---

### Task 4: Feedback route handler

**Files:**
- Create: `src/app/api/feedback/route.ts`

- [ ] **Step 1: Write the handler**

Create `src/app/api/feedback/route.ts`:

```ts
import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export async function POST(request: Request) {
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
  if (typeof item_id !== "string" || !item_id || (signal !== 1 && signal !== -1)) {
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

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors; `/api/feedback` appears in the route list.

- [ ] **Step 3: Commit**

```bash
git add src/app/api/feedback/route.ts
git commit -m "feat(web): add feedback route handler"
```

---

### Task 5: Read-state route handler

**Files:**
- Create: `src/app/api/read/route.ts`

- [ ] **Step 1: Write the handler**

Create `src/app/api/read/route.ts`:

```ts
import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const { item_id, read } = (body ?? {}) as {
    item_id?: unknown;
    read?: unknown;
  };
  if (typeof item_id !== "string" || !item_id || typeof read !== "boolean") {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }

  const client = getServiceClient();
  if (!client) {
    return NextResponse.json({ error: "supabase not configured" }, { status: 503 });
  }

  const { error } = await client
    .from("read_state")
    .upsert(
      { item_id, read, updated_at: new Date().toISOString() },
      { onConflict: "item_id" },
    );
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors; `/api/read` appears in the route list.

- [ ] **Step 3: Commit**

```bash
git add src/app/api/read/route.ts
git commit -m "feat(web): add read-state route handler"
```

---

### Task 6: Read-state loader

**Files:**
- Create: `src/lib/feedback.ts`

- [ ] **Step 1: Write the loader**

Create `src/lib/feedback.ts`:

```ts
import "server-only";
import { getServiceClient } from "./supabase";

export async function getReadStates(): Promise<Set<string>> {
  const client = getServiceClient();
  if (!client) return new Set();
  try {
    const { data, error } = await client
      .from("read_state")
      .select("item_id")
      .eq("read", true);
    if (error || !data) return new Set();
    return new Set(data.map((r) => r.item_id as string));
  } catch {
    return new Set();
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/feedback.ts
git commit -m "feat(web): add read-state loader"
```

---

### Task 7: ItemActions client component

**Files:**
- Create: `src/components/ItemActions.tsx`

- [ ] **Step 1: Write the component**

Create `src/components/ItemActions.tsx`:

```tsx
"use client";

import { useState } from "react";

export function ItemActions({
  itemId,
  initialRead,
}: {
  itemId: string;
  initialRead: boolean;
}) {
  const [signal, setSignal] = useState<1 | -1 | 0>(0);
  const [read, setRead] = useState(initialRead);
  const [busy, setBusy] = useState(false);

  async function sendFeedback(next: 1 | -1) {
    const prev = signal;
    const value = signal === next ? 0 : next; // toggle off if same
    setSignal(value);
    if (value === 0) return; // nothing to record when clearing
    setBusy(true);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemId, signal: value }),
      });
      if (!res.ok) setSignal(prev);
    } catch {
      setSignal(prev);
    } finally {
      setBusy(false);
    }
  }

  async function toggleRead() {
    const next = !read;
    setRead(next);
    setBusy(true);
    try {
      const res = await fetch("/api/read", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemId, read: next }),
      });
      if (!res.ok) setRead(!next);
    } catch {
      setRead(!next);
    } finally {
      setBusy(false);
    }
  }

  const base = "font-mono text-xs transition-colors disabled:opacity-50";
  return (
    <div className="mt-3 flex items-center gap-4">
      <button
        type="button"
        aria-label="Interesting"
        disabled={busy}
        onClick={() => sendFeedback(1)}
        className={`${base} ${signal === 1 ? "text-emerald-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▲ interesting
      </button>
      <button
        type="button"
        aria-label="Not interesting"
        disabled={busy}
        onClick={() => sendFeedback(-1)}
        className={`${base} ${signal === -1 ? "text-rose-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▼ not
      </button>
      <button
        type="button"
        aria-label="Toggle read"
        disabled={busy}
        onClick={toggleRead}
        className={`${base} ${read ? "text-neutral-300" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        {read ? "✓ read" : "mark read"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/components/ItemActions.tsx
git commit -m "feat(web): add ItemActions client component"
```

---

### Task 8: Wire ItemActions into ItemCard

**Files:**
- Modify: `src/components/ItemCard.tsx`

- [ ] **Step 1: Import + props + render**

In `src/components/ItemCard.tsx`, add the import at the top:

```tsx
import { ItemActions } from "./ItemActions";
```

Change the component signature to accept `initialRead`:

```tsx
export function ItemCard({
  item,
  initialRead = false,
}: {
  item: Item;
  initialRead?: boolean;
}) {
```

Add `initialRead && "opacity-60"` to the `<article>` className so read cards dim. The article
opening tag becomes:

```tsx
    <article
      className={`border-b border-neutral-800 py-6 ${initialRead ? "opacity-60" : ""}`}
    >
```

At the end of the card, after the authors paragraph and before the closing `</article>`, add:

```tsx
      <ItemActions
        itemId={`${item.source}:${item.id}`}
        initialRead={initialRead}
      />
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/components/ItemCard.tsx
git commit -m "feat(web): render feedback actions in item cards"
```

---

### Task 9: Hydrate read state on the home page

**Files:**
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Load read states and pass to cards**

In `src/app/page.tsx`, add the import:

```tsx
import { getReadStates } from "@/lib/feedback";
```

In `HomePage`, after `const digest = await getLatestDigest();` add:

```tsx
  const readSet = await getReadStates();
```

Then pass `initialRead` to every `ItemCard`. Both render sites (the topic-section branch and
the flat fallback branch) change their `<ItemCard ... />` to:

```tsx
                  <ItemCard
                    key={itemKey(item)}
                    item={item}
                    initialRead={readSet.has(itemKey(item))}
                  />
```

and (flat fallback):

```tsx
            <ItemCard
              key={itemKey(item)}
              item={item}
              initialRead={readSet.has(itemKey(item))}
            />
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors. (Build runs with no Supabase env → `getReadStates()` returns an empty
set; pages still prerender.)

- [ ] **Step 3: Commit + push**

```bash
git add src/app/page.tsx
git commit -m "feat(web): hydrate read state on home page"
git push
```

---

### Task 10: Live verification + config handoffs

**Files:** none (config + manual verification)

- [ ] **Step 1: Confirm the service_role key is in `.env`** (user-provided). Verify without
printing it:

```bash
set -a && . ./.env && set +a && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ] && echo "KEY PRESENT" || echo "KEY MISSING"
```
If missing, ask the user to paste it into `.env` before continuing.

- [ ] **Step 2: Run dev with env loaded**

```bash
set -a && . ./.env && set +a && (npm run dev > /tmp/tl-dev.log 2>&1 &) && sleep 7 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```
Expected: `200`.

- [ ] **Step 3: Exercise the routes via Playwright**

Navigate to `http://localhost:3000`, click ▲ interesting and "mark read" on the first card,
confirm the optimistic styling changes (emerald thumb, "✓ read", card dims). Screenshot.

- [ ] **Step 4: Confirm rows landed**

Use the Supabase connector `execute_sql` (`project_id=rbvuzuthykisxzgwdxqh`):
`select count(*) from feedback;` and `select count(*) from read_state;` — both ≥ 1.

- [ ] **Step 5: Stop dev**

```bash
pkill -f "next dev"; pkill -f "next-server"
```

- [ ] **Step 6: Handoffs (user, dashboards)**

Tell the user to add `SUPABASE_SERVICE_ROLE_KEY` to:
- **Vercel** project env vars (so deployed route handlers work) — also add `SUPABASE_URL` if not present.
- **GitHub Actions** secrets (Phase 8b CI ranker).

---

## Self-review notes

- **Spec coverage:** tables + RLS (T1), dependency (T2), server client nullable (T3),
  feedback route w/ validation + 503/500 (T4), read route upsert (T5), getReadStates loader
  (T6), ItemActions optimistic client component, no `<form>` (T7), ItemCard render + dim
  (T8), page hydration both render sites (T9), live verify + handoffs (T10). All spec
  sections mapped.
- **Type consistency:** `getServiceClient(): SupabaseClient | null` used by both routes +
  loader; `getReadStates(): Promise<Set<string>>`; `ItemActions({itemId, initialRead})`;
  `ItemCard({item, initialRead?})`; `item_id` = `f"{source}:{id}"` (matches pipeline + the
  `itemKey` helper in page.tsx). Route bodies: `{item_id, signal}` and `{item_id, read}`
  match what ItemActions POSTs.
- **Placeholder scan:** none. Project ref `rbvuzuthykisxzgwdxqh` is the real ref from `.env`.
- **No JS unit tests:** intentional (spec); verification via tsc/build/Playwright/connector.
- **Fault tolerance:** every Supabase touch degrades to 503 / empty-set when env missing, so
  `npm run build` (no env) and a Supabase outage both leave the site working.
- **No backdating / no Claude trailer** on commits.
```
