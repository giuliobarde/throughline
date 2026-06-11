from __future__ import annotations

import json

from pipeline.models import Item
from pipeline.run import load_existing_digest, merge_run_items


def _item(id: str, source: str = "arxiv", title: str = "fresh") -> Item:
    return Item(
        id=id,
        source=source,
        title=title,
        url=f"https://example.com/{id}",
        abstract="",
        authors=[],
        published_at="2026-06-10T00:00:00+00:00",
        has_code=False,
        code_url=None,
    )


def _existing_digest() -> dict:
    return {
        "date": "2026-06-10",
        "generated_at": "earlier",
        "items": [
            {
                "id": "a",
                "source": "arxiv",
                "title": "old title wins",
                "url": "https://example.com/a",
                "abstract": "",
                "authors": [],
                "published_at": "2026-06-10T00:00:00+00:00",
                "has_code": False,
                "code_url": None,
                "summary": "carried summary",
                "repro_difficulty": "low",
                "topic": "t1",
                "for_you_score": 0.5,
            },
            {
                "id": "b",
                "source": "github",
                "title": "no summary yet",
                "url": "https://example.com/b",
                "abstract": "",
                "authors": [],
                "published_at": "2026-06-10T01:00:00+00:00",
                "has_code": True,
                "code_url": "https://example.com/b",
            },
        ],
        "topics": [],
    }


def test_merge_existing_wins_and_new_appended():
    pool, carried, _topics = merge_run_items(_existing_digest(), [_item("a"), _item("c")])
    keys = [f"{i.source}:{i.id}" for i in pool]
    assert keys == ["arxiv:a", "github:b", "arxiv:c"]
    assert pool[0].title == "old title wins"  # existing version kept


def test_merge_carries_only_nonempty_summaries():
    _, carried, carried_topics = merge_run_items(_existing_digest(), [])
    assert carried == {
        "arxiv:a": {"summary": "carried summary", "repro_difficulty": "low"}
    }
    # item a has topic "t1"; item b has no topic field — only a should be carried
    assert carried_topics == {"arxiv:a": "t1"}


def test_merge_none_existing_is_passthrough():
    fetched = [_item("x")]
    pool, carried, carried_topics = merge_run_items(None, fetched)
    assert pool == fetched
    assert carried == {}
    assert carried_topics == {}


def test_load_existing_digest_roundtrip(tmp_path):
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "2026-06-10.json").write_text(json.dumps({"date": "2026-06-10", "items": [], "topics": []}))
    assert load_existing_digest("2026-06-10", tmp_path) == {
        "date": "2026-06-10",
        "items": [],
        "topics": [],
    }
    assert load_existing_digest("2026-06-09", tmp_path) is None
    (digests / "bad.json").write_text("{not json")
    assert load_existing_digest("bad", tmp_path) is None
