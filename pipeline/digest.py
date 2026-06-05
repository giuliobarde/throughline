from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.models import Item

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def build_digest(date: str, items: list[Item]) -> dict:
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [it.to_dict() for it in items],
        "topics": [],
    }


def _update_index(content_dir: Path, date: str, item_count: int, has_synthesis: bool) -> None:
    index_path = content_dir / "index.json"
    index: list[dict] = []
    if index_path.exists():
        index = json.loads(index_path.read_text())
    index = [e for e in index if e["date"] != date]  # idempotent: drop existing
    index.append({"date": date, "item_count": item_count, "has_synthesis": has_synthesis})
    index.sort(key=lambda e: e["date"], reverse=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n")


def write_digest(
    date: str,
    items: list[Item],
    content_dir: Path = DEFAULT_CONTENT_DIR,
    has_synthesis: bool = False,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(date, items)
    out = digests_dir / f"{date}.json"
    out.write_text(json.dumps(digest, indent=2) + "\n")
    _update_index(content_dir, date, len(items), has_synthesis)
    return out
