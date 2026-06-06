# Phase 6 — ML Layer (embeddings → clustering → topic sections) — Design Spec

**Date:** 2026-06-06
**Owner:** Giulio
**Status:** Approved, pre-implementation
**Parent project:** [Throughline](2026-06-05-throughline-design.md)

## What it is

Adds the machine-learning layer to the pipeline: embed each digest item, cluster items into
topics, label each topic, and render the home digest grouped into topic sections. This turns
the flat daily list into a structured, themed digest.

## Decisions locked (2026-06-06)

| Decision | Choice |
|----------|--------|
| Clustering | KMeans over k=2..min(6, n−1), best **silhouette** score; deterministic `random_state=42` |
| Topic labels | Heuristic **TF-IDF top terms** over cluster titles (Claude labels deferred to Phase 7) |
| Topic UI | Home grouped into **topic sections** + a small topic tag on each card |
| Embedding model | `all-MiniLM-L6-v2` (sentence-transformers; free in CI) |
| Embedding cache | `data/embeddings/cache.json` committed to the repo, keyed by `source:id` |

## New dependencies

`pipeline/requirements.txt` adds: `sentence-transformers`, `scikit-learn`, `numpy`.

## Component: `pipeline/embed.py`

- `embed_items(items: list[Item], encoder: Encoder | None = None) -> dict[str, list[float]]`
  - Key per item: `f"{item.source}:{item.id}"`.
  - Text embedded: `f"{title}. {abstract}".strip()`.
  - **Cache:** load `data/embeddings/cache.json` (`{key: vector}`); compute only missing
    keys; write the cache back. Returns the full `{key: vector}` map for the given items.
  - `encoder` is an injectable callable `list[str] -> list[list[float]]`. Default lazy-loads
    the sentence-transformers model (`SentenceTransformer("all-MiniLM-L6-v2").encode`). Tests
    inject a stub, so no model download happens in unit tests.
  - `EMBEDDINGS_CACHE = data/embeddings/cache.json` (path relative to repo root, like
    `digest.DEFAULT_CONTENT_DIR`). Cache dir + file created if missing.

## Component: `pipeline/cluster.py`

- `cluster_items(items, embeddings) -> tuple[list[dict], dict[str, str]]`
  - `embeddings` is the `{key: vector}` map from `embed_items`.
  - If `len(items) < 4`: return a single topic
    `[{"tag": "all", "label": "All", "item_ids": [keys...]}]` and `{key: "all"}` for each.
  - Else: build the matrix in item order, run `KMeans(n_clusters=k, random_state=42,
    n_init=10)` for `k in range(2, min(6, len(items)-1) + 1)`, choose the `k` with the highest
    `silhouette_score`. Assign each item to its cluster.
  - **Label** each cluster: `TfidfVectorizer(stop_words="english")` fit over all item titles;
    for each cluster take the mean TF-IDF vector over its members and pick the top 2 terms;
    `label = " ".join(top_terms).title()` (fallback `"Topic N"` if empty); `tag = slug(label)`
    (lowercase, non-alnum → `-`). Ensure tags are unique (suffix `-2`, `-3` on collision).
  - Returns `topics` (list of `{tag, label, item_ids}`, `item_ids` are the `source:id` keys)
    and `topic_by_key` (`{key: tag}`).

## Integration: `pipeline/run.py`

```
items = collect()
if not args.dry_run and items:
    embeddings = embed_items(items)
    topics, topic_by_key = cluster_items(items, embeddings)
else:
    topics, topic_by_key = [], {}
write_digest(args.date, items, topics=topics, topic_by_key=topic_by_key)
```

Dry-run stays lightweight (no embedding/clustering — just prints items). Embedding/clustering
wrapped so a failure logs and falls back to no-topics (digest still writes).

## Integration: `pipeline/digest.py`

- `build_digest(date, items, topics=None, topic_by_key=None) -> dict`
  - `topics` defaults to `[]` (unchanged behavior).
  - For each item: `d = it.to_dict()`; if `topic_by_key`, set
    `d["topic"] = topic_by_key.get(f"{it.source}:{it.id}")`.
  - `digest["topics"] = topics or []`.
- `write_digest(date, items, content_dir=..., has_synthesis=False, topics=None, topic_by_key=None)`
  passes the new args through. Existing call sites and tests keep working (defaults).

## Frontend

Types already support it (`Item.topic?`, `Digest.topics: Topic[]`), so **no type change**.

- `src/app/page.tsx`: if `digest.topics` non-empty, render one `<section>` per topic — a
  topic label heading (mono, uppercase accent) followed by that topic's `ItemCard`s (looked
  up from `digest.items` by the topic's `item_ids`, matched on `${source}:${id}`). If
  `topics` is empty, fall back to the current flat list.
- `src/components/ItemCard.tsx`: when `item.topic` is set, show a small topic tag in the
  metadata row (alongside source badge / code / date).

## CI: `.github/workflows/daily-digest.yml`

- Add an `actions/cache` step for the HuggingFace model dir (`~/.cache/huggingface`) keyed on
  the workflow file hash, so the model is downloaded once and reused.
- The commit step changes from `git add content` to `git add content data` (and the
  "nothing changed" check covers both) so the embeddings cache persists in the repo.

## Testing (TDD, all offline)

`tests/test_embed.py`:
1. `embed_items` with a stub encoder computes vectors for new items and writes the cache.
2. On a second call (same items), the stub encoder is **not** called again (cache hit) — use
   a counting stub; assert call count stays 0 on the second run for cached keys.
3. Cache file round-trips (written JSON re-read matches).
   (Use a `tmp_path` cache location via a parameter or monkeypatched `EMBEDDINGS_CACHE`.)

`tests/test_cluster.py`:
1. Two clearly separated synthetic embedding groups (e.g. vectors near [0,0,..] vs [9,9,..])
   → exactly 2 topics; items in the same group share a tag.
2. `< 4` items → single `"all"` topic.
3. Labels are non-empty strings; tags are unique and slugified.

`tests/test_digest.py` (extend):
4. `build_digest` with `topics` + `topic_by_key` sets each item's `topic` and populates
   `digest["topics"]`.

## Error handling

- Embedding/clustering failure in `run.py` → logged, falls back to `topics=[], topic_by_key={}`
  so the digest still writes (fault-tolerant).
- `silhouette_score` requires ≥2 clusters and < n samples — guarded by the `<4` short-circuit
  and the `k` range `2..min(6, n−1)`.
- Empty/whitespace titles in TF-IDF → fallback `"Topic N"` label.

## Out of scope (YAGNI)

- `/topics/[tag]` filtered page (Phase 10).
- Claude-generated topic labels (Phase 7).
- Personalization ranker / for-you ordering (Phase 8).
- HDBSCAN.
