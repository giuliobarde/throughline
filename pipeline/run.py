from __future__ import annotations

import argparse
import json
import logging
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

from pipeline.cluster import cluster_items
from pipeline.digest import DEFAULT_CONTENT_DIR, write_digest
from pipeline.embed import embed_items
from pipeline.rank import compute_scores, fetch_feedback
from pipeline.summarize import label_topics, select_for_summary, summarize_items
from pipeline.synthesize import iso_week, recent_summaries, synthesize_week, write_synthesis
from pipeline.models import Item
from pipeline.sources.arxiv import ArxivSource
from pipeline.sources.blogs import BlogSource
from pipeline.sources.github import GitHubSource
from pipeline.sources.hackernews import HackerNewsSource
from pipeline.sources.tavily import TavilySource

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("throughline")

SOURCES = [ArxivSource(), TavilySource(), HackerNewsSource(), GitHubSource(), BlogSource()]


def collect() -> list[Item]:
    items: list[Item] = []
    for source in SOURCES:
        try:
            fetched = source.fetch()
            log.info("source %s: %d items", source.name, len(fetched))
            items.extend(fetched)
        except Exception:  # fault-tolerant: one source must not kill the run
            log.exception("source %s failed; skipping", source.name)
    return dedupe(items)


def dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def load_existing_digest(date: str, content_dir: Path) -> Optional[dict]:
    """Today's digest from an earlier run, or None (absent/corrupt → fresh build)."""
    path = content_dir / "digests" / f"{date}.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def merge_run_items(
    existing: Optional[dict], fetched: list[Item]
) -> tuple[list[Item], dict[str, dict], dict[str, str]]:
    """Union of an earlier same-day run and this fetch.

    Existing items win on duplicate keys (their metadata is already enriched);
    new keys append. Carried summaries and carried topics survive even if the
    ML/cluster step fails this run.

    Returns:
        pool: merged item list
        carried_summaries: {source:id -> {"summary": ..., "repro_difficulty": ...}}
            for items that already have a non-empty summary.
        carried_topics: {source:id -> topic_label}
            for items that already have a non-empty topic assignment.
    """
    if not existing:
        return fetched, {}, {}
    pool: list[Item] = []
    carried_summaries: dict[str, dict] = {}
    carried_topics: dict[str, str] = {}
    seen: set[str] = set()
    for d in existing.get("items", []):
        key = f"{d['source']}:{d['id']}"
        seen.add(key)
        pool.append(Item.from_dict(d))
        if d.get("summary"):
            carried_summaries[key] = {
                "summary": d["summary"],
                "repro_difficulty": d.get("repro_difficulty"),
            }
        if d.get("topic"):
            carried_topics[key] = d["topic"]
    for it in fetched:
        key = f"{it.source}:{it.id}"
        if key in seen:
            continue
        seen.add(key)
        pool.append(it)
    return pool, carried_summaries, carried_topics


def main() -> None:
    parser = argparse.ArgumentParser(description="Throughline daily pipeline")
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    parser.add_argument(
        "--synthesize", action="store_true", help="force weekly synthesis"
    )
    args = parser.parse_args()

    items = collect()
    log.info("collected %d items for %s", len(items), args.date)

    if args.dry_run:
        print(json.dumps([it.to_dict() for it in items], indent=2))
        return

    existing = load_existing_digest(args.date, DEFAULT_CONTENT_DIR)
    items, carried_summaries, carried_topics = merge_run_items(existing, items)
    if existing:
        log.info("merged with earlier run: %d items in pool", len(items))

    topics: list[dict] = (existing or {}).get("topics") or []
    topic_by_key: dict[str, str] = dict(carried_topics)
    summaries: dict[str, dict] = dict(carried_summaries)
    scores: dict[str, float] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
            selected = select_for_summary(items, topic_by_key)
            summaries = {**carried_summaries, **summarize_items(selected)}
            log.info("summarized %d items", len(summaries))
            topics = label_topics(topics, items)
            scores = compute_scores(items, embeddings, fetch_feedback())
            log.info("scored %d items", len(scores))
        except Exception:  # ML/LLM/ranking failure must not lose the digest
            log.exception("ml/summarize/rank step failed; writing with what we have")

    out = write_digest(
        args.date,
        items,
        topics=topics,
        topic_by_key=topic_by_key,
        summaries=summaries,
        scores=scores,
    )
    log.info("wrote %s", out)

    is_sunday = date_cls.fromisoformat(args.date).weekday() == 6
    week_file = DEFAULT_CONTENT_DIR / "synthesis" / f"{iso_week(args.date)}.mdx"
    if (is_sunday and not week_file.exists()) or args.synthesize:
        try:
            week_summaries = recent_summaries(DEFAULT_CONTENT_DIR, args.date)
            essay = synthesize_week(week_summaries)
            if essay:
                log.info("wrote synthesis %s", write_synthesis(args.date, essay))
            else:
                log.info("no synthesis written (empty essay)")
        except Exception:
            log.exception("synthesis step failed; digest already written")
    elif is_sunday:
        log.info("synthesis for %s already exists; skipping", iso_week(args.date))


if __name__ == "__main__":
    main()
