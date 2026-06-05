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


import httpx

from pipeline.sources.github import GitHubSource


def test_fetch_parses_results(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["params"] = params
        captured["headers"] = headers
        return httpx.Response(200, json=SAMPLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    items = GitHubSource().fetch()
    assert {i.id for i in items} == {"gh:acme/awesome-llm", "gh:beta/no-desc"}
    assert captured["params"]["sort"] == "stars"
    assert "Authorization" not in captured["headers"]  # no token -> no auth header


def test_fetch_adds_auth_header_when_token_set(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["headers"] = headers
        return httpx.Response(200, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setenv("GITHUB_TOKEN", "ghtok123")
    GitHubSource().fetch()
    assert captured["headers"]["Authorization"] == "Bearer ghtok123"
