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
