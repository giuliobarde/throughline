# Phase 9 — Weekly Synthesis — Design Spec

**Date:** 2026-06-08
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

A weekly Claude-written essay (~400–600 words) that finds the connective theme across the
week's summarized items — the *throughline*. Generated on Sundays by the daily pipeline,
written to `content/synthesis/YYYY-WW.mdx`, and rendered on a `/synthesis` list + reader.

## Decisions locked (2026-06-08)

| Decision | Choice |
|----------|--------|
| Trigger | Auto on Sundays (run.py detects) **+** `--synthesize` flag for manual/backfill |
| Rendering | `react-markdown` — `.mdx` = YAML frontmatter + plain markdown body (no MDX build) |
| Source data | Summaries from the last 7 daily digests up to the run date |
| Model | `claude-haiku-4-5` (env `ANTHROPIC_MODEL`), plain text `messages.create` (no schema) |
| Listing | `/synthesis` globs `content/synthesis/*.mdx` (not tracked in `index.json`) |

## Component: `pipeline/synthesize.py`

### Constants
```
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
DEFAULT_CONTENT_DIR = <repo>/content   (reuse digest.DEFAULT_CONTENT_DIR)
SYNTH_SYSTEM = grounded practitioner voice; ~400-600 word essay connecting the week's
  items into one narrative throughline; no hype, concrete.
LLMText = Callable[[str, str], str]   # (system, user) -> text
```

### `recent_summaries(content_dir, date, days=7) -> list[dict]` (pure)

- For each of the last `days` dates ending at `date` (inclusive), read
  `content_dir/digests/{d}.json` if it exists; collect items where `item.get("summary")` is
  truthy → `{"title", "summary", "topic"}`.
- Missing files are skipped. Returns a flat list (possibly empty).

### `synthesize_week(summaries, llm=None) -> str`

- If `summaries` is empty → return `""`.
- Resolve `llm` (default `_default_text_llm()`); if `None` (no `ANTHROPIC_API_KEY`) → `""`.
- Build a user prompt listing each summary (`- [topic] title — summary`).
- `essay = llm(SYNTH_SYSTEM, prompt)`; on exception → log + `""`.

### `_default_text_llm() -> LLMText | None`

- If no `ANTHROPIC_API_KEY` → `None`.
- Else lazy-import `anthropic`; closure calls `client.messages.create(model=MODEL,
  max_tokens=1200, system=system, messages=[{"role":"user","content":user}])` and returns the
  first text block's `.text`.

### `iso_week(date_str) -> str`

- Parse `YYYY-MM-DD`; `y, w, _ = date.fromisoformat(date_str).isocalendar()`;
  return `f"{y}-{w:02d}"`.

### `write_synthesis(date, essay, content_dir) -> Path`

- `week = iso_week(date)`; ensure `content_dir/synthesis/` exists.
- Write `content_dir/synthesis/{week}.mdx`:
  ```
  ---
  title: "The Throughline — Week {week}"
  week: "{week}"
  date: "{date}"
  ---

  {essay}
  ```
- Return the path.

## Integration: `pipeline/run.py`

- Add `--synthesize` flag (store_true).
- After `write_digest(...)` (write path, not dry-run): if `date.fromisoformat(args.date).weekday()
  == 6` (Sunday) or `args.synthesize`, wrapped in try/except:
  ```
  summaries = recent_summaries(DEFAULT_CONTENT_DIR, args.date)
  essay = synthesize_week(summaries)
  if essay:
      write_synthesis(args.date, essay, DEFAULT_CONTENT_DIR)
  ```
- Failure logs and is skipped (digest already written). Import `date` is already present
  (`from datetime import date as date_cls`) — use `date_cls.fromisoformat`.

## Frontend

New dependency: `react-markdown`.

### `src/lib/synthesis.ts`

- Types: `SynthesisMeta = { week: string; title: string; date: string }`.
- `getSyntheses(): Promise<SynthesisMeta[]>` — read `content/synthesis/`, for each `*.mdx`
  parse the frontmatter block (lines between the first two `---`; `key: "value"` →
  strip quotes) into `SynthesisMeta`; sort by `week` descending. Missing dir → `[]`.
- `getSynthesis(week): Promise<{ meta: SynthesisMeta; body: string } | null>` — read
  `{week}.mdx`, split frontmatter from body (everything after the second `---`), return both;
  missing file → `null`.

### `src/app/synthesis/page.tsx`

- `export const revalidate = 3600`.
- List `getSyntheses()` as rows (week · title · date) linking to `/synthesis/{week}`.
- Empty → "No synthesis essays yet."

### `src/app/synthesis/[week]/page.tsx`

- `generateStaticParams` → `getSyntheses().map(s => ({ week: s.week }))`.
- `export const revalidate = 3600`.
- `getSynthesis(week)`; if null → Next `notFound()`. Render `meta.title` (h1) + the body via
  `<ReactMarkdown>` inside a `prose`-style wrapper (Tailwind typographic classes, since no
  `@tailwindcss/typography` plugin — use explicit `text-neutral-300 leading-relaxed space-y-4`
  container and let react-markdown emit `<p>`/`<h2>`/`<ul>`).

### `src/app/layout.tsx`

- Add a `synthesis` link to the nav (next to `archive` / `about`).

## Testing (pytest, offline)

`tests/test_synthesize.py`:
1. `recent_summaries` over a tmp `content/digests/` with 2 sample digests (one with summaries,
   one without) → returns only the summarized items, skips missing dates.
2. `iso_week("2026-06-07")` returns the correct `"YYYY-WW"` string (assert format + that a
   known Sunday maps as expected via `isocalendar`).
3. `synthesize_week([...], llm=stub)` returns the stub essay; `synthesize_week([], llm=stub)`
   and `synthesize_week([...], llm=None)` (env unset) → `""`.
4. `write_synthesis("2026-06-07", "Body text.", tmp)` writes `synthesis/{week}.mdx` containing
   the frontmatter keys and the body.

Frontend: tsc + build + Playwright (`/synthesis` + a reader page). No JS unit runner (P10).
Pipeline suite stays green (40 tests + new synth tests).

## Error handling

- No `ANTHROPIC_API_KEY` → `synthesize_week` returns `""` → no file written (run continues).
- Empty week (no summaries) → `""` → skipped.
- Any synthesis exception in run.py → caught; digest already written.
- `/synthesis` with no dir/files → empty list; reader for a missing week → `notFound()`.

## Out of scope (YAGNI)

- Full `@next/mdx` / JSX-in-content.
- `gray-matter` (hand-parse 3 frontmatter fields).
- `@tailwindcss/typography` (explicit classes).
- Tracking synthesis in `index.json` (the page globs the dir).
- Regenerate-caching (one cheap call per week).
- Editing/backfilling past weeks beyond the `--synthesize` manual path.
