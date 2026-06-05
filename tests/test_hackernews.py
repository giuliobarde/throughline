from pipeline.sources.hackernews import parse_hn_results, filter_ai_ml

SAMPLE = {
    "hits": [
        {
            "objectID": "111",
            "title": "Show HN: A new LLM inference engine",
            "url": "https://github.com/acme/fast-llm",
            "author": "alice",
            "points": 250,
            "created_at": "2026-06-05T09:00:00.000Z",
        },
        {
            "objectID": "222",
            "title": "My thoughts on remote work",
            "url": "https://example.com/remote",
            "author": "bob",
            "points": 300,
            "created_at": "2026-06-05T08:00:00.000Z",
        },
        {
            "objectID": "333",
            "title": "Ask HN: best transformer tutorials?",
            "url": None,
            "author": "carol",
            "points": 120,
            "created_at": "2026-06-05T07:00:00.000Z",
        },
    ]
}


def test_parse_maps_fields_and_code_detection():
    items = parse_hn_results(SAMPLE)
    assert len(items) == 3
    it = items[0]
    assert it.id == "hn:111"
    assert it.source == "hackernews"
    assert it.title == "Show HN: A new LLM inference engine"
    assert it.url == "https://github.com/acme/fast-llm"
    assert it.authors == ["alice"]
    assert it.published_at == "2026-06-05T09:00:00.000Z"
    assert it.has_code is True  # github.com url
    assert it.code_url == "https://github.com/acme/fast-llm"


def test_parse_uses_hn_permalink_when_url_missing():
    items = parse_hn_results(SAMPLE)
    carol = [i for i in items if i.id == "hn:333"][0]
    assert carol.url == "https://news.ycombinator.com/item?id=333"
    assert carol.has_code is False
    assert carol.code_url is None


def test_filter_keeps_only_ai_ml_titles():
    items = filter_ai_ml(parse_hn_results(SAMPLE))
    ids = {i.id for i in items}
    assert "hn:111" in ids  # "LLM"
    assert "hn:333" in ids  # "transformer"
    assert "hn:222" not in ids  # remote work -> dropped


def test_parse_missing_hits_returns_empty():
    assert parse_hn_results({}) == []
