import { NextResponse } from "next/server";
import { getAllDigests } from "@/lib/content";
import { itemKey, mergeDigests } from "@/lib/feed";
import { searchItems } from "@/lib/search";

export async function GET(request: Request) {
  const q = (new URL(request.url).searchParams.get("q") ?? "").trim();
  if (q.length > 100) {
    return NextResponse.json({ error: "query too long" }, { status: 400 });
  }
  if (!q) return NextResponse.json({ items: [] });
  const digests = await getAllDigests();
  const pool = mergeDigests(digests);
  const topics = digests[0]?.topics ?? [];
  const { items } = searchItems(pool, topics, q, 8);
  return NextResponse.json({
    items: items.map((i) => ({
      key: itemKey(i),
      title: i.title,
      url: i.url,
      source: i.source,
      date: (i.published_at || i.digestDate).slice(0, 10),
    })),
  });
}
