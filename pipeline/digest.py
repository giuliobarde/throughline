from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline.models import Item

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def build_digest(
    date: str,
    items: list[Item],
    topics: list[dict] | None = None,
    topic_by_key: dict[str, str] | None = None,
    summaries: dict[str, dict] | None = None,
    scores: dict[str, float] | None = None,
) -> dict:
    item_dicts = []
    for it in items:
        d = it.to_dict()
        key = f"{it.source}:{it.id}"
        if topic_by_key is not None:
            d["topic"] = topic_by_key.get(key)
        if summaries is not None and key in summaries:
            d["summary"] = summaries[key].get("summary")
            d["repro_difficulty"] = summaries[key].get("repro_difficulty")
        if scores is not None and key in scores:
            d["for_you_score"] = scores[key]
        item_dicts.append(d)
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_dicts,
        "topics": topics or [],
    }


