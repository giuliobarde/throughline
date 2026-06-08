import "server-only";
import { getServiceClient } from "./supabase";

export async function getReadStates(): Promise<Set<string>> {
  const client = getServiceClient();
  if (!client) return new Set();
  try {
    const { data, error } = await client
      .from("read_state")
      .select("item_id")
      .eq("read", true);
    if (error || !data) return new Set();
    return new Set(data.map((r) => r.item_id as string));
  } catch {
    return new Set();
  }
}
