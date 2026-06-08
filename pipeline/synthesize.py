from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from pipeline.digest import DEFAULT_CONTENT_DIR

log = logging.getLogger("throughline")

LLMText = Callable[[str, str], str]

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

SYNTH_SYSTEM = (
    "You write a weekly synthesis for engineers who ship ML systems. Given short "
    "summaries of the week's notable items, write a single ~400-600 word essay that "
    "finds the connective theme across them - the throughline. Grounded and concrete, "
    "no hype, no bullet lists; flowing prose with a clear argument."
)


def recent_summaries(content_dir: Path, date_str: str, days: int = 7) -> list[dict]:
    end = date.fromisoformat(date_str)
    out: list[dict] = []
    for i in range(days):
        d = (end - timedelta(days=i)).isoformat()
        path = content_dir / "digests" / f"{d}.json"
        if not path.exists():
            continue
        digest = json.loads(path.read_text())
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
