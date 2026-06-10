import type { FeedItem } from "./feed";
import type { Topic } from "./types";

export type SearchResults = { items: FeedItem[]; topics: Topic[] };

/** Bidirectional alias groups: a query term expands to its whole group. */
const ALIAS_GROUPS: string[][] = [
  ["claude", "anthropic"],
  ["gpt", "openai", "chatgpt"],
  ["gemini", "deepmind"],
  ["llama", "meta"],
  ["huggingface", "hf"],
];

function expand(term: string): string[] {
  for (const group of ALIAS_GROUPS) {
    if (group.includes(term)) return group;
  }
  return [term];
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function terms(q: string): string[] {
  return q.toLowerCase().split(/\s+/).filter(Boolean);
}

function itemDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

/** Scoring per term: title x3, hostname/authors x3 (identity), topic x2, body x1.
 *  Terms containing a dot are domain queries: hostname only. Aliases expand terms. */
export function searchItems(
  items: FeedItem[],
  topics: Topic[],
  q: string,
  limit = 20,
): SearchResults {
  const ts = terms(q);
  if (ts.length === 0) return { items: [], topics: [] };
  const labelByTag = new Map(topics.map((t) => [t.tag, t.label.toLowerCase()]));

  const matchers = ts.map((t) => {
    if (t.includes(".")) return { domain: t, raw: t, aliasRes: [] as RegExp[] };
    const aliasRes = expand(t)
      .filter((v) => v !== t)
      .map((v) => new RegExp(`\\b${escapeRegExp(v)}\\b`));
    return { domain: null as string | null, raw: t, aliasRes };
  });

  const ranked = items
    .map((item) => {
      const title = item.title.toLowerCase();
      const body = (item.summary ?? item.abstract).toLowerCase();
      const host = hostname(item.url);
      const authors = item.authors.join(" ").toLowerCase();
      const topicText = item.topic
        ? `${item.topic.toLowerCase()} ${labelByTag.get(item.topic) ?? ""}`
        : "";
      let score = 0;
      for (const m of matchers) {
        if (m.domain) {
          if (host === m.domain || host.endsWith("." + m.domain)) score += 3;
          continue;
        }
        const hit = (field: string) =>
          field.includes(m.raw) || m.aliasRes.some((r) => r.test(field));
        if (hit(title)) score += 3;
        if (hit(host) || hit(authors)) score += 3;
        if (hit(topicText)) score += 2;
        if (hit(body)) score += 1;
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
