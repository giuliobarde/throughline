from pipeline.synthesize import recent_summaries, iso_week


def test_recent_summaries_collects_only_summarized():
    digests = {
        "2026-06-07": {"date": "2026-06-07", "items": [
            {"title": "A", "summary": "sumA", "topic": "t1"},
            {"title": "B"},  # no summary -> skipped
        ], "topics": []},
        "2026-06-06": {"date": "2026-06-06", "items": [
            {"title": "C", "summary": "sumC", "topic": "t2"},
        ], "topics": []},
    }
    out = recent_summaries("2026-06-07", days=3, fetch_digest=digests.get)
    titles = {s["title"] for s in out}
    assert titles == {"A", "C"}
    assert all("summary" in s for s in out)


def test_iso_week_format():
    assert iso_week("2026-06-07") == "2026-23"


from pipeline.synthesize import synthesize_week, synthesis_record


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


def test_synthesis_record_shape():
    rec = synthesis_record("2026-06-14", "essay body")
    assert rec == {
        "week": "2026-24",
        "title": "The Throughline - Week 2026-24",
        "date": "2026-06-14",
        "body": "essay body",
    }
