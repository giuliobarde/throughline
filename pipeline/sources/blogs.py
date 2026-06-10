from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

from pipeline.models import Item
from pipeline.sources.tavily import _iso_date

log = logging.getLogger("throughline")

USER_AGENT = "throughline/0.1 (https://github.com/giuliobarde/throughline)"
TAVILY_API = "https://api.tavily.com/search"

# Live RSS feeds (probed 2026-06-10).
FEEDS: list[tuple[str, str]] = [
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
]

# Vendors with no RSS feed (all known candidates 404/403): reach them via Tavily.
NO_RSS_DOMAINS = ["anthropic.com", "claude.com", "ai.meta.com", "mistral.ai"]
TAVILY_QUERY = "announcement OR release OR research update"

WINDOW_DAYS = 7
PER_PUBLISHER_CAP = 5

_TAG_RE = re.compile(r"<[^>]+>")


def _blog_id(url: str) -> str:
    return "blog:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw or "")
    return re.sub(r"\s+", " ", text).strip()[:500]


def _entry_date(entry: dict) -> str:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return ""


def parse_feed(publisher: str, raw: str) -> list[Item]:
    parsed = feedparser.parse(raw)
    items: list[Item] = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        items.append(
            Item(
                id=_blog_id(link),
                source="blog",
                title=entry.get("title", ""),
                url=link,
                abstract=_strip_html(entry.get("summary", "") or entry.get("description", "")),
                authors=[publisher],
                published_at=_entry_date(entry),
                has_code=False,
                code_url=None,
            )
        )
    return items


def filter_window(
    items: list[Item], days: int = WINDOW_DAYS, cap: int = PER_PUBLISHER_CAP
) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[Item] = []
    counts: dict[str, int] = {}
    for it in items:
        if not it.published_at:
            continue
        try:
            when = datetime.fromisoformat(it.published_at)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < cutoff:
            continue
        publisher = it.authors[0] if it.authors else ""
        if counts.get(publisher, 0) >= cap:
            continue
        counts[publisher] = counts.get(publisher, 0) + 1
        out.append(it)
    return out
