import { promises as fs } from "fs";
import path from "path";
import type { Digest, Item, IndexEntry, Topic } from "./types";

const CONTENT = path.join(process.cwd(), "content");

export async function getIndex(): Promise<IndexEntry[]> {
  try {
    const raw = await fs.readFile(path.join(CONTENT, "index.json"), "utf-8");
    return JSON.parse(raw) as IndexEntry[];
  } catch {
    return [];
  }
}

export async function getDigest(date: string): Promise<Digest | null> {
  try {
    const raw = await fs.readFile(
      path.join(CONTENT, "digests", `${date}.json`),
      "utf-8",
    );
    return JSON.parse(raw) as Digest;
  } catch {
    return null;
  }
}

export async function getLatestDigest(): Promise<Digest | null> {
  const index = await getIndex();
  if (index.length === 0) return null;
  return getDigest(index[0].date);
}

export async function getLatestTopics(): Promise<Topic[]> {
  const digest = await getLatestDigest();
  return digest?.topics ?? [];
}

export async function getTopic(
  tag: string,
): Promise<{ label: string; items: Item[] } | null> {
  const digest = await getLatestDigest();
  if (!digest) return null;
  const topic = digest.topics.find((t) => t.tag === tag);
  if (!topic) return null;
  const byKey = new Map(digest.items.map((i) => [`${i.source}:${i.id}`, i]));
  const items = topic.item_ids
    .map((id) => byKey.get(id))
    .filter((i): i is Item => Boolean(i))
    .sort((a, b) => (b.for_you_score ?? 0) - (a.for_you_score ?? 0));
  return { label: topic.label, items };
}

export async function getRecentDigests(count = 7): Promise<Digest[]> {
  const index = await getIndex();
  const digests = await Promise.all(index.slice(0, count).map((e) => getDigest(e.date)));
  return digests.filter((d): d is Digest => Boolean(d));
}

export async function getDigestsBefore(
  date: string,
  count = 7,
): Promise<{ digests: Digest[]; nextBefore: string | null }> {
  const index = await getIndex();
  const older = index.filter((e) => e.date < date);
  const page = older.slice(0, count);
  const digests = (
    await Promise.all(page.map((e) => getDigest(e.date)))
  ).filter((d): d is Digest => Boolean(d));
  const nextBefore = older.length > count ? page[page.length - 1].date : null;
  return { digests, nextBefore };
}
