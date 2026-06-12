from __future__ import annotations

from pipeline.models import Item
from pipeline.run import merge_run_items


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


def test_dedupe_drops_cross_source_title_duplicates():
    from pipeline.run import dedupe

    hn = _item("h", source="hackernews", title="DiffusionGemma: 4x faster")
    blog = _item("b", source="blog", title="diffusiongemma 4X FASTER")
    kept = dedupe([hn, blog])
    assert [i.source for i in kept] == ["blog"]


