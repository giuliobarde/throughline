# Phase 7 — Claude Summaries + Topic Labels — Design Spec

**Date:** 2026-06-06
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

Adds Claude-generated, practitioner-voice summaries to the top items in each daily digest,
replaces the heuristic TF-IDF topic labels with Claude-named ones, and surfaces a structured
`repro_difficulty` signal per summarized item.

## Decisions locked (2026-06-06)

| Decision | Choice |
|----------|--------|
| Summary cap | ~20 items/run; the rest keep their raw abstract |
| Selection | top-N **per topic**, round-robin by recency |
| Repro signal | structured `repro_difficulty` ("low"/"med"/"high") field + card tag |
| Model | `claude-haiku-4-5` (env `ANTHROPIC_MODEL`); plain `messages.create` (Haiku takes no `effort`/`thinking`) |
| Structured output | `output_config.format` json_schema (supported on Haiku 4.5) |
| SDK | official `anthropic` Python SDK (project is Python) |
| API isolation | behind an injectable `llm` callable so unit tests run offline with no key |

## New dependency

`pipeline/requirements.txt` adds `anthropic==0.69.0`.

## Component: `pipeline/summarize.py`

### Constants
```
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
SUMMARY_CAP = 20
SUMMARIES_CACHE = data/summaries/cache.json   # repo-relative, like embeddings cache
SYSTEM_PROMPT = (grounded practitioner voice — what it is, why a shipping-ML
  practitioner should care; concrete, no hype)
LABEL_SYSTEM = (name each cluster with a short, specific topic label — 2-4 words,
  title case; based on the member titles)
SUMMARY_SCHEMA = {
  "type": "object",
  "properties": {
    "summary": {"type": "string"},
    "repro_difficulty": {"type": "string", "enum": ["low", "med", "high"]}
  },
  "required": ["summary", "repro_difficulty"],
  "additionalProperties": False
}
LABELS_SCHEMA = {
  "type": "object",
  "properties": {
    "labels": {"type": "array", "items": {
      "type": "object",
      "properties": {"tag": {"type": "string"}, "label": {"type": "string"}},
      "required": ["tag", "label"], "additionalProperties": False}}
  },
  "required": ["labels"], "additionalProperties": False
}
```

### Injectable LLM

`LLMJson = Callable[[str, str, dict], dict]` — `(system, user, schema) -> parsed_dict`.

`_default_llm() -> LLMJson | None`:
- If `ANTHROPIC_API_KEY` not set → return `None` (callers no-op gracefully).
- Else lazy-import `anthropic`, build a client, return a closure that calls
  `client.messages.create(model=MODEL, max_tokens=600, system=system,
  messages=[{"role":"user","content":user}], output_config={"format":{"type":"json_schema","schema":schema}})`,
  extracts the first text block, and returns `json.loads(text)`.

### `select_for_summary(items, topic_by_key, cap=SUMMARY_CAP) -> list[Item]` (pure)

- Group items by their topic tag (`topic_by_key[f"{source}:{id}"]`, default `"all"`).
- Sort each group by `published_at` descending (ISO strings sort lexically; empty last).
- Round-robin across topic groups, taking one item at a time, until `cap` reached or all
  groups exhausted. Returns the selected `Item`s (≤ cap). Deterministic.

### `summarize_items(selected, llm=None, cache_path=SUMMARIES_CACHE) -> dict[str, dict]`

- Key = `f"{source}:{id}"`. Load cache; for keys already cached, reuse.
- For uncached items: resolve `llm` (default `_default_llm()`); if `None`, skip (return
  whatever is cached, possibly empty).
- Per item, build a user prompt from title + abstract + `has_code`, call
  `llm(SYSTEM_PROMPT, prompt, SUMMARY_SCHEMA)` → `{"summary","repro_difficulty"}`; on a
  per-item exception, log and skip that item (others still succeed).
- Write the cache back. Return `{key: {"summary","repro_difficulty"}}` for all resolved items.

### `label_topics(topics, items, llm=None) -> list[dict]`

- If `llm` (default `_default_llm()`) is `None` → return `topics` unchanged (keep heuristic).
- Build one user prompt listing each topic `tag` + up to 5 member titles.
- Call `llm(LABEL_SYSTEM, prompt, LABELS_SCHEMA)` → `{"labels":[{"tag","label"}]}`.
- Return a new topics list with each `label` replaced by the matching returned label (tags
  unchanged; unmatched tags keep their existing label). On exception, return `topics` unchanged.

## Integration: `pipeline/run.py`

After `cluster_items`, on the write path (not dry-run), wrapped so failure can't lose the digest:

```
summaries: dict[str, dict] = {}
if items:
    try:
        embeddings = embed_items(items)
        topics, topic_by_key = cluster_items(items, embeddings)
        selected = select_for_summary(items, topic_by_key)
        summaries = summarize_items(selected)
        topics = label_topics(topics, items)
    except Exception:
        log.exception("ml/summarize step failed; writing with what we have")
write_digest(args.date, items, topics=topics, topic_by_key=topic_by_key, summaries=summaries)
```

(Embedding/clustering already wrapped in Phase 6; this extends the same block.)

## Integration: `pipeline/digest.py`

`build_digest(date, items, topics=None, topic_by_key=None, summaries=None)`:
- For each item dict: if `summaries` and key present, set `d["summary"]` and
  `d["repro_difficulty"]` from the entry.
- `write_digest` passes `summaries` through. Existing defaults keep current behavior.

## Frontend

Types already include `summary?` and `repro_difficulty?` — **no type change**.

- `src/components/ItemCard.tsx`: when `item.repro_difficulty` is set, render a small tag
  `repro: <level>` in the metadata row (next to the code badge). `summary ?? abstract` is
  already the body text.

## Configuration

- `ANTHROPIC_API_KEY` already in `.env`; add it to the workflow "Run pipeline" `env`
  as `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` (currently only Tavily + GitHub
  tokens are passed). The user must add `ANTHROPIC_API_KEY` as a GitHub Actions secret.
- Add `ANTHROPIC_MODEL: claude-haiku-4-5` to the same `env` block (the code already defaults
  to this; the env line just makes the model explicit/overridable in CI).
- New `data/summaries/.gitkeep`; CI already commits `data/`.

## Testing (TDD, all offline — no API calls)

`tests/test_summarize.py`:
1. `select_for_summary` round-robins across topics and respects the cap; every topic gets at
   least one slot before any topic gets a second (given enough cap).
2. `select_for_summary` sorts within a topic by recency (newest first).
3. `summarize_items` with a stub `llm` computes + caches; a second call with a counting stub
   does not re-invoke `llm` for cached keys.
4. `summarize_items` with `llm=None` (and empty cache) returns `{}` (graceful no-key path).
5. `label_topics` with a stub `llm` replaces labels by tag; unmatched tags keep old labels.
6. `label_topics` with `llm=None` returns topics unchanged.

`tests/test_digest.py` (extend):
7. `build_digest` with `summaries` attaches `summary` + `repro_difficulty` to the right items.

## Error handling

- No `ANTHROPIC_API_KEY` → `_default_llm()` returns `None` → summaries `{}`, labels unchanged.
- Per-item summary exception → logged, item skipped (keeps its abstract).
- Label call exception → heuristic labels retained.
- Whole step wrapped in `run.py` try/except → digest always writes.

## Out of scope (YAGNI)

- Streaming (summaries are short).
- Prompt caching (system prompt is small).
- Per-source prompt variants.
- Weekly synthesis (Phase 9).
- Personalization ranking of which items lead (Phase 8) — selection here is recency+topic only.
