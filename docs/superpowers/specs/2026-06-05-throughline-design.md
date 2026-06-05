# Throughline — Design Spec

**Date:** 2026-06-05
**Owner:** Giulio (data scientist / full-stack engineer)
**Status:** Approved, pre-implementation

## What it is

A self-updating AI research & engineering intelligence hub. A daily Python pipeline
fetches new ML/AI content, processes it, and writes a dated digest file that a GitHub
Action commits with a real timestamp. A Next.js site renders the digest, archive,
topics, and a weekly synthesis essay, and lets the user mark items interesting/read.

Personal product. Production quality: clean code, honest git history, deployed.

## Non-negotiable principle: honest commits

- **No backdating.** No author-date rewriting. Every commit uses the real current timestamp.
- The contribution graph fills honestly: the scheduled Action does real work daily and
  commits the generated digest.
- The Action authors commits as the user via the GitHub `noreply` email (verified, counts
  toward the graph). Repo owned by the user.
- During the build, commit incrementally — one focused commit per phase — for a genuine,
  readable history.
- **Never add a Claude trailer / co-author line to repo commits.**

## Decisions locked (2026-06-05)

| Decision | Choice |
|----------|--------|
| Repo name | `throughline` |
| Repo visibility | **Public** (contribution graph counts with no extra config; doubles as portfolio) |
| Personalization store | **Supabase** (Postgres; cross-device; enables learned ranker in CI) |
| Claude model | **Haiku 4.5** (`claude-haiku-4-5`) for summaries AND synthesis; behind env var `ANTHROPIC_MODEL` so swappable to Sonnet later |
| Build approach | MVP slice first, then stack layers (see phase order below) |

## Tech stack

- **Frontend:** Next.js (App Router) + TypeScript (strict) + Tailwind. Static generation + ISR
  (`revalidate`). Content driven by committed JSON/MDX. No client-side secrets.
- **Pipeline:** Python 3.11+ (3.12 present locally). `httpx`, `arxiv`/arXiv export API,
  `feedparser`, `sentence-transformers` (`all-MiniLM-L6-v2`, free in CI), `scikit-learn`
  (clustering + ranker), `hdbscan` (optional), `anthropic`, `python-dotenv`.
- **Store:** Supabase (Postgres).
- **Automation:** GitHub Actions, daily cron.
- **Deploy:** Vercel.

## Architecture

```
sources → fetch → dedupe → embed → cluster (topics) → rank (personalization) →
summarize (Claude) → [weekly: synthesize] → write dated file → commit & push → Vercel ISR
```

Pipeline must be:
- **Idempotent** — re-running for the same date overwrites cleanly.
- **Fault-tolerant** — one failing source logs and is skipped; the run continues.
- **Cheap** — cap items sent to Claude (~15–20/day); cache embeddings in the repo.

## Repo structure

```
/app                 # Next.js App Router
/components
/lib                 # ts helpers, supabase client, content loaders
/content
  /digests           # YYYY-MM-DD.json  (committed daily)
  /synthesis         # YYYY-WW.mdx
  index.json
/pipeline
  sources/           # one module per source, common fetch() -> list[Item]
  embed.py
  cluster.py
  rank.py
  summarize.py
  synthesize.py
  run.py             # entrypoint, --date and --dry-run flags
  requirements.txt
/data/embeddings     # cached vectors keyed by item id
/.github/workflows/daily-digest.yml
README.md
```

## Data contracts

**Item** (Python dataclass, also the JSON shape):
```
id: str
source: str            # "arxiv" | "hackernews" | "github"
title: str
url: str
abstract: str          # abstract / text body
authors: list[str]
published_at: str       # ISO 8601
has_code: bool
code_url: str | None
```

**Digest file** `content/digests/YYYY-MM-DD.json`:
```
{
  "date": "YYYY-MM-DD",
  "generated_at": "<ISO timestamp>",
  "items": [ Item + optional {summary, topic, repro_difficulty, for_you_score} ],
  "topics": [ {tag, label, item_ids[]} ]   // empty until Phase 6
}
```

**Manifest** `content/index.json`:
```
[ { "date": "YYYY-MM-DD", "item_count": N, "has_synthesis": bool } ]
```

## Data sources (official APIs only — no scraping)

- **arXiv** — export API (`http://export.arxiv.org/api/query`) or `arxiv` package.
  Categories `cs.LG, cs.CL, cs.AI, cs.MA`. Last 24–48h, dedupe by arXiv id.
- **Hacker News** — Algolia `search_by_date`, AI/ML keyword filter, min-points threshold.
- **GitHub trending** — REST Search API (`created:>{7d}` / `pushed:`, sort by stars, Python,
  ML topics). No trending-page scraping.

Each source: a module exposing `fetch() -> list[Item]`.

## Pipeline detail

- Normalize all sources to `Item`.
- Embed title+abstract with sentence-transformers; cache vectors in `data/embeddings/` by id.
- Cluster into topics (HDBSCAN, or KMeans with silhouette-chosen k). Claude-label each cluster.
- **Ranker:** if Supabase feedback exists, train `LogisticRegression` on embeddings → P(interesting),
  rank within topics + set a "for you" score. Cold-start: recency + source signal (HN points, stars).
- **Summaries:** top N (~15–20). Tight system prompt. Voice = grounded, concrete, no hype.
  Each: 2–3 sentences (what it is + why a shipping-ML practitioner should care) + one line
  "code: yes/no, reproduction difficulty: low/med/high".
- **Weekly synthesis (Sundays):** feed the week's summaries to Claude → ~400–600 word essay
  finding the connective theme. Same voice. Write to `content/synthesis/YYYY-WW.mdx`.

## Frontend

Pages:
- `/` — today's digest: topic sections, item cards (title, source badge, summary, code/repro
  tags, links, thumbs up/down + read toggle), a "for you" highlight strip.
- `/archive` — date list + client-side full-text search (fuse.js) over titles/summaries.
- `/topics/[tag]` — filtered view.
- `/synthesis` — list + reader view of weekly essays (MDX).
- `/about` — what it is / how it's built (portfolio explainer).

Design: sharp editorial/terminal feel, strong typographic hierarchy, generous whitespace,
monospace metadata accents, restrained palette, subtle motion. Apply `frontend-design` skill.
Dark-mode default, fully responsive, accessible (semantic HTML, keyboard nav, contrast).
No `<form>` antipatterns — proper event handlers.

Content loads from committed JSON/MDX at build time with ISR. Feedback/read writes go to
Supabase via a Next.js route handler (server-side key).

## Supabase schema

```sql
create table feedback (
  id uuid primary key default gen_random_uuid(),
  item_id text not null,
  item_embedding vector,
  signal smallint not null,        -- 1 interesting, -1 not, 0 neutral
  created_at timestamptz default now()
);
create table read_state (
  item_id text primary key,
  read boolean default false,
  updated_at timestamptz default now()
);
```

## GitHub Action — honest daily commit

`.github/workflows/daily-digest.yml`:
- Trigger: `schedule` cron `0 12 * * *` + `workflow_dispatch`.
- Steps: checkout → setup Python → cache pip + ST model → run pipeline → if files changed,
  set git author = user (noreply email), commit `chore(digest): YYYY-MM-DD`, push to `main`.
- `ANTHROPIC_API_KEY` + Supabase keys from Actions **secrets**. `GITHUB_TOKEN` auto-provided.
- Real timestamps only. After push, Vercel auto-rebuilds (or ISR `revalidate`).

## Environment variables / secrets

- `ANTHROPIC_API_KEY` — Claude summaries + synthesis.
- `ANTHROPIC_MODEL` — defaults to `claude-haiku-4-5`.
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
- `GITHUB_TOKEN` — auto in Actions.

All documented in README. Never committed.

## Phase order (MVP-first; Action+deploy promoted to Phase 4)

1. **Scaffold** — Next.js+TS+Tailwind app, git init, README skeleton, `/about` placeholder. Commit.
2. **Pipeline skeleton** — `Item` model, arXiv source, `run.py` writes a sample digest JSON +
   `index.json`. `--date` / `--dry-run` flags. Commit.
3. **Frontend reads content** — `/` renders today's digest from JSON (flat list, no topics yet);
   item cards; `/archive` list. ISR. Commit.
4. **Automation + deploy (PROMOTED)** — `daily-digest.yml` honest daily commit (author = user,
   real timestamps); Vercel project + auto-deploy. Test via `workflow_dispatch`. Honest daily
   loop live + deployed here, even when the digest is a raw arXiv pull. Commit.
5. **More sources** — Hacker News + GitHub trending. Dedupe. Commit.
6. **ML layer** — embeddings + clustering + Claude topic labels. Commit.
7. **Claude summaries** — Anthropic API, practitioner-voice prompt, item caps + caching. Commit.
8. **Personalization** — Supabase tables, feedback/read UI, route handlers, LogisticRegression
   ranker reading feedback in CI. Commit.
9. **Weekly synthesis** — Sunday Claude essay → MDX → `/synthesis`. Commit.
10. **Polish + deploy** — apply `frontend-design`, dark mode, search, responsive pass, finish
    README. Commit.

## Quality bar

- TypeScript strict, no unjustified `any`. ESLint + Prettier.
- Pipeline: typed dataclasses, logging, graceful per-source failure, `--date` + `--dry-run`.
- Real README: what it is, architecture diagram, local setup, how the daily job works.
- Conventional Commits.

## Needed at Phase 4 (not before)

- GitHub username + noreply email (for commit authoring).
- `ANTHROPIC_API_KEY` (Phase 7), Supabase project + keys (Phase 8).

## Out of scope (YAGNI)

- No scraping of any kind.
- No auth/multi-user — single owner.
- No client-side secrets.
- No backdated or rewritten commit history.
