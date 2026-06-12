# Throughline

**Live:** https://throughline-theta.vercel.app

A self-updating social board for AI and tech. Every three hours a Python pipeline pulls new
content from arXiv, Hacker News, GitHub, first-party vendor blogs (OpenAI, DeepMind, Google
AI, Hugging Face), and Tavily news, then Claude summarizes each item and labels it into
topics. Anonymous votes rank the **Hot** and **Top** tabs and feed the personalization
ranker that powers **For You**. Everything lives in Supabase; a Next.js site renders it.

## Features

- **Sort tabs** — Hot, New, For You, Top
- **Vote rails** — anonymous upvote/downvote on every item; counts shared across devices
- **Archive-wide search** — alias-aware (claude ⇄ anthropic), domain queries
  (`anthropic.com`), live dropdown; archive reaches back to 2026-01-01
- **Local saves** — bookmark items client-side; browse them at `/saved`
- **Density toggle** — switch between card view and compact list view
- **t/ topic pages** — each Claude-labeled topic gets its own `/topics/[tag]` page
- **Pinned weekly synthesis** — every Sunday Claude writes a synthesis essay; pinned in the sidebar
- **Infinite scroll** — page back through the whole archive
- **Hardened** — per-IP rate limits, input validation, security headers, OG/social cards

## Architecture

```
 sources                   pipeline (every 3h, GitHub Actions)                 web
┌──────────┐   ┌─────────────────────────────────────────────────┐   ┌─────────────────┐
│ arXiv    │   │ fetch → dedupe (incl. cross-source by title)     │   │ Next.js         │
│ blogs    │──▶│   → merge with today's digest → embed → cluster  │   │ App Router, ISR │
│ Tavily   │   │   → summarize + label (Claude) → rank(votes)     │   │ reads Supabase  │
│ HN       │   │   → upsert digest row → [Sun: synthesis row]     │   │                 │
│ GitHub   │   └────────────────────┬────────────────────────────┘   └────────┬────────┘
└──────────┘                        ▼                                          ▼
                          Supabase (Postgres + JSONB)  ◀── votes via /api ── visitors
                          digests · syntheses · kv_cache · feedback
```

- **Sources** (`pipeline/sources/`): arXiv export API, vendor-blog RSS + Tavily fallback,
  Hacker News (Algolia), GitHub trending repos, Tavily news. Each exposes
  `fetch() -> list[Item]`; one failing source never kills the run.
- **Store** (`store.py`): PostgREST layer over Supabase — digests and syntheses as JSONB
  rows, embedding/summary caches in `kv_cache`. Storage failures fail the run loudly.
- **ML** (`embed.py`, `cluster.py`): sentence-transformers (`all-MiniLM-L6-v2`, cached in
  Supabase) → KMeans + silhouette topics with TF-IDF labels.
- **Claude** (`summarize.py`, `synthesize.py`): practitioner summaries + `repro_difficulty`,
  Claude-named topic labels, and the weekly synthesis essay (model `claude-haiku-4-5`).
- **Ranking** (`rank.py`): reads 👍/👎 votes from Supabase, trains a LogisticRegression on
  cached embeddings → `for_you_score` (cold-start = recency + source + code until enough
  votes).
- **Web** (`src/`): board home with Hot/New/For You/Top tabs, archive-wide `/search`, t/
  topic pages, `/saved`, `/archive`, `/synthesis`, `/about`; vote writes go through
  rate-limited server route handlers.

## Pages

| Route | What |
|-------|------|
| `/` | Social board — Hot/New/For You/Top tabs, vote rails, density toggle, infinite scroll |
| `/search` | Archive-wide search (aliases, domains) |
| `/topics` | All Claude-labeled topic tags from the latest digest |
| `/topics/[tag]` | One topic's items (t/ community view) |
| `/saved` | Locally bookmarked items |
| `/archive` | Past digests by date |
| `/synthesis` | Weekly synthesis essays (list + reader) |
| `/about` | What it is / how it's built |

## Local setup

Copy `.env.example` to `.env`. `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are **required**
(both the site and the pipeline read/write Supabase); the other keys enable Claude, Tavily,
and higher GitHub rate limits.

### Frontend

```
npm install
npm run dev          # http://localhost:3000
npm test             # vitest
```

### Pipeline

```
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
python -m pipeline.run --dry-run            # fetch + print, write nothing
python -m pipeline.run --date 2026-06-12    # upsert a dated digest to Supabase
python -m pipeline.run --synthesize         # also force the weekly essay
python -m pytest                            # pipeline test suite
```

There is also a dispatchable backfill (`.github/workflows/backfill.yml`,
`python -m pipeline.backfill --from ... --to ...`) that fetches historical ranges and
Claude-selects 1–5 milestone items per week to summarize.

## How the scheduled job works

`.github/workflows/daily-digest.yml` runs on cron (`0 */3 * * *`, plus manual dispatch). It
runs the pipeline, which merges new items into today's digest row in Supabase — same-day
reruns never lose earlier items, summaries, or topics. No data is committed to the repo.

Required GitHub Actions **secrets**: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (storage —
the run fails loudly without them), plus `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` for
summaries/labels/news (`GITHUB_TOKEN` is auto-provided).

## Environment variables

| Var | Purpose |
|-----|---------|
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | **required** — digests, caches, votes |
| `ANTHROPIC_API_KEY` | Claude summaries, topic labels, weekly synthesis |
| `ANTHROPIC_MODEL` | model id (defaults to `claude-haiku-4-5`) |
| `TAVILY_API_KEY` | AI/ML news source + no-RSS vendor blogs |
| `GITHUB_TOKEN` | GitHub source rate limit (auto-provided in CI) |
| `SITE_URL` | optional — canonical origin for metadata/sitemap (custom domain) |

Secrets live in GitHub Actions secrets / Vercel env. Never committed (`.env` is gitignored).

## Tech stack

Next.js (App Router, TypeScript, Tailwind, ISR) · Python 3.12 (httpx, sentence-transformers,
scikit-learn, anthropic) · Supabase (Postgres + JSONB) · GitHub Actions · Vercel.
