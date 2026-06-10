from __future__ import annotations

import re
import time

import feedparser
import httpx

from pipeline.models import Item

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
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

    def __init__(
        self, max_results: int = 50, timeout: float = 30.0, retries: int = 3
    ) -> None:
        self.max_results = max_results
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(self.max_results),
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    ARXIV_API,
                    params=params,
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                return parse_arxiv_feed(resp.text)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                transient = exc.response.status_code in (429, 500, 503)
                if transient and attempt < self.retries - 1:
                    time.sleep(3 * (attempt + 1))  # polite backoff
                    continue
                raise
        assert last_exc is not None
        raise last_exc


def arxiv_range_params(
    start, end, start_index: int = 0, max_results: int = 100
) -> dict:
    query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    window = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    return {
        "search_query": f"({query}) AND {window}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": str(start_index),
        "max_results": str(max_results),
    }


def fetch_arxiv_range(start, end, timeout: float = 30.0) -> list[Item]:
    resp = httpx.get(
        ARXIV_API,
        params=arxiv_range_params(start, end),
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return parse_arxiv_feed(resp.text)
