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
