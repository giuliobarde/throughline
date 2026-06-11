from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from pipeline import store
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
        if key in summaries and not d.get("summary"):
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


def fetch_blog_history(since: date, timeout: float = 30.0) -> list[Item]:
    from pipeline.sources.blogs import FEEDS, USER_AGENT, parse_feed

    items: list[Item] = []
    for publisher, url in FEEDS:
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                follow_redirects=True,
            )
            resp.raise_for_status()
            items.extend(parse_feed(publisher, resp.text))
        except Exception:
            log.exception("blog feed %s failed; skipping", publisher)
    lo = since.isoformat()
    return [it for it in items if it.published_at and it.published_at[:10] >= lo]


def collect_week(ws: date, we: date) -> list[Item]:
    from pipeline.sources.arxiv import fetch_arxiv_range
    from pipeline.sources.github import fetch_github_range
    from pipeline.sources.hackernews import fetch_hn_range

    items: list[Item] = []
    for name, fn in (
        ("arxiv", fetch_arxiv_range),
        ("hackernews", fetch_hn_range),
        ("github", fetch_github_range),
    ):
        try:
            fetched = fn(ws, we)
            log.info("backfill %s %s..%s: %d items", name, ws, we, len(fetched))
            items.extend(fetched)
        except Exception:  # one source must not kill the week
            log.exception("backfill %s failed for %s..%s; skipping", name, ws, we)
        time.sleep(3)  # API politeness (arXiv especially)
    return items


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Throughline historical backfill")
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    parser.add_argument("--no-summaries", action="store_true", help="skip milestone summaries")
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    all_items: list[Item] = []
    milestones: list[Item] = []
    llm = None if (args.no_summaries or args.dry_run) else _default_llm()

    for ws, we in week_chunks(start, end):
        week_items = collect_week(ws, we)
        all_items.extend(week_items)
        if llm is not None and week_items:
            milestones.extend(select_milestones(week_items, llm))

    all_items.extend(fetch_blog_history(start))
    buckets = bucket_by_date(all_items, start, end)

    if args.dry_run:
        for day in sorted(buckets):
            print(f"{day}: {len(buckets[day])} items")
        print(f"total: {sum(len(v) for v in buckets.values())} items, {len(milestones)} milestones")
        return

    summaries = summarize_items(milestones, llm=llm) if milestones else {}

    for day in sorted(buckets):
        existing = store.fetch_digest(day)
        merged = merge_digest_dict(existing, day, buckets[day])
        merged = apply_summaries_to_digest(merged, summaries)
        store.upsert_digest(day, merged)
        log.info("upserted %s (%d items)", day, len(merged["items"]))


if __name__ == "__main__":
    main()
