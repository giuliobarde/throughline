from __future__ import annotations

from typing import Protocol

from pipeline.models import Item


class Source(Protocol):
    name: str

    def fetch(self) -> list[Item]:
        ...
