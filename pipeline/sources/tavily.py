from __future__ import annotations

import hashlib

from pipeline.models import Item


def _news_id(url: str) -> str:
    return "news:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def parse_tavily_results(payload: dict) -> list[Item]:
    results = payload.get("results") or []
    items: list[Item] = []
    for r in results:
        url = r.get("url", "")
        items.append(
            Item(
                id=_news_id(url),
                source="news",
                title=r.get("title", ""),
                url=url,
                abstract=r.get("content", ""),
                authors=[],
                published_at=r.get("published_date", ""),
                has_code=False,
                code_url=None,
            )
        )
    return items
