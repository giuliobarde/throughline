# Throughline

**Live:** https://throughline-theta.vercel.app

A self-updating social board for AI and tech. Every day a Python pipeline pulls new content
from arXiv, Hacker News, GitHub, and Tavily news, then Claude summarizes each item and labels
it into topics. Anonymous votes rank the **Hot** and **Top** tabs and feed the
personalization ranker that powers **For You**. A Next.js site renders it all.

## Features

- **Sort tabs** — Hot, New, For You, Top
- **Vote rails** — anonymous upvote/downvote on every item; counts stored in Supabase
- **Local saves** — bookmark items client-side; browse them at `/saved`
- **Density toggle** — switch between card view and compact list view
- **t/ topic pages** — each Claude-labeled topic gets its own `/topics/[tag]` page
- **Pinned weekly synthesis** — every Sunday Claude writes a synthesis essay; pinned in the sidebar
- **Infinite scroll** — load earlier digests progressively from the archive

## Architecture

```
 sources                      pipeline (daily, GitHub Actions)                     web
┌──────────┐   ┌───────────────────────────────────────────────────────┐   ┌────────────┐
│ arXiv    │   │ fetch → dedupe → embed → cluster → rank(votes)         │   │ Next.js    │
│ Tavily   │──▶│   → summarize + label (Claude) → [Sun: synthesize]     │──▶│ App Router │
│ HN       │   │   → write content/digests/YYYY-MM-DD.json (+ MDX)      │   │ ISR, dark  │
│ GitHub   │   │   → commit (author = you, real timestamp) → push       │   │ social     │
└──────────┘   └───────────────────────────────────────────────────────┘   └────────────┘
                          │                                  ▲   votes (👍/👎)
                          └── data/embeddings cache          └── Supabase ◀── /api routes
```

- **Sources** (`pipeline/sources/`): arXiv export API, Tavily news (AI-lab blogs), Hacker
  News (Algolia), GitHub trending repos. Each exposes `fetch() -> list[Item]`; one failing
  source never kills the run.
- **ML** (`embed.py`, `cluster.py`): sentence-transformers (`all-MiniLM-L6-v2`, cached) →
  KMeans + silhouette topics with TF-IDF labels.
- **Claude** (`summarize.py`, `synthesize.py`): practitioner summaries + `repro_difficulty`,
  Claude-named topic labels, and the weekly synthesis essay (model `claude-haiku-4-5`).
- **Ranking** (`rank.py`): reads 👍/👎 votes from Supabase, trains a LogisticRegression on
  cached embeddings → `for_you_score` (cold-start = recency + source + code until enough
  votes).
- **Web** (`src/`): social board home with Hot/New/For You/Top tabs, t/ topic pages,
  `/saved`, `/archive`, `/synthesis`, `/about`; vote writes go through server route handlers.

## Pages

| Route | What |
|-------|------|
| `/` | Social board — Hot/New/For You/Top tabs, vote rails, density toggle, infinite scroll |
| `/topics` | All Claude-labeled topic tags from the latest digest |
| `/topics/[tag]` | One topic's items (t/ community view) |
| `/saved` | Locally bookmarked items |
| `/archive` | Past digests by date |
| `/synthesis` | Weekly synthesis essays (list + reader) |
| `/about` | What it is / how it's built |

## Local setup

### Frontend

```
npm install
npm run dev          # http://localhost:3000
```

### Pipeline

```
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
python -m pipeline.run --dry-run            # fetch + print, write nothing
python -m pipeline.run --date 2026-06-09    # write a dated digest
python -m pipeline.run --synthesize         # also force the weekly essay
pytest                                       # pipeline test suite
```

Copy `.env.example` to `.env` and fill keys to enable Claude, Tavily, and Supabase locally
(the pipeline degrades gracefully without them — sources/summaries/ranking just no-op).

## How the daily job works

`.github/workflows/daily-digest.yml` runs on cron (`0 12 * * *`, plus manual dispatch). It
runs the pipeline and, **if the content changed**, commits `content/` + `data/` authored as
the repo owner via the GitHub **noreply** email and pushes to `main`; Vercel auto-deploys.

**Honest commits:** real timestamps only, never backdated, no rewritten author dates, no
Claude trailer. The contribution graph fills because the Action does real work each day.

Required GitHub Actions **secrets**: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY` (`GITHUB_TOKEN` is auto-provided). Without them the run still
commits a digest, just with fewer sources / no summaries / cold-start ranking.

## Environment variables

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude summaries, topic labels, weekly synthesis |
| `ANTHROPIC_MODEL` | model id (defaults to `claude-haiku-4-5`) |
| `TAVILY_API_KEY` | AI/ML news source (Tavily Search) |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | votes + ranking store |
| `GITHUB_TOKEN` | GitHub source rate limit (auto-provided in CI) |

Secrets live in GitHub Actions secrets / Vercel env. Never committed (`.env` is gitignored).

## Tech stack

Next.js (App Router, TypeScript, Tailwind, ISR) · Python 3.12 (httpx, sentence-transformers,
scikit-learn, anthropic) · Supabase (Postgres) · GitHub Actions · Vercel.
