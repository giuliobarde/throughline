from __future__ import annotations

from collections import defaultdict

from pipeline.models import Item

SUMMARY_CAP = 20


def _key(item: Item) -> str:
    return f"{item.source}:{item.id}"


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
