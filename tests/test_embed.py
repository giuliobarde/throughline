import json
from pathlib import Path

from pipeline.embed import embed_items
from pipeline.models import Item


def _item(source: str, id_: str, title: str) -> Item:
    return Item(
        id=id_, source=source, title=title, url="http://x",
        abstract="abstract text", authors=[], published_at="2026-06-06T00:00:00Z",
        has_code=False, code_url=None,
    )


class CountingEncoder:
    def __init__(self) -> None:
        self.calls = 0
        self.texts: list[str] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts = list(texts)
        return [[float(len(t)), 1.0, 2.0] for t in texts]


def test_embed_computes_and_caches(tmp_path: Path):
    cache = tmp_path / "cache.json"
    items = [_item("arxiv", "1", "Alpha"), _item("hn", "2", "Beta")]
    enc = CountingEncoder()

    vecs = embed_items(items, encoder=enc, cache_path=cache)

    assert set(vecs.keys()) == {"arxiv:1", "hn:2"}
    assert len(vecs["arxiv:1"]) == 3
    assert enc.calls == 1  # one batch call for the two new items
    assert cache.exists()
    on_disk = json.loads(cache.read_text())
    assert "arxiv:1" in on_disk and "hn:2" in on_disk


def test_embed_uses_cache_on_second_call(tmp_path: Path):
    cache = tmp_path / "cache.json"
    items = [_item("arxiv", "1", "Alpha")]
    embed_items(items, encoder=CountingEncoder(), cache_path=cache)

    enc2 = CountingEncoder()
    vecs = embed_items(items, encoder=enc2, cache_path=cache)
    assert enc2.calls == 0  # fully cached -> encoder not called
    assert vecs["arxiv:1"][1] == 1.0
