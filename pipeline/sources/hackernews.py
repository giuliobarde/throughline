from __future__ import annotations

import time

import httpx

from pipeline.models import Item

ALGOLIA_API = "https://hn.algolia.com/api/v1/search_by_date"
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
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


class HackerNewsSource:
    name = "hackernews"

    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        since = int(time.time()) - WINDOW_HOURS * 3600
        params = {
            "tags": "story",
            "numericFilters": f"points>={MIN_POINTS},created_at_i>={since}",
            "hitsPerPage": "50",
        }
        headers = {"User-Agent": USER_AGENT}
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    ALGOLIA_API, params=params, timeout=self.timeout, headers=headers
                )
                resp.raise_for_status()
                return filter_ai_ml(parse_hn_results(resp.json()))
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                transient = exc.response.status_code in (429, 500, 503)
                if transient and attempt < self.retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
