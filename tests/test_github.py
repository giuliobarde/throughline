from pipeline.sources.github import parse_github_results

SAMPLE = {
    "items": [
        {
            "full_name": "acme/awesome-llm",
            "html_url": "https://github.com/acme/awesome-llm",
            "description": "A fast LLM training framework.",
            "owner": {"login": "acme"},
            "stargazers_count": 1200,
            "created_at": "2026-06-01T00:00:00Z",
        },
        {
            "full_name": "beta/no-desc",
            "html_url": "https://github.com/beta/no-desc",
            "description": None,
            "owner": {"login": "beta"},
            "stargazers_count": 800,
            "created_at": "2026-06-02T00:00:00Z",
        },
    ]
}


def test_parse_maps_repo_fields():
    items = parse_github_results(SAMPLE)
    assert len(items) == 2
    it = items[0]
    assert it.id == "gh:acme/awesome-llm"
    assert it.source == "github"
    assert it.title == "acme/awesome-llm"
    assert it.url == "https://github.com/acme/awesome-llm"
    assert it.abstract == "A fast LLM training framework."
    assert it.authors == ["acme"]
    assert it.published_at == "2026-06-01T00:00:00Z"
    assert it.has_code is True
    assert it.code_url == "https://github.com/acme/awesome-llm"


def test_parse_handles_null_description():
    items = parse_github_results(SAMPLE)
    assert items[1].abstract == ""


def test_parse_missing_items_returns_empty():
    assert parse_github_results({}) == []
