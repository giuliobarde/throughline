import json
from pathlib import Path

from pipeline.synthesize import recent_summaries, iso_week


def _write_digest(content: Path, date: str, items: list[dict]) -> None:
    d = content / "digests"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}.json").write_text(json.dumps({"date": date, "items": items, "topics": []}))


def test_recent_summaries_collects_only_summarized(tmp_path: Path):
    content = tmp_path / "content"
    _write_digest(content, "2026-06-07", [
        {"title": "A", "summary": "sumA", "topic": "t1"},
        {"title": "B"},  # no summary -> skipped
    ])
    _write_digest(content, "2026-06-06", [
        {"title": "C", "summary": "sumC", "topic": "t2"},
    ])
    out = recent_summaries(content, "2026-06-07", days=3)
    titles = {s["title"] for s in out}
    assert titles == {"A", "C"}
    assert all("summary" in s for s in out)


def test_iso_week_format():
    assert iso_week("2026-06-07") == "2026-23"
