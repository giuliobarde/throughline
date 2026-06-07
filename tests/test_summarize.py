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


from pathlib import Path

from pipeline.summarize import summarize_items


class CountingLLM:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        return {"summary": "A grounded summary.", "repro_difficulty": "med"}


def test_summarize_computes_and_caches(tmp_path: Path):
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z")]
    llm = CountingLLM()
    out = summarize_items(items, llm=llm, cache_path=cache)
    assert out["arxiv:1"]["summary"] == "A grounded summary."
    assert out["arxiv:1"]["repro_difficulty"] == "med"
    assert llm.calls == 1
    assert cache.exists()

    llm2 = CountingLLM()
    out2 = summarize_items(items, llm=llm2, cache_path=cache)
    assert llm2.calls == 0  # cached
    assert out2["arxiv:1"]["summary"] == "A grounded summary."


def test_summarize_no_llm_returns_cached_only(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z")]
    out = summarize_items(items, llm=None, cache_path=cache)  # no key path
    assert out == {}


def test_summarize_skips_item_on_llm_error(tmp_path: Path):
    cache = tmp_path / "sum.json"
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z"),
             _item("arxiv", "2", "2026-06-06T00:00:00Z")]

    def flaky(system, user, schema):
        if "T1" in user:
            raise RuntimeError("boom")
        return {"summary": "ok", "repro_difficulty": "low"}

    out = summarize_items(items, llm=flaky, cache_path=cache)
    assert "arxiv:1" not in out  # errored item skipped
    assert out["arxiv:2"]["summary"] == "ok"


from pipeline.summarize import label_topics


def test_label_topics_replaces_by_tag():
    topics = [
        {"tag": "t1", "label": "Old One", "item_ids": ["arxiv:1"]},
        {"tag": "t2", "label": "Old Two", "item_ids": ["arxiv:2"]},
    ]
    items = [_item("arxiv", "1", "2026-06-06T00:00:00Z"),
             _item("arxiv", "2", "2026-06-06T00:00:00Z")]

    def llm(system, user, schema):
        return {"labels": [{"tag": "t1", "label": "Diffusion Models"}]}

    out = label_topics(topics, items, llm=llm)
    by_tag = {t["tag"]: t["label"] for t in out}
    assert by_tag["t1"] == "Diffusion Models"
    assert by_tag["t2"] == "Old Two"


def test_label_topics_no_llm_unchanged(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    topics = [{"tag": "t1", "label": "Old", "item_ids": ["arxiv:1"]}]
    out = label_topics(topics, [_item("arxiv", "1", "2026-06-06T00:00:00Z")], llm=None)
    assert out == topics


def test_label_topics_llm_error_unchanged():
    topics = [{"tag": "t1", "label": "Old", "item_ids": ["arxiv:1"]}]

    def boom(system, user, schema):
        raise RuntimeError("x")

    out = label_topics(topics, [_item("arxiv", "1", "2026-06-06T00:00:00Z")], llm=boom)
    assert out == topics
