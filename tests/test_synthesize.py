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


from pipeline.synthesize import synthesize_week, write_synthesis


def test_synthesize_week_with_stub():
    captured = {}

    def stub(system, user):
        captured["user"] = user
        return "The week's throughline essay."

    summaries = [{"title": "A", "summary": "sumA", "topic": "t1"}]
    essay = synthesize_week(summaries, llm=stub)
    assert essay == "The week's throughline essay."
    assert "sumA" in captured["user"]


def test_synthesize_week_empty_or_no_llm():
    assert synthesize_week([], llm=lambda s, u: "x") == ""


def test_synthesize_week_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert synthesize_week([{"title": "A", "summary": "s", "topic": None}], llm=None) == ""


def test_write_synthesis_creates_mdx(tmp_path: Path):
    content = tmp_path / "content"
    path = write_synthesis("2026-06-07", "Body text here.", content)
    assert path.name == "2026-23.mdx"
    text = path.read_text()
    assert 'week: "2026-23"' in text
    assert 'date: "2026-06-07"' in text
    assert "Body text here." in text
    assert text.startswith("---")
