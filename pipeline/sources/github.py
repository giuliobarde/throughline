from __future__ import annotations

import os
import time
from datetime import date, timedelta

import httpx

from pipeline.models import Item

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
WINDOW_DAYS = 7


def parse_github_results(payload: dict) -> list[Item]:
    repos = payload.get("items") or []
    items: list[Item] = []
    for r in repos:
        html_url = r.get("html_url", "")
        owner = (r.get("owner") or {}).get("login")
        items.append(
            Item(
                id=f"gh:{r.get('full_name', '')}",
                source="github",
                title=r.get("full_name", ""),
                url=html_url,
                abstract=r.get("description") or "",
                authors=[owner] if owner else [],
                published_at=r.get("created_at", ""),
                has_code=True,
                code_url=html_url,
            )
        )
    return items


class GitHubSource:
    name = "github"

    def __init__(self, per_page: int = 10, timeout: float = 30.0, retries: int = 3) -> None:
        self.per_page = per_page
        self.timeout = timeout
        self.retries = retries

    def fetch(self) -> list[Item]:
        since = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
        params = {
            "q": f"machine learning created:>={since}",
            "sort": "stars",
            "order": "desc",
            "per_page": str(self.per_page),
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    GITHUB_SEARCH_API,
                    params=params,
                    timeout=self.timeout,
                    headers=headers,
                )
                resp.raise_for_status()
                return parse_github_results(resp.json())
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                transient = exc.response.status_code in (429, 500, 503)
                if transient and attempt < self.retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
