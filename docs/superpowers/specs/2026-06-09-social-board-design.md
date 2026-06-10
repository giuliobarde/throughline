# Throughline Social Board — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Predecessor:** `2026-06-05-throughline-design.md` (digest hub, phases 1–10 complete)

## Summary

Pivot Throughline's presentation layer from a daily digest hub into a social-board experience for tech-world information. The Python pipeline (arXiv · Tavily news · Hacker News · GitHub → embed → cluster → rank → summarize → synthesis) stays the content engine, unchanged. The Next.js frontend becomes a Reddit-style ranked board: sources "post," anonymous votes rank, topics behave like communities. No user accounts.

Chosen direction (via mockup review): **Board format** with a user-facing **density toggle** between rich cards and compact rows.

## Goals

- Engaging, social-feed reading experience over the existing aggregated content.
- Zero-friction interaction: vote, save, share with no sign-up.
- Engagement loops back into the existing personalization ranker (phase 8b) — votes are feedback rows.
- Easy to use on mobile and desktop.

## Non-Goals (YAGNI)

- User accounts, profiles, or user-authored posts.
- Comments (link out to HN discussion where one exists).
- Notifications, realtime updates, DMs.
- Pipeline changes beyond none — content generation is untouched.

## Information Architecture

| Route | Purpose |
|---|---|
| `/` | The board: tabbed ranked feed + sidebar |
| `/topics/[tag]` | t/ community page: ranked feed scoped to topic |
| `/saved` | Locally saved items (localStorage) |
| `/synthesis`, `/synthesis/[week]` | Weekly essay (existing, restyled as "This Week") |
| `/archive` | Existing digest archive (kept; feeds infinite scroll) |
| `/about` | Existing |

Top nav: `topics · archive · weekly · about`. Tagline: "the tech wire, ranked daily."

## Feed Engine (`src/lib/feed.ts`)

- **Item pool:** merge the latest N daily digests (start N=7), dedupe by `source:id` keeping the newest occurrence.
- **Sort tabs:**
  - **Hot** (default): `(1 + upvotes − downvotes) / (age_hours + 2)^1.5` — votes × time-decay, gravity-style.
  - **New:** published/ingested date desc.
  - **For You:** existing `for_you_score` desc (phase 8b ranker output).
  - **Top:** net votes desc within trailing 7 days.
- **Pagination:** first page server-rendered; "load more" sentinel calls a new `GET /api/feed?before=<date>` route handler that reads older digest JSON from `data/` server-side and returns items, which the client appends through the active sort.

## Votes

- Reuse Supabase `feedback` table and existing `POST /api/feedback` (`{item_id, signal}` where signal is up/down).
- New `GET /api/votes` → aggregate net counts per item (single grouped count query), response cached ~60s.
- Client `VoteRail`: optimistic ▲/▼ update, revert on failure (existing ItemActions pattern). One vote per item per browser enforced via localStorage guard (soft constraint — acceptable without accounts).
- Because votes are feedback rows, the phase 8b LogisticRegression ranker trains on them automatically: engagement improves For You with no new ML work.

## Saves & Density

- **Saves:** localStorage only (`tl:saves`). `/saved` page renders from it. No server state. Sidebar card shows count with "stored locally, no account needed."
- **Density toggle:** Cards ↔ Compact segmented control above feed. Preference in localStorage (`tl:density`), default **Cards**. Pure client switch — same data, two row renderers.

## Components (replace ItemCard/ItemActions)

- `FeedTabs` — Hot/New/For You/Top pills.
- `PostCard` — rich: vote rail, topic tag, source badge, title, Claude summary, repro tag, actions (save/share/discuss-on-HN link when source=hackernews).
- `PostRow` — compact: vote rail, title + domain, single meta line.
- `VoteRail` — shared by both.
- `DensityToggle`, `SaveButton`, `ShareButton` (navigator.share with copy-link fallback).
- `Sidebar` — `WeeklyCard` (pinned latest synthesis), `TrendingTopics` (topics ranked by Δ item count vs previous digest), `SavesCard`.
- Mobile: sidebar collapses below the feed; vote rail stays left of each item.

## Visual Direction

Keep the existing dark theme, Geist fonts, and amber accent (brand continuity with phases 1–10 polish). Source badge colors stay (arXiv red / HN orange / GitHub neutral / NEWS sky). Board chrome: pill tabs (active = amber), bordered cards `#11161d`-style surface, blue `t/topic` links.

## Error Handling

- Supabase unavailable → vote counts hidden, vote POSTs optimistic-then-revert (existing 8a behavior preserved).
- Missing env vars → routes return 503 as today; UI degrades to read-only board.
- Empty latest digest → pool falls back to older archive digests.
- All server-side loaders stay null-safe (existing pattern).

## Testing

- **Vitest** (new — finally adds the deferred JS harness): feed merge/dedupe, hot/top scoring, vote aggregation shaping, localStorage guards (jsdom).
- **pytest:** untouched, must stay green (46/46).
- **Live verification:** Playwright pass — tab switching, vote optimistic update + Supabase row, density toggle persistence, save → `/saved`, mobile layout.

## Out-of-Scope Future Ideas

Comments, accounts, cross-digest topic aggregation pages, RSS/share images, archive search.
