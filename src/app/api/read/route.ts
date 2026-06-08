import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const { item_id, read } = (body ?? {}) as {
    item_id?: unknown;
    read?: unknown;
  };
  if (typeof item_id !== "string" || !item_id || typeof read !== "boolean") {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }

  const client = getServiceClient();
  if (!client) {
    return NextResponse.json({ error: "supabase not configured" }, { status: 503 });
  }

  const { error } = await client
    .from("read_state")
    .upsert(
      { item_id, read, updated_at: new Date().toISOString() },
      { onConflict: "item_id" },
    );
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
