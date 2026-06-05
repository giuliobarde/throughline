import json
from pathlib import Path

from pipeline.digest import build_digest, write_digest
from pipeline.models import Item


def _item(i: str) -> Item:
    return Item(
        id=i, source="arxiv", title=f"T{i}", url=f"http://x/{i}",
        abstract="a", authors=["Z"], published_at="2026-06-05T00:00:00Z",
        has_code=False, code_url=None,
    )


def test_build_digest_shape():
    d = build_digest("2026-06-05", [_item("1"), _item("2")])
    assert d["date"] == "2026-06-05"
    assert "generated_at" in d
    assert len(d["items"]) == 2
    assert d["topics"] == []


def test_write_digest_is_idempotent_and_updates_index(tmp_path: Path):
    content = tmp_path / "content"
    write_digest("2026-06-05", [_item("1")], content_dir=content)
    write_digest("2026-06-05", [_item("1"), _item("2")], content_dir=content)  # rerun

    digest = json.loads((content / "digests" / "2026-06-05.json").read_text())
    assert len(digest["items"]) == 2  # overwritten cleanly

    index = json.loads((content / "index.json").read_text())
    assert len(index) == 1  # not duplicated
    assert index[0] == {"date": "2026-06-05", "item_count": 2, "has_synthesis": False}
