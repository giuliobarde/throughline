from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pipeline.models import Item
from pipeline.sources.blogs import filter_window, parse_feed

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Example Blog</title>
<item>
  <title>Model X released</title>
  <link>https://example.com/model-x</link>
  <description>&lt;p&gt;Big &lt;b&gt;news&lt;/b&gt;   today.&lt;/p&gt;</description>
  <pubDate>Mon, 08 Jun 2026 12:00:00 +0000</pubDate>
</item>
<item>
  <title>No link entry</title>
  <description>skipped</description>
</item>
</channel></rss>"""


def _blog_item(published_at: str, publisher: str = "OpenAI", url: str = "https://x.com/a") -> Item:
    return Item(
        id="blog:abc",
        source="blog",
        title="t",
        url=url,
        abstract="",
        authors=[publisher],
        published_at=published_at,
        has_code=False,
        code_url=None,
    )


def test_parse_feed_maps_fields_and_strips_html():
    items = parse_feed("Example", RSS_FIXTURE)
    assert len(items) == 1  # entry without link skipped
    it = items[0]
    assert it.source == "blog"
    assert it.id.startswith("blog:") and len(it.id) == len("blog:") + 12
    assert it.title == "Model X released"
    assert it.url == "https://example.com/model-x"
    assert it.abstract == "Big news today."
    assert it.authors == ["Example"]
    assert it.published_at.startswith("2026-06-08T12:00:00")
    assert it.has_code is False


def test_filter_window_drops_old_and_undated_and_caps_per_publisher():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=30)).isoformat()
    items = [
        _blog_item(fresh, url="https://x.com/1"),
        _blog_item(old, url="https://x.com/2"),
        _blog_item("", url="https://x.com/3"),
        _blog_item("not-a-date", url="https://x.com/4"),
    ]
    kept = filter_window(items)
    assert [i.url for i in kept] == ["https://x.com/1"]

    many = [_blog_item(fresh, url=f"https://x.com/{n}") for n in range(8)]
    assert len(filter_window(many, cap=5)) == 5
