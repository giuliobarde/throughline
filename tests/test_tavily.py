from pipeline.sources.tavily import parse_tavily_results

SAMPLE = {
    "results": [
        {
            "title": "Claude gets a new feature",
            "url": "https://www.anthropic.com/news/claude-new-feature",
            "content": "Anthropic announced a new capability for Claude today.",
            "score": 0.9,
            "published_date": "2026-06-04T10:00:00Z",
        },
        {
            "title": "OpenAI ships something",
            "url": "https://openai.com/blog/something",
            "content": "Details about the release.",
            "score": 0.8,
            "published_date": "2026-06-05T08:00:00Z",
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
    assert it.published_at == "2026-06-04T10:00:00Z"
    assert it.has_code is False
    assert it.code_url is None


def test_parse_id_is_stable_and_prefixed():
    items = parse_tavily_results(SAMPLE)
    first = items[0].id
    again = parse_tavily_results(SAMPLE)[0].id
    assert first == again  # deterministic
    assert first.startswith("news:")
    assert len(first) == len("news:") + 12  # 12 hex chars


def test_parse_missing_results_key_returns_empty():
    assert parse_tavily_results({}) == []
