import type { Digest } from "./types";

export type TrendingTopic = { tag: string; label: string; count: number; delta: number };

export function trendingTopics(
  latest: Digest | null,
  previous: Digest | null,
  limit = 5,
): TrendingTopic[] {
  if (!latest) return [];
  const prev = new Map((previous?.topics ?? []).map((t) => [t.tag, t.item_ids.length]));
  return latest.topics
    .map((t) => ({
      tag: t.tag,
      label: t.label,
      count: t.item_ids.length,
      delta: t.item_ids.length - (prev.get(t.tag) ?? 0),
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}
