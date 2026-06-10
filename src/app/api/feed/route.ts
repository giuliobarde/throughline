import { NextResponse } from "next/server";
import { getDigestsBefore } from "@/lib/content";
import { mergeDigests } from "@/lib/feed";

export async function GET(request: Request) {
  const before = new URL(request.url).searchParams.get("before");
  if (!before || !/^\d{4}-\d{2}-\d{2}$/.test(before)) {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
  const { digests, nextBefore } = await getDigestsBefore(before);
  return NextResponse.json({ items: mergeDigests(digests), nextBefore });
}
