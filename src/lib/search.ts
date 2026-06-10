import type { FeedItem } from "./feed";
import type { Topic } from "./types";

export type SearchResults = { items: FeedItem[]; topics: Topic[] };

function terms(q: string): string[] {
  return q.toLowerCase().split(/\s+/).filter(Boolean);
}

function itemDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

/** Substring scoring: title x3, topic tag/label x2, summary-or-abstract x1. */
export function searchItems(
  items: FeedItem[],
  topics: Topic[],
  q: string,
  limit = 20,
): SearchResults {
  const ts = terms(q);
  if (ts.length === 0) return { items: [], topics: [] };
  const labelByTag = new Map(topics.map((t) => [t.tag, t.label.toLowerCase()]));

  const ranked = items
    .map((item) => {
      const title = item.title.toLowerCase();
      const body = (item.summary ?? item.abstract).toLowerCase();
      const topicText = item.topic
        ? `${item.topic.toLowerCase()} ${labelByTag.get(item.topic) ?? ""}`
        : "";
      let score = 0;
      for (const t of ts) {
        if (title.includes(t)) score += 3;
        if (topicText.includes(t)) score += 2;
        if (body.includes(t)) score += 1;
      }
      return { item, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || itemDate(b.item) - itemDate(a.item))
    .slice(0, limit)
    .map((s) => s.item);

  const matchedTopics = topics.filter((t) =>
    ts.some(
      (term) => t.tag.toLowerCase().includes(term) || t.label.toLowerCase().includes(term),
    ),
  );
  return { items: ranked, topics: matchedTopics };
}
