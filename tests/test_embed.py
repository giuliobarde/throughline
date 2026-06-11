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


def _mem_cache():
    store: dict = {}

    def get(keys):
        return {k: store[k] for k in keys if k in store}

    def put(entries):
        store.update(entries)

    return store, get, put


def test_embed_computes_and_caches():
    backing, get, put = _mem_cache()
    items = [_item("arxiv", "1", "Alpha"), _item("hn", "2", "Beta")]
    enc = CountingEncoder()

    vecs = embed_items(items, encoder=enc, cache_get=get, cache_put=put)

    assert set(vecs.keys()) == {"arxiv:1", "hn:2"}
    assert len(vecs["arxiv:1"]) == 3
    assert enc.calls == 1  # one batch call for the two new items
    assert "arxiv:1" in backing and "hn:2" in backing


def test_embed_uses_cache_on_second_call():
    backing, get, put = _mem_cache()
    items = [_item("arxiv", "1", "Alpha")]
    embed_items(items, encoder=CountingEncoder(), cache_get=get, cache_put=put)

    enc2 = CountingEncoder()
    vecs = embed_items(items, encoder=enc2, cache_get=get, cache_put=put)
    assert enc2.calls == 0  # fully cached -> encoder not called
    assert vecs["arxiv:1"][1] == 1.0
