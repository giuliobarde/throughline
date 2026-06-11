from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Callable, Optional

from pipeline.models import Item

log = logging.getLogger("throughline")

LLMJson = Callable[[str, str, dict], dict]
CacheGet = Callable[[list[str]], dict[str, dict]]
CachePut = Callable[[dict[str, dict]], None]

SUMMARY_CAP = 20
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

SYSTEM_PROMPT = (
    "You write tight, grounded summaries for an audience of engineers who ship "
    "ML systems. No hype, no corporate filler. For the given item, write 2-3 "
    "sentences: what it is, and why someone shipping ML systems should care. Then "
    "judge how hard it would be to reproduce or adopt: 'low', 'med', or 'high'."
)

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "repro_difficulty": {"type": "string", "enum": ["low", "med", "high"]},
    },
    "required": ["summary", "repro_difficulty"],
    "additionalProperties": False,
}


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


def _default_llm() -> Optional[LLMJson]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set; skipping summaries/labels")
        return None
    import anthropic

    client = anthropic.Anthropic()

    def call(system: str, user: str, schema: dict) -> dict:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return json.loads(text)

    return call


def _summary_prompt(item: Item) -> str:
    code = "yes" if item.has_code else "no"
    return (
        f"Title: {item.title}\n"
        f"Source: {item.source}\n"
        f"Code available: {code}\n"
        f"Abstract: {item.abstract}"
    )


def _store_get(keys: list[str]) -> dict[str, dict]:
    from pipeline import store

    return store.cache_get("summaries", keys)


def _store_put(entries: dict[str, dict]) -> None:
    from pipeline import store

    store.cache_put("summaries", entries)


def summarize_items(
    items: list[Item],
    llm: Optional[LLMJson] = None,
    cache_get: Optional[CacheGet] = None,
    cache_put: Optional[CachePut] = None,
) -> dict[str, dict]:
    get = cache_get or _store_get
    put = cache_put or _store_put
    keys = [_key(it) for it in items]
    cache = get(keys)
    missing = [it for it in items if _key(it) not in cache]
    fresh: dict[str, dict] = {}
    if missing:
        call = llm if llm is not None else _default_llm()
        if call is not None:
            for it in missing:
                try:
                    fresh[_key(it)] = call(SYSTEM_PROMPT, _summary_prompt(it), SUMMARY_SCHEMA)
                except Exception:  # one bad item must not kill the batch
                    log.exception("summary failed for %s; skipping", _key(it))
            if fresh:
                put(fresh)
            cache.update(fresh)
    return {k: cache[k] for k in keys if k in cache}


LABEL_SYSTEM = (
    "You name clusters of AI/ML items with short, specific topic labels of 2-4 "
    "words in Title Case, based on the member titles. Return one label per tag given."
)

LABELS_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["tag", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


def _labels_prompt(topics: list[dict], items: list[Item]) -> str:
    by_key = {_key(it): it for it in items}
    lines: list[str] = []
    for t in topics:
        lines.append(f"tag {t['tag']}:")
        for k in t["item_ids"][:5]:
            if k in by_key:
                lines.append(f"  - {by_key[k].title}")
    return "\n".join(lines)


def label_topics(
    topics: list[dict],
    items: list[Item],
    llm: Optional[LLMJson] = None,
) -> list[dict]:
    call = llm if llm is not None else _default_llm()
    if call is None:
        return topics
    try:
        result = call(LABEL_SYSTEM, _labels_prompt(topics, items), LABELS_SCHEMA)
        new_labels = {x["tag"]: x["label"] for x in result.get("labels", [])}
    except Exception:
        log.exception("topic labelling failed; keeping heuristic labels")
        return topics
    return [{**t, "label": new_labels.get(t["tag"], t["label"])} for t in topics]


def select_for_summary(
    items: list[Item],
    topic_by_key: dict[str, str],
    cap: int = SUMMARY_CAP,
) -> list[Item]:
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        groups[topic_by_key.get(_key(it), "all")].append(it)
    for g in groups.values():
        g.sort(key=lambda i: i.published_at or "", reverse=True)  # newest first

    selected: list[Item] = []
    tags = list(groups.keys())
    idx = 0
    while len(selected) < cap and any(groups.values()):
        tag = tags[idx % len(tags)]
        bucket = groups.get(tag)
        if bucket:
            selected.append(bucket.pop(0))
        idx += 1
        if idx > len(tags) * (cap + 1):  # safety: avoid infinite loop
            break
    return selected[:cap]
