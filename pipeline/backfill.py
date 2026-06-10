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


def week_listing(items: list[Item]) -> str:
    lines: list[str] = []
    for it in items:
        who = it.authors[0] if it.authors else ""
        lines.append(f"{it.source}:{it.id} | {it.source} | {who} | {it.title}")
    return "\n".join(lines)


def select_milestones(items: list[Item], llm: Optional[LLMJson]) -> list[Item]:
    if llm is None or not items:
        return []
    by_key = {f"{it.source}:{it.id}": it for it in items}
    try:
        result = llm(SELECT_SYSTEM, week_listing(items), SELECT_SCHEMA)
    except Exception:  # selection is optional polish; never block the backfill
        log.exception("milestone selection failed for week; skipping")
        return []
    picked: list[Item] = []
    seen: set[str] = set()
    for key in result.get("item_ids", [])[:5]:
        if key in by_key and key not in seen:
            seen.add(key)
            picked.append(by_key[key])
    return picked
