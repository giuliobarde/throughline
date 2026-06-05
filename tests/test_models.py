from pipeline.models import Item


def test_item_roundtrips_to_dict_and_back():
    item = Item(
        id="2401.00001",
        source="arxiv",
        title="A Title",
        url="http://arxiv.org/abs/2401.00001",
        abstract="An abstract.",
        authors=["Ada Lovelace"],
        published_at="2026-06-05T00:00:00Z",
        has_code=False,
        code_url=None,
    )
    d = item.to_dict()
    assert d["id"] == "2401.00001"
    assert d["authors"] == ["Ada Lovelace"]
    assert Item.from_dict(d) == item
