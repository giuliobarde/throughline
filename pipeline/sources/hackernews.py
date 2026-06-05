from __future__ import annotations

from pipeline.models import Item

ALGOLIA_API = "https://hn.algolia.com/api/v1/search_by_date"
MIN_POINTS = 100
WINDOW_HOURS = 48
KEYWORDS = [
    "llm",
    "gpt",
    "transformer",
    "neural",
    "diffusion",
    "machine learning",
    "deep learning",
    "ai model",
    "open source model",
    "fine-tun",
    "rag",
    "agent",
    "inference",
    "pytorch",
    "hugging face",
    "anthropic",
    "openai",
]


def parse_hn_results(payload: dict) -> list[Item]:
    hits = payload.get("hits") or []
    items: list[Item] = []
    for h in hits:
        object_id = str(h.get("objectID", ""))
        url = h.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        has_code = "github.com" in url
        author = h.get("author")
        items.append(
            Item(
                id=f"hn:{object_id}",
                source="hackernews",
                title=h.get("title", ""),
                url=url,
                abstract="",
                authors=[author] if author else [],
                published_at=h.get("created_at", ""),
                has_code=has_code,
                code_url=url if has_code else None,
            )
        )
    return items


def filter_ai_ml(items: list[Item]) -> list[Item]:
    return [it for it in items if any(kw in it.title.lower() for kw in KEYWORDS)]
