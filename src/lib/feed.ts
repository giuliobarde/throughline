import type { Digest, Item } from "./types";

export type FeedItem = Item & { digestDate: string };
export type FeedSort = "hot" | "new" | "foryou" | "top";
export type VoteCounts = Record<string, number>;

const SOURCE_PRIORITY: Record<string, number> = {
  blog: 5,        // first-party announcement wins
  hackernews: 4,  // has discussion
  news: 3,
  arxiv: 2,
  github: 1,
};

function normTitle(title: string): string {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function itemKey(i: Pick<Item, "source" | "id">): string {
  return `${i.source}:${i.id}`;
}

/** Digests must be ordered newest-first; first occurrence of a key wins. */
export function mergeDigests(digests: Digest[]): FeedItem[] {
  const seen = new Set<string>();
  const out: FeedItem[] = [];
  for (const d of digests) {
    for (const item of d.items) {
      const key = itemKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ ...item, digestDate: d.date });
    }
  }
  const byTitle = new Map<string, FeedItem>();
  for (const item of out) {
    const t = normTitle(item.title);
    if (!t) continue;
    const prev = byTitle.get(t);
    if (!prev || (SOURCE_PRIORITY[item.source] ?? 0) > (SOURCE_PRIORITY[prev.source] ?? 0)) {
      byTitle.set(t, item);
    }
  }
  return out.filter((item) => {
    const t = normTitle(item.title);
    return !t || byTitle.get(t) === item;
  });
}

/** Gravity-style: votes push up, age pulls down. */
export function hotScore(net: number, ageHours: number): number {
  return Math.max(0, 1 + net) / Math.pow(ageHours + 2, 1.5);
}

function effectiveDate(i: FeedItem): number {
  const t = Date.parse(i.published_at);
  return Number.isNaN(t) ? Date.parse(i.digestDate) : t;
}

function ageHours(i: FeedItem, now: Date): number {
  return Math.max(0, (now.getTime() - effectiveDate(i)) / 3_600_000);
}

const WEEK_MS = 7 * 24 * 3_600_000;

export function sortFeed(
  items: FeedItem[],
  sort: FeedSort,
  votes: VoteCounts,
  now: Date,
): FeedItem[] {
  const net = (i: FeedItem) => votes[itemKey(i)] ?? 0;
  switch (sort) {
    case "hot":
      return [...items].sort(
        (a, b) => hotScore(net(b), ageHours(b, now)) - hotScore(net(a), ageHours(a, now)),
      );
    case "new":
      return [...items].sort((a, b) => effectiveDate(b) - effectiveDate(a));
    case "foryou":
      return [...items].sort((a, b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0));
    case "top":
      return items
        .filter((i) => now.getTime() - effectiveDate(i) <= WEEK_MS)
        .sort((a, b) => net(b) - net(a) || effectiveDate(b) - effectiveDate(a));
  }
}

export function aggregateVotes(rows: { item_id: string; signal: number }[]): VoteCounts {
  const out: VoteCounts = {};
  for (const r of rows) out[r.item_id] = (out[r.item_id] ?? 0) + r.signal;
  return out;
}
