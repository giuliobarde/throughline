from __future__ import annotations

from pipeline.models import Item

SOURCE_WEIGHT = {"github": 0.15, "hackernews": 0.10, "news": 0.10, "arxiv": 0.05}
MIN_PER_CLASS = 3


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
