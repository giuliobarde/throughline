from __future__ import annotations

from datetime import date

from pipeline.models import Item
from pipeline.backfill import (
    apply_summaries_to_digest,
    bucket_by_date,
    merge_digest_dict,
    week_chunks,
)


def _item(id: str, published_at: str, source: str = "arxiv") -> Item:
    return Item(
        id=id,
        source=source,
        title=f"title {id}",
        url=f"https://example.com/{id}",
        abstract="",
        authors=[],
        published_at=published_at,
        has_code=False,
        code_url=None,
    )


def test_week_chunks_align_to_weeks_inclusive():
    # Thu Jan 1 2026 .. Mon Jan 12 2026
    chunks = week_chunks(date(2026, 1, 1), date(2026, 1, 12))
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 4)),    # partial week (Sun end)
        (date(2026, 1, 5), date(2026, 1, 11)),   # full Mon-Sun
        (date(2026, 1, 12), date(2026, 1, 12)),  # partial tail
    ]


def test_bucket_by_date_bounds_and_dedupe():
    items = [
        _item("a", "2026-01-03T10:00:00+00:00"),
        _item("a", "2026-01-03T10:00:00+00:00"),  # dup key dropped
        _item("b", "2026-01-04T00:00:00+00:00"),
        _item("early", "2025-12-31T23:59:00+00:00"),  # before range
        _item("late", "2026-02-01T00:00:00+00:00"),   # after range
        _item("undated", ""),                          # dropped
    ]
    buckets = bucket_by_date(items, date(2026, 1, 1), date(2026, 1, 31))
    assert sorted(buckets.keys()) == ["2026-01-03", "2026-01-04"]
    assert [i.id for i in buckets["2026-01-03"]] == ["a"]


def test_merge_digest_dict_never_clobbers_existing():
    existing = {
        "date": "2026-01-03",
        "generated_at": "old",
        "items": [
            {"id": "a", "source": "arxiv", "summary": "keep me", "title": "old a"},
        ],
        "topics": [{"tag": "t", "label": "T", "item_ids": []}],
    }
    merged = merge_digest_dict(existing, "2026-01-03", [_item("a", "x"), _item("b", "2026-01-03T00:00:00+00:00")])
    ids = [d["id"] for d in merged["items"]]
    assert ids == ["a", "b"]  # existing first, new appended, dup skipped
    assert merged["items"][0]["summary"] == "keep me"  # untouched
    assert merged["topics"] == existing["topics"]


def test_merge_digest_dict_from_scratch():
    merged = merge_digest_dict(None, "2026-01-05", [_item("c", "2026-01-05T00:00:00+00:00")])
    assert merged["date"] == "2026-01-05"
    assert merged["topics"] == []
    assert [d["id"] for d in merged["items"]] == ["c"]


def test_apply_summaries_to_digest_patches_matching_items():
    digest = {
        "date": "2026-01-03",
        "items": [
            {"id": "a", "source": "arxiv", "title": "t"},
            {"id": "b", "source": "github", "title": "t"},
        ],
        "topics": [],
    }
    out = apply_summaries_to_digest(
        digest, {"arxiv:a": {"summary": "s!", "repro_difficulty": "low"}}
    )
    assert out["items"][0]["summary"] == "s!"
    assert out["items"][0]["repro_difficulty"] == "low"
    assert "summary" not in out["items"][1]


def test_arxiv_range_params_window():
    from pipeline.sources.arxiv import arxiv_range_params

    p = arxiv_range_params(date(2026, 1, 5), date(2026, 1, 11))
    assert "submittedDate:[202601050000 TO 202601112359]" in p["search_query"]
    assert p["search_query"].startswith("(cat:")
    assert p["max_results"] == "100"


def test_hn_range_params_filters():
    from pipeline.sources.hackernews import hn_range_params

    p = hn_range_params(1000, 2000)
    assert p["numericFilters"] == "points>=100,created_at_i>=1000,created_at_i<2000"
    assert p["hitsPerPage"] == "1000"


def test_github_range_params_query():
    from pipeline.sources.github import github_range_params

    p = github_range_params(date(2026, 1, 5), date(2026, 1, 11))
    assert p["q"] == "machine learning created:2026-01-05..2026-01-11"
    assert p["sort"] == "stars"


def test_select_milestones_with_injectable_llm_filters_bad_ids():
    from pipeline.backfill import select_milestones

    items = [_item("a", "2026-01-03T00:00:00+00:00"), _item("b", "2026-01-04T00:00:00+00:00")]

    def llm(system, user, schema):
        assert "arxiv:a" in user and "arxiv:b" in user
        return {"item_ids": ["arxiv:a", "bogus:zzz", "arxiv:a"]}

    picked = select_milestones(items, llm)
    assert [i.id for i in picked] == ["a"]  # bad id dropped, dup collapses


def test_select_milestones_no_llm_or_empty():
    from pipeline.backfill import select_milestones

    assert select_milestones([_item("a", "2026-01-03T00:00:00+00:00")], None) == []
    assert select_milestones([], lambda s, u, j: {"item_ids": []}) == []


def test_select_milestones_llm_error_returns_empty():
    from pipeline.backfill import select_milestones

    def boom(system, user, schema):
        raise RuntimeError("api down")

    assert select_milestones([_item("a", "2026-01-03T00:00:00+00:00")], boom) == []


def test_apply_summaries_never_overwrites_existing_summary():
    digest = {
        "date": "2026-01-03",
        "items": [{"id": "a", "source": "arxiv", "title": "t", "summary": "original"}],
        "topics": [],
    }
    out = apply_summaries_to_digest(
        digest, {"arxiv:a": {"summary": "new", "repro_difficulty": "low"}}
    )
    assert out["items"][0]["summary"] == "original"
    assert "repro_difficulty" not in out["items"][0]
