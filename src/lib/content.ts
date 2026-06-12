import "server-only";
import type { Digest, IndexEntry, Item, Topic } from "./types";
import { getServiceClient } from "./supabase";

function isoWeek(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00Z`);
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-${String(week).padStart(2, "0")}`;
}

export async function getIndex(): Promise<IndexEntry[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    const [idx, syn] = await Promise.all([
      client
        .from("digest_index")
        .select("date, item_count")
        .order("date", { ascending: false }),
      client.from("syntheses").select("week"),
    ]);
    if (idx.error || !idx.data) return [];
    const weeks = new Set((syn.data ?? []).map((w) => w.week as string));
    return idx.data.map((r) => ({
      date: r.date as string,
      item_count: (r.item_count as number) ?? 0,
      has_synthesis: weeks.has(isoWeek(r.date as string)),
    }));
  } catch {
    return [];
  }
}

export async function getDigest(date: string): Promise<Digest | null> {
  const client = getServiceClient();
  if (!client) return null;
  try {
    const { data, error } = await client
      .from("digests")
      .select("payload")
      .eq("date", date)
      .maybeSingle();
    if (error || !data) return null;
    return data.payload as Digest;
  } catch {
    return null;
  }
}

async function digestsQuery(
  before: string | null,
  count: number | null,
): Promise<Digest[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    let q = client
      .from("digests")
      .select("payload")
      .order("date", { ascending: false });
    if (before) q = q.lt("date", before);
    if (count !== null) q = q.limit(count);
    const { data, error } = await q;
    if (error || !data) return [];
    return data.map((r) => r.payload as Digest);
  } catch {
    return [];
  }
}

export async function getLatestDigest(): Promise<Digest | null> {
  const [d] = await digestsQuery(null, 1);
  return d ?? null;
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
  return digestsQuery(null, count);
}

export async function getDigestsBefore(
  date: string,
  count = 7,
): Promise<{ digests: Digest[]; nextBefore: string | null }> {
  const page = await digestsQuery(date, count + 1);
  const digests = page.slice(0, count);
  const nextBefore =
    page.length > count && digests.length > 0
      ? digests[digests.length - 1].date
      : null;
  return { digests, nextBefore };
}

let allDigestsCache: { key: string; digests: Digest[] } | null = null;

/** Every digest, newest first. Cached per instance; invalidates on new head/length. */
export async function getAllDigests(): Promise<Digest[]> {
  const probe = await digestsQuery(null, 1);
  const head = probe[0]?.date ?? "";
  if (allDigestsCache && allDigestsCache.key.startsWith(`${head}:`)) {
    return allDigestsCache.digests;
  }
  const digests = await digestsQuery(null, null);
  allDigestsCache = { key: `${head}:${digests.length}`, digests };
  return digests;
}
