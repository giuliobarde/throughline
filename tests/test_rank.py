from pipeline.rank import compute_scores
from pipeline.models import Item


def _item(source: str, id_: str, published: str, has_code: bool = False) -> Item:
    return Item(
        id=id_, source=source, title=f"T{id_}", url="http://x",
        abstract="a", authors=[], published_at=published,
        has_code=has_code, code_url=None,
    )


def test_cold_start_ranks_newer_code_github_higher():
    items = [
        _item("github", "g", "2026-06-08T00:00:00Z", has_code=True),
        _item("arxiv", "a", "2026-06-01T00:00:00Z", has_code=False),
    ]
    scores = compute_scores(items, embeddings={}, feedback_rows=[])
    assert scores["github:g"] > scores["arxiv:a"]


def test_below_threshold_uses_cold_start():
    items = [
        _item("github", "g", "2026-06-08T00:00:00Z", has_code=True),
        _item("arxiv", "a", "2026-06-01T00:00:00Z"),
    ]
    embeddings = {"github:g": [0.0, 0.0], "arxiv:a": [1.0, 1.0]}
    feedback = [("x1", 1), ("x2", 1), ("y1", -1), ("y2", -1)]
    scores = compute_scores(items, embeddings, feedback)
    assert scores["github:g"] > scores["arxiv:a"]


def test_trained_path_scores_near_positive_higher():
    items = [
        _item("arxiv", "newA", "2026-06-08T00:00:00Z"),
        _item("arxiv", "newB", "2026-06-08T00:00:00Z"),
    ]
    embeddings = {
        "arxiv:a1": [0.0, 0.0, 0.1], "arxiv:a2": [0.1, 0.0, 0.0], "arxiv:a3": [0.0, 0.1, 0.0],
        "arxiv:b1": [9.0, 9.0, 9.1], "arxiv:b2": [9.1, 9.0, 9.0], "arxiv:b3": [9.0, 9.1, 9.0],
        "arxiv:newA": [0.05, 0.05, 0.0], "arxiv:newB": [9.0, 9.0, 9.0],
    }
    feedback = [
        ("arxiv:a1", 1), ("arxiv:a2", 1), ("arxiv:a3", 1),
        ("arxiv:b1", -1), ("arxiv:b2", -1), ("arxiv:b3", -1),
    ]
    scores = compute_scores(items, embeddings, feedback)
    assert scores["arxiv:newA"] > scores["arxiv:newB"]
    assert 0.0 <= scores["arxiv:newA"] <= 1.0
