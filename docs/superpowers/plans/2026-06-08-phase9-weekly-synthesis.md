# Phase 9 — Weekly Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a weekly Claude essay connecting the week's summarized items, write it to `content/synthesis/YYYY-WW.mdx`, and render it on `/synthesis`.

**Architecture:** `pipeline/synthesize.py` gathers the last 7 days of summarized items, asks Claude (injectable text LLM) for a ~400–600 word essay, and writes an `.mdx` (frontmatter + markdown body). `run.py` triggers it on Sundays or via `--synthesize`. The frontend lists essays and renders one with `react-markdown`.

**Tech Stack:** Python 3.12 (`anthropic`, `pytest` — present); Next.js + `react-markdown`.

**API note (claude-api skill):** Haiku 4.5 → plain `messages.create`, no `effort`/`thinking`; text output (no `output_config`). Injectable `llm` keeps tests offline.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/synthesize.py        # NEW — recent_summaries, synthesize_week, iso_week, write_synthesis, _default_text_llm
/pipeline/run.py               # MODIFY — --synthesize flag + Sunday trigger
/tests/test_synthesize.py      # NEW
/content/synthesis/.gitkeep    # NEW
/package.json                  # MODIFY — add react-markdown
/src/lib/synthesis.ts          # NEW — getSyntheses, getSynthesis
/src/app/synthesis/page.tsx    # NEW — list
/src/app/synthesis/[week]/page.tsx  # NEW — reader
/src/app/layout.tsx            # MODIFY — nav link
```

---

### Task 1: recent_summaries + iso_week (pure)

**Files:**
- Create: `pipeline/synthesize.py`
- Create: `tests/test_synthesize.py`
- Create: `content/synthesis/.gitkeep`

- [ ] **Step 1: Write the failing test**

Create `tests/test_synthesize.py`:

```python
import json
from pathlib import Path

from pipeline.synthesize import recent_summaries, iso_week


def _write_digest(content: Path, date: str, items: list[dict]) -> None:
    d = content / "digests"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}.json").write_text(json.dumps({"date": date, "items": items, "topics": []}))


def test_recent_summaries_collects_only_summarized(tmp_path: Path):
    content = tmp_path / "content"
    _write_digest(content, "2026-06-07", [
        {"title": "A", "summary": "sumA", "topic": "t1"},
        {"title": "B"},  # no summary -> skipped
    ])
    _write_digest(content, "2026-06-06", [
        {"title": "C", "summary": "sumC", "topic": "t2"},
    ])
    # 2026-06-05 missing -> skipped silently
    out = recent_summaries(content, "2026-06-07", days=3)
    titles = {s["title"] for s in out}
    assert titles == {"A", "C"}
    assert all("summary" in s for s in out)


def test_iso_week_format():
    # 2026-06-07 is a Sunday; isocalendar week for it:
    assert iso_week("2026-06-07") == "2026-23"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_synthesize.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.synthesize).

(If `test_iso_week_format` later fails on the exact week number, correct the expected value to
whatever `python -c "import datetime;print(datetime.date.fromisoformat('2026-06-07').isocalendar())"`
reports — the format `YYYY-WW` is what matters.)

- [ ] **Step 3: Write the pure helpers**

Create `pipeline/synthesize.py`:

```python
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from pipeline.digest import DEFAULT_CONTENT_DIR

log = logging.getLogger("throughline")

LLMText = Callable[[str, str], str]

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

SYNTH_SYSTEM = (
    "You write a weekly synthesis for engineers who ship ML systems. Given short "
    "summaries of the week's notable items, write a single ~400-600 word essay that "
    "finds the connective theme across them - the throughline. Grounded and concrete, "
    "no hype, no bullet lists; flowing prose with a clear argument."
)


def recent_summaries(content_dir: Path, date_str: str, days: int = 7) -> list[dict]:
    end = date.fromisoformat(date_str)
    out: list[dict] = []
    for i in range(days):
        d = (end - timedelta(days=i)).isoformat()
        path = content_dir / "digests" / f"{d}.json"
        if not path.exists():
            continue
        digest = json.loads(path.read_text())
        for item in digest.get("items", []):
            if item.get("summary"):
                out.append(
                    {
                        "title": item.get("title", ""),
                        "summary": item["summary"],
                        "topic": item.get("topic"),
                    }
                )
    return out


def iso_week(date_str: str) -> str:
    y, w, _ = date.fromisoformat(date_str).isocalendar()
    return f"{y}-{w:02d}"
```

Create empty `content/synthesis/.gitkeep`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_synthesize.py -v`
Expected: PASS (2 passed). If `iso_week` value differs, fix the test's expected string per the
note in Step 2.

- [ ] **Step 5: Commit**

```bash
git add pipeline/synthesize.py tests/test_synthesize.py content/synthesis/.gitkeep
git commit -m "feat(pipeline): add recent_summaries and iso_week helpers"
```

---

### Task 2: synthesize_week + write_synthesis

**Files:**
- Modify: `pipeline/synthesize.py`
- Modify: `tests/test_synthesize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_synthesize.py`:

```python
from pipeline.synthesize import synthesize_week, write_synthesis


def test_synthesize_week_with_stub():
    captured = {}

    def stub(system, user):
        captured["user"] = user
        return "The week's throughline essay."

    summaries = [{"title": "A", "summary": "sumA", "topic": "t1"}]
    essay = synthesize_week(summaries, llm=stub)
    assert essay == "The week's throughline essay."
    assert "sumA" in captured["user"]


def test_synthesize_week_empty_or_no_llm():
    assert synthesize_week([], llm=lambda s, u: "x") == ""


def test_synthesize_week_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert synthesize_week([{"title": "A", "summary": "s", "topic": None}], llm=None) == ""


def test_write_synthesis_creates_mdx(tmp_path: Path):
    content = tmp_path / "content"
    path = write_synthesis("2026-06-07", "Body text here.", content)
    assert path.name == "2026-23.mdx"
    text = path.read_text()
    assert 'week: "2026-23"' in text
    assert 'date: "2026-06-07"' in text
    assert "Body text here." in text
    assert text.startswith("---")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_synthesize.py -k "synthesize_week or write_synthesis" -v`
Expected: FAIL (cannot import name 'synthesize_week').

- [ ] **Step 3: Add the functions**

Append to `pipeline/synthesize.py`:

```python
def _default_text_llm() -> Optional[LLMText]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set; skipping synthesis")
        return None
    import anthropic

    client = anthropic.Anthropic()

    def call(system: str, user: str) -> str:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )

    return call


def _synth_prompt(summaries: list[dict]) -> str:
    lines = ["This week's items:", ""]
    for s in summaries:
        topic = s.get("topic") or "general"
        lines.append(f"- [{topic}] {s['title']} - {s['summary']}")
    return "\n".join(lines)


def synthesize_week(summaries: list[dict], llm: Optional[LLMText] = None) -> str:
    if not summaries:
        return ""
    call = llm if llm is not None else _default_text_llm()
    if call is None:
        return ""
    try:
        return call(SYNTH_SYSTEM, _synth_prompt(summaries))
    except Exception:
        log.exception("synthesis failed")
        return ""


def write_synthesis(
    date_str: str, essay: str, content_dir: Path = DEFAULT_CONTENT_DIR
) -> Path:
    week = iso_week(date_str)
    out_dir = content_dir / "synthesis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{week}.mdx"
    front = (
        "---\n"
        f'title: "The Throughline - Week {week}"\n'
        f'week: "{week}"\n'
        f'date: "{date_str}"\n'
        "---\n\n"
    )
    out.write_text(front + essay + "\n")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_synthesize.py -v`
Expected: PASS (all synth tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/synthesize.py tests/test_synthesize.py
git commit -m "feat(pipeline): add weekly synthesis essay generation and writer"
```

---

### Task 3: Trigger synthesis in run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Add the import + flag**

In `pipeline/run.py`, add to the imports:

```python
from pipeline.synthesize import recent_summaries, synthesize_week, write_synthesis
```

In `main()`, add the flag next to the existing args:

```python
    parser.add_argument(
        "--synthesize", action="store_true", help="force weekly synthesis"
    )
```

- [ ] **Step 2: Expose DEFAULT_CONTENT_DIR via the digest import**

In `pipeline/run.py`, change the existing `from pipeline.digest import write_digest` line to:

```python
from pipeline.digest import DEFAULT_CONTENT_DIR, write_digest
```

- [ ] **Step 3: Trigger after write_digest**

In `pipeline/run.py`, immediately after `log.info("wrote %s", out)` (end of `main`), add:

```python
    is_sunday = date_cls.fromisoformat(args.date).weekday() == 6
    if is_sunday or args.synthesize:
        try:
            summaries = recent_summaries(DEFAULT_CONTENT_DIR, args.date)
            essay = synthesize_week(summaries)
            if essay:
                log.info("wrote synthesis %s", write_synthesis(args.date, essay))
            else:
                log.info("no synthesis written (empty essay)")
        except Exception:
            log.exception("synthesis step failed; digest already written")
```

- [ ] **Step 4: Full test suite + dry-run sanity**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (40 + synth 6 = 46).
Run: `.venv/bin/python -m pipeline.run --dry-run`
Expected: prints items JSON, returns (dry-run skips digest + synthesis). No crash.

- [ ] **Step 5: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): trigger weekly synthesis on Sundays or --synthesize"
```

---

### Task 4: react-markdown dependency

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install**

Run: `npm install react-markdown`
Expected: adds `react-markdown` to `dependencies`.

- [ ] **Step 2: Build sanity**

Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore(web): add react-markdown"
```

---

### Task 5: synthesis loaders

**Files:**
- Create: `src/lib/synthesis.ts`

- [ ] **Step 1: Write the loaders**

Create `src/lib/synthesis.ts`:

```ts
import { promises as fs } from "fs";
import path from "path";

export type SynthesisMeta = { week: string; title: string; date: string };

const DIR = path.join(process.cwd(), "content", "synthesis");

function parseFrontmatter(raw: string): { meta: SynthesisMeta; body: string } {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  const fields: Record<string, string> = {};
  if (m) {
    for (const line of m[1].split("\n")) {
      const idx = line.indexOf(":");
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      let val = line.slice(idx + 1).trim();
      if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
      fields[key] = val;
    }
  }
  return {
    meta: {
      week: fields.week ?? "",
      title: fields.title ?? "",
      date: fields.date ?? "",
    },
    body: (m ? m[2] : raw).trim(),
  };
}

export async function getSyntheses(): Promise<SynthesisMeta[]> {
  let files: string[];
  try {
    files = await fs.readdir(DIR);
  } catch {
    return [];
  }
  const out: SynthesisMeta[] = [];
  for (const f of files) {
    if (!f.endsWith(".mdx")) continue;
    const raw = await fs.readFile(path.join(DIR, f), "utf-8");
    out.push(parseFrontmatter(raw).meta);
  }
  return out.sort((a, b) => (a.week < b.week ? 1 : -1));
}

export async function getSynthesis(
  week: string,
): Promise<{ meta: SynthesisMeta; body: string } | null> {
  try {
    const raw = await fs.readFile(path.join(DIR, `${week}.mdx`), "utf-8");
    return parseFrontmatter(raw);
  } catch {
    return null;
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/synthesis.ts
git commit -m "feat(web): add synthesis content loaders"
```

---

### Task 6: /synthesis list page

**Files:**
- Create: `src/app/synthesis/page.tsx`

- [ ] **Step 1: Write the page**

Create `src/app/synthesis/page.tsx`:

```tsx
import { getSyntheses } from "@/lib/synthesis";

export const revalidate = 3600;

export default async function SynthesisPage() {
  const essays = await getSyntheses();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Synthesis</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">
        Weekly throughlines across the digest.
      </p>
      {essays.length === 0 ? (
        <p className="mt-6 text-neutral-500">No synthesis essays yet.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {essays.map((e) => (
            <li key={e.week} className="py-3">
              <a href={`/synthesis/${e.week}`} className="group block">
                <span className="font-mono text-xs text-neutral-500">
                  {e.week} · {e.date}
                </span>
                <span className="mt-1 block font-semibold group-hover:underline">
                  {e.title}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors; `/synthesis` in route list.

- [ ] **Step 3: Commit**

```bash
git add src/app/synthesis/page.tsx
git commit -m "feat(web): add synthesis list page"
```

---

### Task 7: /synthesis/[week] reader page

**Files:**
- Create: `src/app/synthesis/[week]/page.tsx`

- [ ] **Step 1: Write the reader**

Create `src/app/synthesis/[week]/page.tsx`:

```tsx
import ReactMarkdown from "react-markdown";
import { notFound } from "next/navigation";
import { getSyntheses, getSynthesis } from "@/lib/synthesis";

export const revalidate = 3600;

export async function generateStaticParams() {
  const essays = await getSyntheses();
  return essays.map((e) => ({ week: e.week }));
}

export default async function SynthesisReader({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const doc = await getSynthesis(week);
  if (!doc) notFound();

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="font-mono text-xs text-neutral-500">
        {doc.meta.week} · {doc.meta.date}
      </p>
      <h1 className="mt-1 text-2xl font-bold">{doc.meta.title}</h1>
      <div className="mt-6 space-y-4 leading-relaxed text-neutral-300 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-neutral-100">
        <ReactMarkdown>{doc.body}</ReactMarkdown>
      </div>
    </main>
  );
}
```

(Note: `params` is a Promise in this Next.js version — the home/archive pages don't use
params, but route segments with `[week]` receive an async `params`. Awaiting it is required.)

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors. With no `.mdx` files, `generateStaticParams` returns `[]` and the dynamic
segment still builds.

- [ ] **Step 3: Commit**

```bash
git add "src/app/synthesis/[week]/page.tsx"
git commit -m "feat(web): add synthesis reader page"
```

---

### Task 8: Nav link

**Files:**
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Add the link**

In `src/app/layout.tsx`, in the nav `<div>` that holds the `archive` and `about` links, add a
`synthesis` link before `about`:

```tsx
              <a href="/synthesis" className="hover:text-neutral-100">
                synthesis
              </a>
```

- [ ] **Step 2: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no errors.

- [ ] **Step 3: Commit + push**

```bash
git add src/app/layout.tsx
git commit -m "feat(web): add synthesis nav link"
git push
```

---

### Task 9: Live verification

**Files:** none

- [ ] **Step 1: Backfill a synthesis essay (manual flag)**

There must be at least one daily digest with summaries in `content/digests/` for the last 7
days. If none committed have summaries, first generate today's digest locally:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-08
```
Then force synthesis:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-08 --synthesize
```
Expected: logs `wrote synthesis content/synthesis/2026-XX.mdx`. Inspect:
```bash
ls content/synthesis/ && head -20 content/synthesis/*.mdx
```

- [ ] **Step 2: Visual check**

`set -a && . ./.env && set +a && npm run dev`; Playwright `http://localhost:3000/synthesis`
(list shows the essay) → click into `/synthesis/{week}` (reader renders title + prose).
Screenshot both.

- [ ] **Step 3: Restore + stop**

Remove hand-run artifacts (do not commit a locally-generated digest/essay; the Sunday Action
produces the real one):
```bash
git checkout content/index.json 2>/dev/null
rm -f content/digests/2026-06-08.json data/summaries/cache.json data/embeddings/cache.json content/synthesis/2026-*.mdx
git checkout data 2>/dev/null
pkill -f "next dev"; pkill -f "next-server"
```
(If `content/digests/2026-06-08.json` is a committed Action digest, `git checkout` it instead
of `rm`.)

- [ ] **Step 4: Confirm tests + clean tree**

```bash
.venv/bin/python -m pytest tests/ -q   # 46 passed
git status --short                      # clean
```

---

## Self-review notes

- **Spec coverage:** recent_summaries + iso_week (T1), synthesize_week + write_synthesis +
  text LLM (T2), run.py Sunday/--synthesize trigger (T3), react-markdown dep (T4), loaders
  (T5), list page (T6), reader + generateStaticParams (T7), nav (T8), live verify (T9). All
  spec sections mapped.
- **API correctness:** Haiku via plain `messages.create`, text output, no effort/thinking;
  `ANTHROPIC_MODEL` env default; no-key → `""`. Injectable `llm` → offline tests.
- **Type consistency:** `recent_summaries(content_dir, date_str, days) -> list[dict]`;
  `synthesize_week(summaries, llm) -> str`; `iso_week(date_str) -> str`;
  `write_synthesis(date_str, essay, content_dir) -> Path`. TS `SynthesisMeta {week,title,date}`
  produced by `getSyntheses`/`getSynthesis` and consumed by both pages. `.mdx` filename =
  `{week}.mdx` on both write (Python) and read (TS).
- **Placeholder scan:** none. The `if False` snippet in T3 is explicitly marked as the
  wrong version with the clean replacement shown immediately after — the engineer writes only
  the clean import + body.
- **Test math:** 40 prior + 6 synth (2 T1 + 4 T2) = 46.
- **Frontend:** no JS unit runner (consistent w/ P8); tsc/build/Playwright. `params` awaited
  (this Next.js treats route params as a Promise).
- **CI:** unchanged — daily Action commits `content/` and run.py self-triggers Sundays.
- **No backdating / no Claude trailer** on commits.
```
