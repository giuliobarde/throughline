from __future__ import annotations

import logging
import os
from typing import Callable, Optional

import httpx

from pipeline.models import Item

log = logging.getLogger("throughline")

USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
SOURCE_WEIGHT = {"github": 0.15, "hackernews": 0.10, "news": 0.10, "arxiv": 0.05}
MIN_PER_CLASS = 3

FeedbackFetcher = Callable[[], list[dict]]


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _recency_norm(items: list[Item]) -> dict[str, float]:
    order = sorted(items, key=lambda i: i.published_at or "", reverse=True)
    n = len(order)
    return {
        _key(it): (1.0 if n <= 1 else 1.0 - idx / (n - 1))
        for idx, it in enumerate(order)
    }


def _cold_start_scores(items: list[Item]) -> dict[str, float]:
    recency = _recency_norm(items)
    scores: dict[str, float] = {}
    for it in items:
        scores[_key(it)] = (
            recency[_key(it)]
            + SOURCE_WEIGHT.get(it.source, 0.0)
            + (0.1 if it.has_code else 0.0)
        )
    return scores


def compute_scores(
    items: list[Item],
    embeddings: dict[str, list[float]],
    feedback_rows: list[tuple[str, int]],
) -> dict[str, float]:
    train_x: list[list[float]] = []
    train_y: list[int] = []
    for item_id, signal in feedback_rows:
        if item_id in embeddings:
            train_x.append(embeddings[item_id])
            train_y.append(1 if signal > 0 else 0)
    pos = sum(train_y)
    neg = len(train_y) - pos
    if pos < MIN_PER_CLASS or neg < MIN_PER_CLASS:
        return _cold_start_scores(items)

    import numpy as np
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(np.array(train_x), np.array(train_y))
    pos_idx = list(clf.classes_).index(1)
    cold = _cold_start_scores(items)
    scores: dict[str, float] = {}
    for it in items:
        k = _key(it)
        if k in embeddings:
            proba = clf.predict_proba(np.array([embeddings[k]]))[0][pos_idx]
            scores[k] = float(proba)
        else:
            scores[k] = cold[k]
    return scores


def _default_fetcher() -> list[dict]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.warning("Supabase env not set; ranking without feedback")
        return []
    resp = httpx.get(
        f"{url}/rest/v1/feedback",
        params={"select": "item_id,signal"},
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "User-Agent": USER_AGENT,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_feedback(fetcher: Optional[FeedbackFetcher] = None) -> list[tuple[str, int]]:
    call = fetcher if fetcher is not None else _default_fetcher
    try:
        rows = call()
    except Exception:
        log.exception("fetch_feedback failed; returning no feedback")
        return []
    out: list[tuple[str, int]] = []
    for r in rows:
        item_id = r.get("item_id")
        signal = r.get("signal")
        if isinstance(item_id, str) and isinstance(signal, int):
            out.append((item_id, signal))
    return out
