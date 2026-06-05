from __future__ import annotations

import hashlib
import logging
import os
import time

import httpx

from pipeline.models import Item

log = logging.getLogger("throughline")

TAVILY_API = "https://api.tavily.com/search"
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
QUERY = "latest artificial intelligence and machine learning developments"
ALLOWED_DOMAINS = [
    "anthropic.com",
    "openai.com",
    "deepmind.google",
    "ai.meta.com",
    "huggingface.co",
    "mistral.ai",
    "ai.googleblog.com",
    "blog.google",
]


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


class TavilySource:
    name = "news"

    def __init__(
        self, max_results: int = 10, days: int = 2, timeout: float = 30.0, retries: int = 3
    ) -> None:
        self.max_results = max_results
        self.days = days
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            log.warning("TAVILY_API_KEY not set; skipping news source")
            return []
        body = {
            "query": QUERY,
            "topic": "news",
            "days": self.days,
            "max_results": self.max_results,
            "include_domains": ALLOWED_DOMAINS,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "User-Agent": USER_AGENT,
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.post(
                    TAVILY_API, json=body, headers=headers, timeout=self.timeout
                )
                resp.raise_for_status()
                return parse_tavily_results(resp.json())
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                transient = exc.response.status_code in (429, 500, 503)
                if transient and attempt < self.retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
