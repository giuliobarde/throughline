import type { Digest, Item } from "./types";

export type FeedItem = Item & { digestDate: string };
export type FeedSort = "hot" | "new" | "foryou" | "top";
export type VoteCounts = Record<string, number>;

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
  return out;
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
