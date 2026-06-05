from __future__ import annotations

import re

import feedparser
import httpx

from pipeline.models import Item

ARXIV_API = "http://export.arxiv.org/api/query"
CATEGORIES = ["cs.LG", "cs.CL", "cs.AI", "cs.MA"]
_ABS_ID = re.compile(r"abs/([^v]+)")
_CODE_HINT = re.compile(r"\b(code|github|implementation)\b", re.IGNORECASE)


def _arxiv_id(raw_id: str) -> str:
    m = _ABS_ID.search(raw_id)
    return m.group(1) if m else raw_id


def parse_arxiv_feed(xml: str) -> list[Item]:
    feed = feedparser.parse(xml)
    items: list[Item] = []
    for e in feed.entries:
        summary = getattr(e, "summary", "") or ""
        authors = [a.get("name", "") for a in getattr(e, "authors", []) if a.get("name")]
        items.append(
            Item(
                id=_arxiv_id(getattr(e, "id", "")),
                source="arxiv",
                title=" ".join(getattr(e, "title", "").split()),
                url=getattr(e, "link", ""),
                abstract=" ".join(summary.split()),
                authors=authors,
                published_at=getattr(e, "published", ""),
                has_code=bool(_CODE_HINT.search(summary)),
                code_url=None,
            )
        )
    return items


class ArxivSource:
    name = "arxiv"

    def __init__(self, max_results: int = 50, timeout: float = 30.0) -> None:
        self.max_results = max_results
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        query = "+OR+".join(f"cat:{c}" for c in CATEGORIES)
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(self.max_results),
        }
        resp = httpx.get(ARXIV_API, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return parse_arxiv_feed(resp.text)
