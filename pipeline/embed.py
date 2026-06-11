from __future__ import annotations

from typing import Callable, Optional

from pipeline.models import Item

Encoder = Callable[[list[str]], list[list[float]]]
CacheGet = Callable[[list[str]], dict[str, list[float]]]
CachePut = Callable[[dict[str, list[float]]], None]

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


def _store_get(keys: list[str]) -> dict[str, list[float]]:
    from pipeline import store

    return {k: v["v"] for k, v in store.cache_get("embeddings", keys).items()}


def _store_put(entries: dict[str, list[float]]) -> None:
    from pipeline import store

    store.cache_put("embeddings", {k: {"v": v} for k, v in entries.items()})


def embed_items(
    items: list[Item],
    encoder: Optional[Encoder] = None,
    cache_get: Optional[CacheGet] = None,
    cache_put: Optional[CachePut] = None,
) -> dict[str, list[float]]:
    get = cache_get or _store_get
    put = cache_put or _store_put
    keys = [_key(it) for it in items]
    cache = get(keys)
    missing = [it for it in items if _key(it) not in cache]
    if missing:
        enc = encoder or _default_encoder()
        vectors = enc([_text(it) for it in missing])
        fresh = {_key(it): list(vec) for it, vec in zip(missing, vectors)}
        cache.update(fresh)
        put(fresh)
    return {k: cache[k] for k in keys}
