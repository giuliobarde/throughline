import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const { item_id, signal } = (body ?? {}) as {
    item_id?: unknown;
    signal?: unknown;
  };
  if (typeof item_id !== "string" || !item_id || (signal !== 1 && signal !== -1)) {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }

  const client = getServiceClient();
  if (!client) {
    return NextResponse.json({ error: "supabase not configured" }, { status: 503 });
  }

  const { error } = await client.from("feedback").insert({ item_id, signal });
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
