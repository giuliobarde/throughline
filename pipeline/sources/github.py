from __future__ import annotations

from pipeline.models import Item

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
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
