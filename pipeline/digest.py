from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.models import Item

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def build_digest(
    date: str,
    items: list[Item],
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
) -> dict:
    item_dicts = []
    for it in items:
        d = it.to_dict()
        if topic_by_key is not None:
            d["topic"] = topic_by_key.get(f"{it.source}:{it.id}")
        item_dicts.append(d)
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_dicts,
        "topics": topics or [],
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
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
) -> Path:
    digests_dir = content_dir / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    digest = build_digest(date, items, topics=topics, topic_by_key=topic_by_key)
    out = digests_dir / f"{date}.json"
    out.write_text(json.dumps(digest, indent=2) + "\n")
    _update_index(content_dir, date, len(items), has_synthesis)
    return out
