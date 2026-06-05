from pipeline.sources.tavily import parse_tavily_results

SAMPLE = {
    "results": [
        {
            "title": "Claude gets a new feature",
            "url": "https://www.anthropic.com/news/claude-new-feature",
            "content": "Anthropic announced a new capability for Claude today.",
            "score": 0.9,
            "published_date": "Thu, 04 Jun 2026 10:00:00 GMT",  # Tavily uses RFC 2822
        },
        {
            "title": "OpenAI ships something",
            "url": "https://openai.com/blog/something",
            "content": "Details about the release.",
            "score": 0.8,
            "published_date": "Fri, 05 Jun 2026 08:00:00 GMT",
        },
    ]
}


def test_parse_maps_fields_to_items():
    items = parse_tavily_results(SAMPLE)
    assert len(items) == 2
    it = items[0]
    assert it.source == "news"
    assert it.title == "Claude gets a new feature"
    assert it.url == "https://www.anthropic.com/news/claude-new-feature"
    assert it.abstract == "Anthropic announced a new capability for Claude today."
    assert it.authors == []
    assert it.published_at.startswith("2026-06-04")  # RFC 2822 normalized to ISO
    assert it.has_code is False
    assert it.code_url is None


def test_iso_date_normalizes_rfc2822_and_passes_iso_through():
    from pipeline.sources.tavily import _iso_date

    assert _iso_date("Thu, 04 Jun 2026 16:07:30 GMT").startswith("2026-06-04T16:07:30")
    assert _iso_date("2026-06-04T10:00:00Z").startswith("2026-06-04T10:00:00")
    assert _iso_date("") == ""
    assert _iso_date("not a date") == "not a date"  # unparseable kept as-is


def test_parse_id_is_stable_and_prefixed():
    items = parse_tavily_results(SAMPLE)
    first = items[0].id
    again = parse_tavily_results(SAMPLE)[0].id
    assert first == again  # deterministic
    assert first.startswith("news:")
    assert len(first) == len("news:") + 12  # 12 hex chars


def test_parse_missing_results_key_returns_empty():
    assert parse_tavily_results({}) == []


from pipeline.sources.tavily import TavilySource


def test_fetch_returns_empty_when_key_missing(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert TavilySource().fetch() == []
