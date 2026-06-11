import { NextResponse } from "next/server";
import { getAllDigests } from "@/lib/content";
import { itemKey, mergeDigests } from "@/lib/feed";
import { clientIp, createRateLimiter } from "@/lib/ratelimit";
import { searchItems } from "@/lib/search";

const limiter = createRateLimiter(30, 60_000);

export async function GET(request: Request) {
  if (!limiter.allow(clientIp(request))) {
    return NextResponse.json(
      { error: "rate limited" },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  }
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
