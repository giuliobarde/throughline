# Phase 8b — Personalization Ranker — Design Spec

**Date:** 2026-06-08
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)
**Sibling:** Phase 8a — Feedback capture (done; provides the data)

## What it is

A pipeline ranker that reads the 👍/👎 feedback captured in 8a, trains a LogisticRegression
on the embeddings of fed-back items, scores each item in today's digest with a
`for_you_score`, and lets the frontend surface a "For You" strip + reorder topics by score.
Falls back to a recency/source heuristic until enough feedback exists.

## Decisions locked (2026-06-08)

| Decision | Choice |
|----------|--------|
| Surfacing | "For You" strip (top 5 by score) at top of home + topic sections reordered by score |
| Cold-start | until ≥3 👍 and ≥3 👎: `recency_norm + source_weight + 0.1·has_code` |
| Feedback read in CI | httpx → Supabase PostgREST with the service_role key (no new dep) |
| Model | `LogisticRegression(random_state=42)` on cached embeddings (sklearn already present) |
| Embedding source | `data/embeddings/cache.json` (keyed `source:id`); no embeddings stored in Supabase |

## Component: `pipeline/rank.py`

### `fetch_feedback(fetcher=None) -> list[tuple[str, int]]`

- `fetcher` is an injectable callable `() -> list[dict]` (each `{"item_id","signal"}`); default
  does the network call. Tests pass a stub → fully offline.
- Default fetcher: requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`; if either missing,
  return `[]`. GET `${SUPABASE_URL}/rest/v1/feedback?select=item_id,signal` with headers
  `apikey: <key>` and `Authorization: Bearer <key>`; on any HTTP/parse error, return `[]`.
- Returns `[(item_id, signal), ...]`.

### `compute_scores(items, embeddings, feedback_rows) -> dict[str, float]` (pure, tested)

- `keys = [f"{it.source}:{it.id}" for it in items]`.
- Build training data from feedback rows whose `item_id` is in `embeddings`:
  `X = [embeddings[item_id]]`, `y = [1 if signal > 0 else 0]`.
- `pos = sum(y)`, `neg = len(y) - pos`.
- **Trained path** (`pos >= 3 and neg >= 3`): fit `LogisticRegression(random_state=42,
  max_iter=1000)` on `(X, y)`. For each item: if its key is in `embeddings`,
  `score = clf.predict_proba([emb])[0][idx_of_class_1]`; else `score = _cold_start_score(item, items)`.
- **Cold-start path** (otherwise): every item gets `_cold_start_score(item, items)`.
- Returns `{key: float}` for all items.

### `_cold_start_score(item, items) -> float` (pure)

- `recency_norm`: rank items by `published_at` descending; newest → `1.0`, oldest → ~`0.0`
  (`1 - rank/len`). Empty/equal dates: stable order, still in `[0,1]`.
- `SOURCE_WEIGHT = {"github": 0.15, "hackernews": 0.10, "news": 0.10, "arxiv": 0.05}`
  (default `0.0`).
- `score = recency_norm + SOURCE_WEIGHT.get(item.source, 0.0) + (0.1 if item.has_code else 0.0)`.

(Implementation note: recency ranking over the whole `items` list is computed once and passed
into per-item scoring, or `_cold_start_score` is written to take a precomputed
`recency_by_key` map — either is fine as long as it stays pure and deterministic.)

## Integration: `pipeline/run.py`

On the write path, after summaries/labels and before `write_digest`:

```
scores: dict[str, float] = {}
if items:
    try:
        feedback_rows = fetch_feedback()
        scores = compute_scores(items, embeddings, feedback_rows)
    except Exception:
        log.exception("ranking failed; writing without scores")
write_digest(..., scores=scores)
```

`embeddings` is already computed earlier in the same block. Ranking failure must not lose the
digest (same fault-tolerance pattern as embed/cluster/summarize).

## Integration: `pipeline/digest.py`

`build_digest(date, items, topics=None, topic_by_key=None, summaries=None, scores=None)`:
- For each item dict, if `scores` and key present: `d["for_you_score"] = scores[key]`.
- `write_digest` threads `scores` through. Existing defaults unchanged.

## Frontend: `src/app/page.tsx`

`Item.for_you_score?` is already in the TS type — no type change.

- Compute `scored = [...digest.items].sort((a,b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0))`.
- **"For You" strip:** if any item has a `for_you_score`, render a section at the top titled
  `FOR YOU` (mono accent heading) with the top 5 of `scored` as `ItemCard`s.
- **Topic sections:** unchanged grouping, but each topic's items sorted by
  `(b.for_you_score ?? 0) - (a.for_you_score ?? 0)` before rendering.
- If no scores present, omit the strip and keep current behavior (topic order unchanged).
- `initialRead` hydration (8a) stays.

## Configuration / CI

- `.github/workflows/daily-digest.yml` "Run pipeline" `env`: add
  `SUPABASE_URL: ${{ secrets.SUPABASE_URL }}` and
  `SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}`.
- User adds those two as GitHub Actions secrets (service_role already needed for 8a deploy).
- Local: both already in `.env`.

## Testing (pytest, offline)

`tests/test_rank.py`:
1. `_cold_start_score` / `compute_scores` cold-start: with `feedback_rows=[]`, a newer
   `has_code` github item scores higher than an older no-code arxiv item.
2. `compute_scores` trained path: two synthetic embedding clusters; feedback gives ≥3 👍 to the
   "A" cluster and ≥3 👎 to the "B" cluster; an unseen item with an A-like embedding scores
   higher than one with a B-like embedding.
3. `compute_scores` with 2 👍 / 2 👎 (below threshold) → cold-start path (assert ordering
   matches the recency/source heuristic, not the model).
4. `fetch_feedback(fetcher=stub)` parses rows to `(item_id, signal)` tuples; default with no
   env → `[]` (monkeypatch delenv).

`tests/test_digest.py` (extend): `build_digest` with `scores` attaches `for_you_score`.

## Error handling

- Missing Supabase env / network error → `fetch_feedback` returns `[]` → cold-start scoring.
- Ranking exception in `run.py` → caught, digest written without scores (frontend omits strip).
- Item without a cached embedding on the trained path → cold-start score (never crashes).

## Out of scope (YAGNI)

- Storing embeddings in Supabase (recompute from the cache).
- Per-user models / auth (single-user).
- Online/incremental learning (retrain from scratch each run — cheap).
- Using `read_state` as a ranking signal (interest only).
- A JS test harness (Phase 10).
