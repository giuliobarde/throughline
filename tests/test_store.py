from __future__ import annotations

import pytest

from pipeline.store import StoreError, _chunks, _env, _in_param, derive_index


def test_in_param_quotes_keys():
    assert _in_param(["arxiv:1", "github:gh:o/r"]) == 'in.("arxiv:1","github:gh:o/r")'


def test_chunks_splits_evenly():
    assert list(_chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_derive_index_marks_synthesis_weeks():
    rows = [
        {"date": "2026-06-07", "item_count": 77},
        {"date": "2026-06-14", "item_count": 5},
    ]
    # 2026-06-14 is Sunday of ISO week 2026-24; 2026-06-07 is Sunday of week 2026-23
    out = derive_index(rows, {"2026-24"})
    assert out == [
        {"date": "2026-06-14", "item_count": 5, "has_synthesis": True},
        {"date": "2026-06-07", "item_count": 77, "has_synthesis": False},
    ]


def test_env_raises_without_creds(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(StoreError):
        _env()
