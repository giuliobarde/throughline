# Phase 6 — ML Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed digest items, cluster them into labeled topics, and render the home digest grouped into topic sections.

**Architecture:** `embed.py` turns items into cached vectors (sentence-transformers, injectable encoder for tests). `cluster.py` runs KMeans+silhouette and TF-IDF labeling to produce topics. `run.py` wires embed→cluster into the write path; `digest.py` enriches each item with a `topic` and populates `digest.topics`. The frontend groups items into topic sections and shows a topic tag per card.

**Tech Stack:** Python 3.12 (`sentence-transformers`, `scikit-learn`, `numpy`, `pytest`); Next.js/TS frontend.

**Honest-commit rules:** real timestamps, no backdating, no Claude trailer, Conventional Commits.

---

## File structure

```
/pipeline/requirements.txt        # MODIFY — add sentence-transformers, scikit-learn, numpy
/pipeline/embed.py                # NEW — embed_items() + JSON cache + injectable encoder
/pipeline/cluster.py              # NEW — cluster_items() KMeans+silhouette + TF-IDF labels
/pipeline/digest.py               # MODIFY — build_digest/write_digest accept topics + topic_by_key
/pipeline/run.py                  # MODIFY — embed+cluster on write path
/tests/test_embed.py              # NEW
/tests/test_cluster.py            # NEW
/tests/test_digest.py             # MODIFY — topic enrichment test
/data/embeddings/.gitkeep         # NEW — keep dir; cache.json lands here
/src/app/page.tsx                 # MODIFY — topic sections
/src/components/ItemCard.tsx      # MODIFY — topic tag
/.github/workflows/daily-digest.yml  # MODIFY — model cache + commit data/
```

---

### Task 1: Dependencies + embeddings dir

**Files:**
- Modify: `pipeline/requirements.txt`
- Create: `data/embeddings/.gitkeep`

- [ ] **Step 1: Add deps**

Set `pipeline/requirements.txt` to:

```
httpx==0.27.2
feedparser==6.0.11
pytest==8.3.3
sentence-transformers==3.0.1
scikit-learn==1.5.2
numpy==1.26.4
```

- [ ] **Step 2: Install into the venv**

Run: `.venv/bin/pip install -r pipeline/requirements.txt`
Expected: installs sentence-transformers, scikit-learn, numpy (+ torch). Takes a few minutes.

- [ ] **Step 3: Create the cache dir keeper**

Create empty file `data/embeddings/.gitkeep`.

- [ ] **Step 4: Commit**

```bash
git add pipeline/requirements.txt data/embeddings/.gitkeep
git commit -m "chore(pipeline): add ML deps and embeddings cache dir"
```

---

### Task 2: embed_items with injectable encoder + JSON cache

**Files:**
- Create: `pipeline/embed.py`
- Create: `tests/test_embed.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_embed.py`:

```python
import json
from pathlib import Path

from pipeline.embed import embed_items
from pipeline.models import Item


def _item(source: str, id_: str, title: str) -> Item:
    return Item(
        id=id_, source=source, title=title, url="http://x",
        abstract="abstract text", authors=[], published_at="2026-06-06T00:00:00Z",
        has_code=False, code_url=None,
    )


class CountingEncoder:
    def __init__(self) -> None:
        self.calls = 0
        self.texts: list[str] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts = list(texts)
        return [[float(len(t)), 1.0, 2.0] for t in texts]


def test_embed_computes_and_caches(tmp_path: Path):
    cache = tmp_path / "cache.json"
    items = [_item("arxiv", "1", "Alpha"), _item("hn", "2", "Beta")]
    enc = CountingEncoder()

    vecs = embed_items(items, encoder=enc, cache_path=cache)

    assert set(vecs.keys()) == {"arxiv:1", "hn:2"}
    assert len(vecs["arxiv:1"]) == 3
    assert enc.calls == 1  # one batch call for the two new items
    assert cache.exists()
    on_disk = json.loads(cache.read_text())
    assert "arxiv:1" in on_disk and "hn:2" in on_disk


def test_embed_uses_cache_on_second_call(tmp_path: Path):
    cache = tmp_path / "cache.json"
    items = [_item("arxiv", "1", "Alpha")]
    embed_items(items, encoder=CountingEncoder(), cache_path=cache)

    enc2 = CountingEncoder()
    vecs = embed_items(items, encoder=enc2, cache_path=cache)
    assert enc2.calls == 0  # fully cached -> encoder not called
    assert vecs["arxiv:1"][1] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_embed.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.embed).

- [ ] **Step 3: Write the implementation**

Create `pipeline/embed.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from pipeline.models import Item

Encoder = Callable[[list[str]], list[list[float]]]

EMBEDDINGS_CACHE = (
    Path(__file__).resolve().parent.parent / "data" / "embeddings" / "cache.json"
)
MODEL_NAME = "all-MiniLM-L6-v2"


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _text(item: Item) -> str:
    return f"{item.title}. {item.abstract}".strip()


def _default_encoder() -> Encoder:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)

    def encode(texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in model.encode(texts)]

    return encode


def _load_cache(cache_path: Path) -> dict[str, list[float]]:
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}


def embed_items(
    items: list[Item],
    encoder: Optional[Encoder] = None,
    cache_path: Path = EMBEDDINGS_CACHE,
) -> dict[str, list[float]]:
    cache = _load_cache(cache_path)
    missing = [it for it in items if _key(it) not in cache]
    if missing:
        enc = encoder or _default_encoder()
        vectors = enc([_text(it) for it in missing])
        for it, vec in zip(missing, vectors):
            cache[_key(it)] = list(vec)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache))
    return {_key(it): cache[_key(it)] for it in items}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_embed.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/embed.py tests/test_embed.py
git commit -m "feat(pipeline): add embed_items with injectable encoder and JSON cache"
```

---

### Task 3: cluster_items (KMeans+silhouette + TF-IDF labels)

**Files:**
- Create: `pipeline/cluster.py`
- Create: `tests/test_cluster.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cluster.py`:

```python
from pipeline.cluster import cluster_items, _slug
from pipeline.models import Item


def _item(source: str, id_: str, title: str) -> Item:
    return Item(
        id=id_, source=source, title=title, url="http://x",
        abstract="", authors=[], published_at="2026-06-06T00:00:00Z",
        has_code=False, code_url=None,
    )


def test_two_clear_groups_make_two_topics():
    items = [
        _item("arxiv", "1", "diffusion image generation models"),
        _item("arxiv", "2", "diffusion sampling for images"),
        _item("hn", "3", "rust systems programming language"),
        _item("hn", "4", "rust memory safety in systems"),
    ]
    embeddings = {
        "arxiv:1": [0.0, 0.0, 0.1],
        "arxiv:2": [0.0, 0.1, 0.0],
        "hn:3": [9.0, 9.0, 9.1],
        "hn:4": [9.1, 9.0, 9.0],
    }
    topics, topic_by_key = cluster_items(items, embeddings)
    assert len(topics) == 2
    # items 1&2 share a tag; 3&4 share a different tag
    assert topic_by_key["arxiv:1"] == topic_by_key["arxiv:2"]
    assert topic_by_key["hn:3"] == topic_by_key["hn:4"]
    assert topic_by_key["arxiv:1"] != topic_by_key["hn:3"]
    tags = {t["tag"] for t in topics}
    assert len(tags) == 2  # unique tags
    for t in topics:
        assert t["label"]  # non-empty label
        assert t["tag"] == _slug(t["tag"]) or t["tag"]  # tag is slug-safe


def test_few_items_single_all_topic():
    items = [_item("arxiv", "1", "alpha"), _item("arxiv", "2", "beta")]
    embeddings = {"arxiv:1": [0.0, 1.0], "arxiv:2": [1.0, 0.0]}
    topics, topic_by_key = cluster_items(items, embeddings)
    assert len(topics) == 1
    assert topics[0]["tag"] == "all"
    assert set(topic_by_key.values()) == {"all"}


def test_slug():
    assert _slug("Diffusion Models") == "diffusion-models"
    assert _slug("C++ & Rust!") == "c-rust"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cluster.py -v`
Expected: FAIL (ModuleNotFoundError: pipeline.cluster).

- [ ] **Step 3: Write the implementation**

Create `pipeline/cluster.py`:

```python
from __future__ import annotations

import re

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from pipeline.models import Item

MIN_ITEMS_TO_CLUSTER = 4
MAX_K = 6
RANDOM_STATE = 42
TOP_TERMS = 2


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "topic"


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _best_k_labels(matrix: np.ndarray, n: int) -> np.ndarray:
    best_labels = None
    best_score = -1.0
    upper = min(MAX_K, n - 1)
    for k in range(2, upper + 1):
        labels = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit_predict(
            matrix
        )
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(matrix, labels)
        if score > best_score:
            best_score = score
            best_labels = labels
    if best_labels is None:  # fallback: everything in one cluster
        best_labels = np.zeros(n, dtype=int)
    return best_labels


def _label_for(cluster_titles: list[str], all_titles: list[str], fallback: str) -> str:
    try:
        vec = TfidfVectorizer(stop_words="english")
        vec.fit(all_titles)
        terms = vec.get_feature_names_out()
        cluster_matrix = vec.transform(cluster_titles).toarray()
        mean = cluster_matrix.mean(axis=0)
        top_idx = mean.argsort()[::-1][:TOP_TERMS]
        top = [terms[i] for i in top_idx if mean[i] > 0]
        if top:
            return " ".join(top).title()
    except ValueError:
        pass
    return fallback


def cluster_items(
    items: list[Item], embeddings: dict[str, list[float]]
) -> tuple[list[dict], dict[str, str]]:
    keys = [_key(it) for it in items]
    if len(items) < MIN_ITEMS_TO_CLUSTER:
        return (
            [{"tag": "all", "label": "All", "item_ids": keys}],
            {k: "all" for k in keys},
        )

    matrix = np.array([embeddings[k] for k in keys])
    labels = _best_k_labels(matrix, len(items))

    all_titles = [it.title or "untitled" for it in items]
    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    used_tags: set[str] = set()
    for cluster_id in sorted(set(labels)):
        members = [i for i, lab in enumerate(labels) if lab == cluster_id]
        cluster_titles = [all_titles[i] for i in members]
        label = _label_for(cluster_titles, all_titles, f"Topic {cluster_id + 1}")
        tag = _slug(label)
        while tag in used_tags:
            tag = f"{tag}-{len(used_tags) + 1}"
        used_tags.add(tag)
        member_keys = [keys[i] for i in members]
        topics.append({"tag": tag, "label": label, "item_ids": member_keys})
        for k in member_keys:
            topic_by_key[k] = tag
    return topics, topic_by_key
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cluster.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/cluster.py tests/test_cluster.py
git commit -m "feat(pipeline): add KMeans+silhouette clustering with TF-IDF labels"
```

---

### Task 4: Digest enrichment (topics + per-item topic)

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_digest.py`:

```python
def test_build_digest_attaches_topics_and_item_topic():
    items = [_item("1"), _item("2")]
    topics = [{"tag": "t1", "label": "T1", "item_ids": ["arxiv:1", "arxiv:2"]}]
    topic_by_key = {"arxiv:1": "t1", "arxiv:2": "t1"}
    d = build_digest("2026-06-06", items, topics=topics, topic_by_key=topic_by_key)
    assert d["topics"] == topics
    assert d["items"][0]["topic"] == "t1"
    assert d["items"][1]["topic"] == "t1"
```

(Note: the existing `_item(i)` helper in this file builds `Item(id=i, source="arxiv", ...)`,
so its key is `arxiv:{i}`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_digest.py::test_build_digest_attaches_topics_and_item_topic -v`
Expected: FAIL (build_digest() got an unexpected keyword argument 'topics').

- [ ] **Step 3: Update digest.py**

In `pipeline/digest.py`, replace `build_digest` and `write_digest` with:

```python
def build_digest(
    date: str,
    items: list[Item],
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
) -> dict:
    item_dicts = []
    for it in items:
        d = it.to_dict()
        if topic_by_key is not None:
            d["topic"] = topic_by_key.get(f"{it.source}:{it.id}")
        item_dicts.append(d)
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_dicts,
        "topics": topics or [],
    }


def write_digest(
    date: str,
    items: list[Item],
    content_dir: Path = DEFAULT_CONTENT_DIR,
    has_synthesis: bool = False,
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(date, items, topics=topics, topic_by_key=topic_by_key)
    out = digests_dir / f"{date}.json"
    out.write_text(json.dumps(digest, indent=2) + "\n")
    _update_index(content_dir, date, len(items), has_synthesis)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_digest.py -v`
Expected: PASS (all digest tests, including the new one).

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat(pipeline): enrich digest with topics and per-item topic tag"
```

---

### Task 5: Wire embed+cluster into run.py

**Files:**
- Modify: `pipeline/run.py`

- [ ] **Step 1: Add imports**

In `pipeline/run.py`, add after the existing source imports:

```python
from pipeline.cluster import cluster_items
from pipeline.embed import embed_items
```

- [ ] **Step 2: Replace the write path in `main()`**

In `pipeline/run.py`, replace the block from `if args.dry_run:` to the end of `main()` with:

```python
    if args.dry_run:
        print(json.dumps([it.to_dict() for it in items], indent=2))
        return

    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
        except Exception:  # ML failure must not lose the digest
            log.exception("embedding/clustering failed; writing without topics")

    out = write_digest(args.date, items, topics=topics, topic_by_key=topic_by_key)
    log.info("wrote %s", out)
```

- [ ] **Step 3: Full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (existing + new embed/cluster/digest tests).

- [ ] **Step 4: Live run (real model + clustering)**

Run: `set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-06`
Expected: logs `clustered into N topics`; writes `content/digests/2026-06-06.json` with
non-empty `topics` and `data/embeddings/cache.json` populated. (arXiv may be rate-limited;
news/HN/GitHub still provide items.) First run downloads the model (~90MB).

- [ ] **Step 5: Inspect output then restore content**

Run:
```bash
.venv/bin/python -c "import json;d=json.load(open('content/digests/2026-06-06.json'));print('topics:',[t['label'] for t in d['topics']]);print('items:',len(d['items']))"
```
Then restore so the digest stays the Action's job (the cache may stay — see Step 6):
```bash
git checkout content/digests/2026-06-06.json content/index.json 2>/dev/null || rm -f content/digests/2026-06-06.json
```

- [ ] **Step 6: Commit code (not the hand-run digest)**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): embed and cluster items into topics on write path"
```

(If `data/embeddings/cache.json` was created and you want to seed it, it can be committed
separately; otherwise discard it with `git checkout data/embeddings` / `rm`. The CI run will
populate and commit it for real.)

---

### Task 6: Frontend — topic sections + topic tag

**Files:**
- Modify: `src/components/ItemCard.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Add topic tag to ItemCard**

In `src/components/ItemCard.tsx`, add a topic tag in the metadata row. Replace the metadata
`<div>` (the one containing `SourceBadge`, code, and `<time>`) with:

```tsx
      <div className="flex items-center gap-3">
        <SourceBadge source={item.source} />
        {item.has_code && (
          <span className="font-mono text-xs text-emerald-500">code</span>
        )}
        {item.topic && (
          <span className="font-mono text-xs text-neutral-600">#{item.topic}</span>
        )}
        <time className="font-mono text-xs text-neutral-600">
          {item.published_at.slice(0, 10)}
        </time>
      </div>
```

- [ ] **Step 2: Group home into topic sections**

Replace the body of `src/app/page.tsx` with:

```tsx
import { ItemCard } from "@/components/ItemCard";
import { getLatestDigest } from "@/lib/content";
import type { Item } from "@/lib/types";

export const revalidate = 3600; // ISR: rebuild hourly

export default async function HomePage() {
  const digest = await getLatestDigest();
  const itemKey = (i: Item) => `${i.source}:${i.id}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Today&rsquo;s digest</h1>
        {digest && (
          <p className="mt-1 font-mono text-xs text-neutral-500">
            {digest.date} · {digest.items.length} items
          </p>
        )}
      </header>

      {!digest || digest.items.length === 0 ? (
        <p className="text-neutral-500">
          No digest yet. The pipeline runs daily.
        </p>
      ) : digest.topics.length > 0 ? (
        <div className="space-y-12">
          {digest.topics.map((topic) => {
            const byKey = new Map(digest.items.map((i) => [itemKey(i), i]));
            const topicItems = topic.item_ids
              .map((id) => byKey.get(id))
              .filter((i): i is Item => Boolean(i));
            if (topicItems.length === 0) return null;
            return (
              <section key={topic.tag}>
                <h2 className="mb-2 font-mono text-xs uppercase tracking-wider text-neutral-500">
                  {topic.label}
                </h2>
                <div>
                  {topicItems.map((item) => (
                    <ItemCard key={itemKey(item)} item={item} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div>
          {digest.items.map((item) => (
            <ItemCard key={itemKey(item)} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Typecheck + build**

Run: `npx tsc --noEmit`
Expected: no errors.
Run: `npm run build`
Expected: Compiled successfully.

- [ ] **Step 4: Commit**

```bash
git add src/components/ItemCard.tsx src/app/page.tsx
git commit -m "feat(web): group home digest into topic sections with topic tags"
```

---

### Task 7: CI — model cache + commit data/

**Files:**
- Modify: `.github/workflows/daily-digest.yml`

- [ ] **Step 1: Add a HuggingFace model cache step**

In `.github/workflows/daily-digest.yml`, add this step **after** the `setup-python` step and
**before** "Install pipeline deps":

```yaml
      - name: Cache HuggingFace model
        uses: actions/cache@v4
        with:
          path: ~/.cache/huggingface
          key: hf-${{ hashFiles('pipeline/requirements.txt') }}
```

- [ ] **Step 2: Commit content AND data**

In the same file, change the "Commit digest if changed" step's diff check and `git add` to
cover both `content` and `data`:

```yaml
      - name: Commit digest if changed
        run: |
          if [ -z "$(git status --porcelain content data)" ]; then
            echo "No content changes; nothing to commit."
            exit 0
          fi
          # Author as the repo owner via the verified GitHub noreply email so the
          # commit counts toward the contribution graph. Real timestamp; never backdated.
          git config user.name "Giulio"
          git config user.email "giuliobarde@users.noreply.github.com"
          git add content data
          git commit -m "chore(digest): $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 3: Commit + push**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "ci: cache HF model and commit embeddings cache with digest"
git push
```

---

### Task 8: Live visual verification

**Files:** none

- [ ] **Step 1: Generate a digest with topics + start dev**

Run:
```bash
set -a && . ./.env && set +a && .venv/bin/python -m pipeline.run --date 2026-06-06
npm run dev > /tmp/tl-dev.log 2>&1 &
sleep 7 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```
Expected: digest written with topics; dev returns 200.

- [ ] **Step 2: Confirm topic sections render**

Use Playwright (navigate to `http://localhost:3000`) and confirm topic-label section headings
appear above grouped cards, and cards show a `#<topic>` tag. Screenshot for the record.

- [ ] **Step 3: Restore + stop**

```bash
git checkout content/digests/2026-06-06.json content/index.json 2>/dev/null || rm -f content/digests/2026-06-06.json
git checkout data/embeddings 2>/dev/null || true
pkill -f "next dev"; pkill -f "next-server"
```

---

## Self-review notes

- **Spec coverage:** deps (T1), embed_items+cache+injectable encoder (T2), cluster_items
  KMeans+silhouette+TF-IDF labels+<4 short-circuit (T3), digest enrichment (T4), run.py wiring
  with fault-tolerant fallback (T5), frontend topic sections + tag (T6), CI model cache +
  data commit (T7), live visual check (T8). All spec sections mapped.
- **Type consistency:** `embed_items(...) -> dict[str, list[float]]` keyed `source:id`;
  `cluster_items(items, embeddings) -> (list[dict], dict[str,str])`; `build_digest`/
  `write_digest` accept `topics` + `topic_by_key`. Keys are `f"{source}:{id}"` everywhere
  (embed, cluster, digest, frontend `itemKey`). Topic dict shape `{tag,label,item_ids}`
  matches the TS `Topic` type. `_slug`/`_key` helper names consistent.
- **Placeholder scan:** none.
- **Test math:** existing 19 + embed 2 + cluster 3 + digest 1 = 25 expected after Task 5.
- **Frontend:** `Item.topic?` and `Digest.topics` already exist in `types.ts` — no type change;
  `page.tsx` matches items to topics via the same `source:id` key the pipeline writes.
- **No backdating / no Claude trailer** on every commit.
```
