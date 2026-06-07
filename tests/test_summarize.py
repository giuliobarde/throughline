from pipeline.summarize import select_for_summary
from pipeline.models import Item


def _item(source: str, id_: str, published: str) -> Item:
    return Item(
        id=id_, source=source, title=f"T{id_}", url="http://x",
        abstract="a", authors=[], published_at=published,
        has_code=False, code_url=None,
    )


def test_round_robin_balances_topics_and_respects_cap():
    items = [
        _item("arxiv", "a1", "2026-06-06T03:00:00Z"),
        _item("arxiv", "a2", "2026-06-06T02:00:00Z"),
        _item("arxiv", "a3", "2026-06-06T01:00:00Z"),
        _item("hn", "b1", "2026-06-06T09:00:00Z"),
    ]
    topic_by_key = {
        "arxiv:a1": "ta", "arxiv:a2": "ta", "arxiv:a3": "ta", "hn:b1": "tb",
    }
    selected = select_for_summary(items, topic_by_key, cap=3)
    ids = [f"{i.source}:{i.id}" for i in selected]
    assert len(ids) == 3
    assert "hn:b1" in ids
    assert ids.index("arxiv:a1") < ids.index("arxiv:a2")


def test_cap_zero_padding_and_missing_topic_defaults_all():
    items = [_item("arxiv", "x", "2026-06-06T00:00:00Z")]
    selected = select_for_summary(items, {}, cap=5)
    assert [f"{i.source}:{i.id}" for i in selected] == ["arxiv:x"]
