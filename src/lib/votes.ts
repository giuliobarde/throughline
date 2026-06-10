import "server-only";
import { aggregateVotes, type VoteCounts } from "./feed";
import { getServiceClient } from "./supabase";

export async function getVoteCounts(): Promise<VoteCounts> {
  const client = getServiceClient();
  if (!client) return {};
  try {
    const { data, error } = await client
      .from("feedback")
      .select("item_id, signal")
      .range(0, 9999);
    if (error || !data) return {};
    return aggregateVotes(data as { item_id: string; signal: number }[]);
  } catch {
    return {};
  }
}
