# Throughline

**Live:** https://throughline-theta.vercel.app

A self-updating AI research & engineering intelligence hub. Every day a Python pipeline pulls
new ML/AI content from several sources, clusters it into topics, writes opinionated
practitioner summaries with Claude, ranks it against your feedback, and a scheduled GitHub
Action commits the dated digest with a **real timestamp**. On Sundays it also writes a longer
synthesis essay — the *throughline* of the week. A Next.js site renders it all.

## Architecture

```
 sources                      pipeline (daily, GitHub Actions)                     web
┌──────────┐   ┌───────────────────────────────────────────────────────┐   ┌────────────┐
│ arXiv    │   │ fetch → dedupe → embed → cluster → rank(feedback)      │   │ Next.js    │
│ Tavily   │──▶│   → summarize + label (Claude) → [Sun: synthesize]     │──▶│ App Router │
│ HN       │   │   → write content/digests/YYYY-MM-DD.json (+ MDX)      │   │ ISR, dark  │
│ GitHub   │   │   → commit (author = you, real timestamp) → push       │   │ editorial  │
└──────────┘   └───────────────────────────────────────────────────────┘   └────────────┘
                          │                                  ▲   feedback (👍/👎, read)
                          └── data/embeddings cache          └── Supabase ◀── /api routes
```

- **Sources** (`pipeline/sources/`): arXiv export API, Tavily news (AI-lab blogs), Hacker
  News (Algolia), GitHub trending repos. Each exposes `fetch() -> list[Item]`; one failing
  source never kills the run.
- **ML** (`embed.py`, `cluster.py`): sentence-transformers (`all-MiniLM-L6-v2`, cached) →
  KMeans + silhouette topics with TF-IDF labels.
- **Claude** (`summarize.py`, `synthesize.py`): practitioner summaries + `repro_difficulty`,
  Claude-named topic labels, and the weekly synthesis essay (model `claude-haiku-4-5`).
- **Ranking** (`rank.py`): reads 👍/👎 feedback from Supabase, trains a LogisticRegression on
  cached embeddings → `for_you_score` (cold-start = recency + source + code until enough
  feedback).
- **Web** (`src/`): today's digest grouped into topics with a "For You" strip, `/archive`,
  `/topics/[tag]`, `/synthesis`, `/about`; feedback writes go through server route handlers.

## Pages

| Route | What |
|-------|------|
| `/` | Today's digest — For You strip + topic sections, item cards (summary, code/repro tags, 👍/👎, read) |
| `/archive` | Past digests by date |
| `/topics/[tag]` | One topic's items from the latest digest |
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
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | feedback + ranking store |
| `GITHUB_TOKEN` | GitHub source rate limit (auto-provided in CI) |

Secrets live in GitHub Actions secrets / Vercel env. Never committed (`.env` is gitignored).

## Tech stack

Next.js (App Router, TypeScript, Tailwind, ISR) · Python 3.12 (httpx, sentence-transformers,
scikit-learn, anthropic) · Supabase (Postgres) · GitHub Actions · Vercel.
