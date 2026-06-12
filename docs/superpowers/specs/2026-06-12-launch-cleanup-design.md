# Launch Cleanup — Design Spec

**Date:** 2026-06-12
**Status:** Approved (user: "address everything except the domain")
**Source:** pre-launch audit findings 2-5 + cheap conscious-gap fixes + analytics. Actions secrets (item 1) remain a user task; custom domain deferred.

## Changes

1. **About page rewrite** (`src/app/about/page.tsx`): describe the board as it is — community-style ranked feed over an automated pipeline (arXiv/HN/GitHub/vendor blogs/news), Claude summaries + topic labels, anonymous votes feeding a personal ranker, archive to 2026-01-01, data in Supabase, built solo + AI-assisted. Keep board styling.
2. **README rewrite**: remove the retired data-commit/contribution-graph narrative; architecture now pipeline → Supabase ← Next.js; update run instructions (env REQUIRED), keep honest tone. Screenshots section trimmed to reference docs/ images or removed.
3. **Base URL env-var**: `SITE_URL` (fallback `https://throughline-theta.vercel.app`) consumed by layout `metadataBase`, `robots.ts`, `sitemap.ts` via a tiny `src/lib/site.ts` export. `.env.example` documents it as optional.
4. **Repo cleanup**: delete the 13 root screenshots (`home*.png/jpeg`, `polish-*.png`, `synthesis-reader.png`); delete `pipeline/migrate_to_db.py` (one-off, already executed; lives in git history).
5. **/saved title**: `src/app/saved/layout.tsx` server wrapper exporting `metadata = { title: "Saved — Throughline" }`.
6. **Analytics**: add `@vercel/analytics`, `<Analytics />` in root layout (no-op until enabled in dashboard — user toggle).
7. **Drop orphaned `read_state` table** in Supabase (UI/API removed in the board pivot; zero readers).

## Out of scope
Custom domain (user, later), CSP/nonce middleware (documented follow-up), WAF rules (dashboard), Actions secrets (user).

## Verification
Suites green (vitest 34, pytest 70, lint, tsc, build); robots/sitemap/metadata render the fallback URL; About/README read accurately; prod spot-check post-push.
