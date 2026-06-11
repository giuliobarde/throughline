from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Callable, Optional

log = logging.getLogger("throughline")

LLMText = Callable[[str, str], str]
FetchDigest = Callable[[str], Optional[dict]]

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

SYNTH_SYSTEM = (
    "You write a weekly synthesis for engineers who ship ML systems. Given short "
    "summaries of the week's notable items, write a single ~400-600 word essay that "
    "finds the connective theme across them - the throughline. Grounded and concrete, "
    "no hype, no bullet lists; flowing prose with a clear argument."
)


def recent_summaries(
    date_str: str, days: int = 7, fetch_digest: Optional[FetchDigest] = None
) -> list[dict]:
    if fetch_digest is None:
        from pipeline import store

        fetch_digest = store.fetch_digest
    end = date.fromisoformat(date_str)
    out: list[dict] = []
    for i in range(days):
        d = (end - timedelta(days=i)).isoformat()
        digest = fetch_digest(d)
        if not digest:
            continue
        for item in digest.get("items", []):
            if item.get("summary"):
                out.append(
                    {
                        "title": item.get("title", ""),
                        "summary": item["summary"],
                        "topic": item.get("topic"),
                    }
                )
    return out


def iso_week(date_str: str) -> str:
    y, w, _ = date.fromisoformat(date_str).isocalendar()
    return f"{y}-{w:02d}"


def _default_text_llm() -> Optional[LLMText]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set; skipping synthesis")
        return None
    import anthropic

    client = anthropic.Anthropic()

    def call(system: str, user: str) -> str:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(b.text for b in resp.content if getattr(b, "type", None) == "text")

    return call


def _synth_prompt(summaries: list[dict]) -> str:
    lines = ["This week's items:", ""]
    for s in summaries:
        topic = s.get("topic") or "general"
        lines.append(f"- [{topic}] {s['title']} - {s['summary']}")
    return "\n".join(lines)


def synthesize_week(summaries: list[dict], llm: Optional[LLMText] = None) -> str:
    if not summaries:
        return ""
    call = llm if llm is not None else _default_text_llm()
    if call is None:
        return ""
    try:
        return call(SYNTH_SYSTEM, _synth_prompt(summaries))
    except Exception:
        log.exception("synthesis failed")
        return ""


def synthesis_record(date_str: str, essay: str) -> dict:
    week = iso_week(date_str)
    return {
        "week": week,
        "title": f"The Throughline - Week {week}",
        "date": date_str,
        "body": essay,
    }
