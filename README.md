# Throughline

**Live:** https://throughline-theta.vercel.app

Self-updating AI research & engineering intelligence hub. A daily Python pipeline fetches
new ML/AI content, writes a dated digest, and a scheduled GitHub Action commits it with a
real timestamp. A Next.js site renders the digest, archive, and (later) weekly synthesis.

## Architecture

```
sources → fetch → dedupe → embed → cluster → rank → summarize (Claude)
  → [weekly: synthesize] → write dated JSON/MDX → commit & push → Vercel ISR
```

## Local setup

### Frontend

```
npm install
npm run dev
```

### Pipeline

```
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
python -m pipeline.run --dry-run          # print, don't write
python -m pipeline.run --date 2026-06-05  # write a specific date
```

## How the daily job works

`.github/workflows/daily-digest.yml` runs on a cron (`0 12 * * *`), executes the pipeline,
and if files changed commits them authored as the repo owner using the GitHub noreply email
(real timestamp, no backdating) and pushes to `main`. Vercel auto-deploys.

## Environment variables

| Var | Purpose | Phase |
|-----|---------|-------|
| `ANTHROPIC_API_KEY` | Claude summaries + synthesis | 7 |
| `ANTHROPIC_MODEL` | model id, defaults to `claude-haiku-4-5` | 7 |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | personalization store | 8 |
| `TAVILY_API_KEY` | AI/ML news source (Tavily Search) | news |

Secrets live in GitHub Actions secrets / Vercel env. Never committed.
```
