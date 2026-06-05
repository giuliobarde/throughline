from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class Item:
    id: str
    source: str
    title: str
    url: str
    abstract: str
    authors: list[str]
    published_at: str  # ISO 8601
    has_code: bool
    code_url: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            id=d["id"],
            source=d["source"],
            title=d["title"],
            url=d["url"],
            abstract=d["abstract"],
            authors=list(d["authors"]),
            published_at=d["published_at"],
            has_code=bool(d["has_code"]),
            code_url=d.get("code_url"),
        )
