from pipeline.cluster import cluster_items, _slug
from pipeline.models import Item


def _item(source: str, id_: str, title: str) -> Item:
    return Item(
        id=id_, source=source, title=title, url="http://x",
        abstract="", authors=[], published_at="2026-06-06T00:00:00Z",
        has_code=False, code_url=None,
    )


def test_two_clear_groups_make_two_topics():
    items = [
        _item("arxiv", "1", "diffusion image generation models"),
        _item("arxiv", "2", "diffusion sampling for images"),
        _item("hn", "3", "rust systems programming language"),
        _item("hn", "4", "rust memory safety in systems"),
    ]
    embeddings = {
        "arxiv:1": [0.0, 0.0, 0.1],
        "arxiv:2": [0.0, 0.1, 0.0],
        "hn:3": [9.0, 9.0, 9.1],
        "hn:4": [9.1, 9.0, 9.0],
    }
    topics, topic_by_key = cluster_items(items, embeddings)
    assert len(topics) == 2
    assert topic_by_key["arxiv:1"] == topic_by_key["arxiv:2"]
    assert topic_by_key["hn:3"] == topic_by_key["hn:4"]
    assert topic_by_key["arxiv:1"] != topic_by_key["hn:3"]
    tags = {t["tag"] for t in topics}
    assert len(tags) == 2  # unique tags
    for t in topics:
        assert t["label"]  # non-empty label


def test_few_items_single_all_topic():
    items = [_item("arxiv", "1", "alpha"), _item("arxiv", "2", "beta")]
    embeddings = {"arxiv:1": [0.0, 1.0], "arxiv:2": [1.0, 0.0]}
    topics, topic_by_key = cluster_items(items, embeddings)
    assert len(topics) == 1
    assert topics[0]["tag"] == "all"
    assert set(topic_by_key.values()) == {"all"}


def test_slug():
    assert _slug("Diffusion Models") == "diffusion-models"
    assert _slug("C++ & Rust!") == "c-rust"
