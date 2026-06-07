# Phase 8a — Feedback Capture — Design Spec

**Date:** 2026-06-07
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)
**Sibling:** Phase 8b — Personalization ranker (separate spec; consumes this data)

## What it is

Capture per-item interest (👍/👎) and read/unread state, persisted to Supabase via
server-side Next.js route handlers. This is the data-collection half of personalization;
Phase 8b trains the ranker on it.

## Decisions locked (2026-06-07)

| Decision | Choice |
|----------|--------|
| Write path | Browser → Next.js route handler → Supabase with **service_role** key (never exposed) |
| Controls | 👍 / 👎 (signal +1 / −1) + read/unread toggle |
| Identity | Single-user app — feedback is global, no `user_id` |
| Stored embedding | **None** in `feedback` (8b recomputes from `data/embeddings/cache.json` by `item_id`) |
| RLS | Enabled on both tables, **no** public policies; service_role (server) bypasses RLS |

## Prerequisite (user)

`SUPABASE_SERVICE_ROLE_KEY` is blank in `.env`. It must be added to: local `.env`, Vercel
project env vars (for deployed route handlers), and GitHub Actions secrets (Phase 8b CI).
`SUPABASE_URL` + `SUPABASE_ANON_KEY` are already set. The connector provisions the tables.

## Supabase schema (provisioned via the Supabase connector)

```sql
create table feedback (
  id uuid primary key default gen_random_uuid(),
  item_id text not null,
  signal smallint not null,           -- 1 interesting, -1 not
  created_at timestamptz default now()
);
alter table feedback enable row level security;

create table read_state (
  item_id text primary key,
  read boolean default false,
  updated_at timestamptz default now()
);
alter table read_state enable row level security;
```

No `select`/`insert`/`update` policies are created — anon/public clients get nothing; the
server's service_role key bypasses RLS for all writes/reads. `item_id` is the existing
`f"{source}:{id}"` key used throughout the pipeline and frontend.

## Server components

### `src/lib/supabase.ts` (server-only)

- Exports `getServiceClient(): SupabaseClient | null`.
- Reads `process.env.SUPABASE_URL` and `process.env.SUPABASE_SERVICE_ROLE_KEY`; returns
  `null` if either is missing (callers degrade gracefully).
- Uses `@supabase/supabase-js` `createClient(url, serviceKey, { auth: { persistSession: false } })`.
- **Never imported by a client component.** Only route handlers and server-side loaders use it.

### `app/api/feedback/route.ts`

- `POST` handler. Body: `{ item_id: string, signal: 1 | -1 }`.
- Validate: `item_id` non-empty string, `signal` ∈ {1, -1}; else `400`.
- `getServiceClient()` → if `null`, `503`.
- `insert({ item_id, signal })` into `feedback`; on DB error `500`; on success `{ ok: true }`.

### `app/api/read/route.ts`

- `POST` handler. Body: `{ item_id: string, read: boolean }`.
- Validate: `item_id` non-empty, `read` boolean; else `400`.
- `getServiceClient()` → if `null`, `503`.
- `upsert({ item_id, read, updated_at: new Date().toISOString() }, { onConflict: "item_id" })`
  into `read_state`; DB error `500`; success `{ ok: true }`.

### `src/lib/feedback.ts` (server-side read loader)

- `getReadStates(): Promise<Set<string>>` — returns the set of `item_id`s with `read = true`.
- `getServiceClient()` → if `null`, return empty set. Select `item_id` where `read = true`.
- Any error → empty set (site never breaks on a Supabase outage).

## Frontend

### `src/components/ItemActions.tsx` (`"use client"`)

- Props: `{ itemId: string; initialRead: boolean }`.
- Local state: `signal: 1 | -1 | 0` (0 = none), `read: boolean` (init `initialRead`), `busy`.
- Renders three buttons (semantic `<button>`, not a form): 👍, 👎, and read/unread toggle.
  Active state styled (e.g. emerald for chosen thumb, neutral for read).
- Handlers: optimistic state update, then `fetch("/api/feedback"|"/api/read", {method:"POST",
  body: JSON.stringify(...)})`. On non-ok response, revert the optimistic change.
- No `<form>` — plain `onClick` handlers (per project frontend rules).

### `src/components/ItemCard.tsx`

- Accept an optional `initialRead?: boolean` prop (default `false`).
- Render `<ItemActions itemId={`${item.source}:${item.id}`} initialRead={initialRead} />` in
  the card footer. Read cards get a subtle dimming (e.g. `opacity-60`).

### `src/app/page.tsx`

- Call `getReadStates()` once; pass `initialRead={readSet.has(itemKey(item))}` to each card.
- Keep the existing topic-section grouping.

## Data flow

```
click 👍 → ItemActions optimistic → POST /api/feedback → getServiceClient → insert feedback
click read → ItemActions optimistic → POST /api/read → upsert read_state
page load → getReadStates() (service_role select) → initialRead per card
```

## Configuration

- `.env`, Vercel env, GH Actions secrets: `SUPABASE_SERVICE_ROLE_KEY` (user adds).
  `SUPABASE_URL` already present.
- README env table already lists the Supabase vars; no doc change needed beyond noting they
  are now used.
- New dependency: `@supabase/supabase-js`.

## Error handling

- Missing Supabase env → `getServiceClient()` returns `null` → routes `503`, loader returns
  empty set. The site renders normally; clicks fail quietly (optimistic revert).
- Invalid request body → `400`.
- DB error → `500`; client reverts optimistic state.

## Testing / verification

No JavaScript test runner is set up in this repo; adding one is deferred to Phase 10. 8a is
verified by:
1. `npx tsc --noEmit` — types clean.
2. `npm run build` — compiles (routes + client component).
3. Playwright: click 👍/👎 and the read toggle on a card; assert optimistic UI changes.
4. Supabase connector: confirm rows land in `feedback` and `read_state`.

The Python pipeline test suite (34 tests) is untouched and must stay green.

## Out of scope (YAGNI)

- The LogisticRegression ranker and `for_you_score` (Phase 8b).
- `item_embedding` column (8b recomputes from the cache).
- User accounts / auth (single-user).
- localStorage fallback (Supabase is the store).
- A JS unit-test harness (Phase 10).
