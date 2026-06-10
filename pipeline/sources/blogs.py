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


def fetch_tavily_blogs(
    days: int = WINDOW_DAYS, max_results: int = 10, timeout: float = 30.0
) -> list[Item]:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        log.warning("TAVILY_API_KEY not set; skipping no-RSS blog vendors")
        return []
    body = {
        "query": TAVILY_QUERY,
        "topic": "news",
        "days": days,
        "max_results": max_results,
        "include_domains": NO_RSS_DOMAINS,
    }
    headers = {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}
    try:
        resp = httpx.post(TAVILY_API, json=body, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:  # fallback is best-effort; RSS feeds already fetched
        log.exception("tavily blog fallback failed; skipping")
        return []
    items: list[Item] = []
    for r in resp.json().get("results") or []:
        url = r.get("url", "")
        if not url:
            continue
        domain = url.split("/")[2].removeprefix("www.") if "://" in url else ""
        items.append(
            Item(
                id=_blog_id(url),
                source="blog",
                title=r.get("title", ""),
                url=url,
                abstract=_strip_html(r.get("content", "")),
                authors=[domain],
                published_at=_iso_date(r.get("published_date", "")),
                has_code=False,
                code_url=None,
            )
        )
    return items


class BlogSource:
    name = "blog"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for publisher, url in FEEDS:
            try:
                resp = httpx.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                items.extend(parse_feed(publisher, resp.text))
            except Exception:  # one dead feed must not kill the source
                log.exception("blog feed %s failed; skipping", publisher)
        items.extend(fetch_tavily_blogs())
        seen: set[str] = set()
        deduped: list[Item] = []
        for it in items:
            if it.id in seen:
                continue
            seen.add(it.id)
            deduped.append(it)
        return filter_window(deduped)
