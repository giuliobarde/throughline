from __future__ import annotations

import logging
import os
import time
from typing import Iterator, Optional

import httpx

from pipeline.synthesize import iso_week

log = logging.getLogger("throughline")

RETRIES = 3
CHUNK = 200
TIMEOUT = 30.0


class StoreError(RuntimeError):
    """The data store is the critical path: failures must be loud."""


def _env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise StoreError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return url.rstrip("/"), key


def _headers(key: str, upsert: bool = False) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates"
    return h


def _request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[object] = None,
    upsert: bool = False,
) -> httpx.Response:
    url, key = _env()
    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        try:
            resp = httpx.request(
                method,
                f"{url}/rest/v1/{path}",
                params=params,
                json=json_body,
                headers=_headers(key, upsert=upsert),
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001 — uniform retry then loud fail
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    raise StoreError(f"supabase {method} {path} failed after {RETRIES} attempts") from last


def _in_param(keys: list[str]) -> str:
    quoted = ",".join(f'"{k}"' for k in keys)
    return f"in.({quoted})"


def _chunks(seq: list, size: int = CHUNK) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def derive_index(rows: list[dict], synthesis_weeks: set[str]) -> list[dict]:
    """digest_index rows + synthesis weeks -> index entries, newest first."""
    out = [
        {
            "date": r["date"],
            "item_count": r.get("item_count") or 0,
            "has_synthesis": iso_week(r["date"]) in synthesis_weeks,
        }
        for r in rows
    ]
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def fetch_digest(date: str) -> Optional[dict]:
    resp = _request("GET", "digests", params={"date": f"eq.{date}", "select": "payload"})
    rows = resp.json()
    return rows[0]["payload"] if rows else None


def upsert_digest(date: str, payload: dict) -> None:
    _request(
        "POST",
        "digests",
        params={"on_conflict": "date"},
        json_body=[{"date": date, "generated_at": payload["generated_at"], "payload": payload}],
        upsert=True,
    )


def fetch_index() -> list[dict]:
    rows = _request("GET", "digest_index", params={"select": "date,item_count"}).json()
    weeks = {r["week"] for r in _request("GET", "syntheses", params={"select": "week"}).json()}
    return derive_index(rows, weeks)


def upsert_synthesis(week: str, title: str, date: str, body: str) -> None:
    _request(
        "POST",
        "syntheses",
        params={"on_conflict": "week"},
        json_body=[{"week": week, "title": title, "date": date, "body": body}],
        upsert=True,
    )


def synthesis_exists(week: str) -> bool:
    rows = _request("GET", "syntheses", params={"week": f"eq.{week}", "select": "week"}).json()
    return len(rows) > 0


def cache_get(scope: str, keys: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for chunk in _chunks(keys):
        rows = _request(
            "GET",
            "kv_cache",
            params={"scope": f"eq.{scope}", "key": _in_param(chunk), "select": "key,value"},
        ).json()
        for r in rows:
            out[r["key"]] = r["value"]
    return out


def cache_put(scope: str, entries: dict[str, dict]) -> None:
    rows = [{"scope": scope, "key": k, "value": v} for k, v in entries.items()]
    for chunk in _chunks(rows):
        _request(
            "POST", "kv_cache", params={"on_conflict": "scope,key"}, json_body=chunk, upsert=True
        )
