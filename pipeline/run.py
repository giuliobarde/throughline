from __future__ import annotations

import argparse
import json
import logging
from datetime import date as date_cls

from pipeline.cluster import cluster_items
from pipeline.digest import write_digest
from pipeline.embed import embed_items
from pipeline.rank import compute_scores, fetch_feedback
from pipeline.summarize import label_topics, select_for_summary, summarize_items
from pipeline.models import Item
from pipeline.sources.arxiv import ArxivSource
from pipeline.sources.github import GitHubSource
from pipeline.sources.hackernews import HackerNewsSource
from pipeline.sources.tavily import TavilySource

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("throughline")

SOURCES = [ArxivSource(), TavilySource(), HackerNewsSource(), GitHubSource()]


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Throughline daily pipeline")
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = parser.parse_args()

    items = collect()
    log.info("collected %d items for %s", len(items), args.date)

    if args.dry_run:
        print(json.dumps([it.to_dict() for it in items], indent=2))
        return

    topics: list[dict] = []
    topic_by_key: dict[str, str] = {}
    summaries: dict[str, dict] = {}
    scores: dict[str, float] = {}
    if items:
        try:
            embeddings = embed_items(items)
            topics, topic_by_key = cluster_items(items, embeddings)
            log.info("clustered into %d topics", len(topics))
            selected = select_for_summary(items, topic_by_key)
            summaries = summarize_items(selected)
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


if __name__ == "__main__":
    main()
