from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from pipeline.digest import DEFAULT_CONTENT_DIR, _update_index
from pipeline.models import Item
from pipeline.summarize import LLMJson, _default_llm, summarize_items

log = logging.getLogger("throughline")

SELECT_SYSTEM = (
    "You curate a tech-history archive. From this week's item listing, select ONLY "
    "landmark events: major model announcements, breakout open-source repos, or "
    "landmark research papers. Fewer is better; zero is acceptable. Never more than 5. "
    "Return the item ids exactly as given."
)

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 5}
    },
    "required": ["item_ids"],
    "additionalProperties": False,
}


def week_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Inclusive [start, end] split at Sunday boundaries (first/last may be partial)."""
    chunks: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        week_end = min(cur + timedelta(days=6 - cur.weekday()), end)
        chunks.append((cur, week_end))
        cur = week_end + timedelta(days=1)
    return chunks


def bucket_by_date(items: list[Item], start: date, end: date) -> dict[str, list[Item]]:
    """Group by published date; drop undated, out-of-range, and duplicate keys."""
    buckets: dict[str, list[Item]] = {}
    seen: set[str] = set()
    lo, hi = start.isoformat(), end.isoformat()
    for it in items:
        day = (it.published_at or "")[:10]
        if not day or day < lo or day > hi:
            continue
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        buckets.setdefault(day, []).append(it)
    return buckets


def merge_digest_dict(
    existing: Optional[dict], date_str: str, new_items: list[Item]
) -> dict:
    """Append new items to an existing digest dict; never touch existing entries."""
    items: list[dict] = list(existing.get("items", [])) if existing else []
    seen = {f"{d['source']}:{d['id']}" for d in items}
    for it in new_items:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        items.append(it.to_dict())
    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "topics": (existing or {}).get("topics", []),
    }


def apply_summaries_to_digest(digest: dict, summaries: dict[str, dict]) -> dict:
    for d in digest.get("items", []):
        key = f"{d['source']}:{d['id']}"
        if key in summaries:
            d["summary"] = summaries[key].get("summary")
            d["repro_difficulty"] = summaries[key].get("repro_difficulty")
    return digest
