import "server-only";
import { getServiceClient } from "./supabase";

export type SynthesisMeta = { week: string; title: string; date: string };

export async function getSyntheses(): Promise<SynthesisMeta[]> {
  const client = getServiceClient();
  if (!client) return [];
  try {
    const { data, error } = await client
      .from("syntheses")
      .select("week, title, date")
      .order("week", { ascending: false });
    if (error || !data) return [];
    return data as SynthesisMeta[];
  } catch {
    return [];
  }
}

export async function getSynthesis(
  week: string,
): Promise<{ meta: SynthesisMeta; body: string } | null> {
  const client = getServiceClient();
  if (!client) return null;
  try {
    const { data, error } = await client
      .from("syntheses")
      .select("week, title, date, body")
      .eq("week", week)
      .maybeSingle();
    if (error || !data) return null;
    const { body, ...meta } = data;
    return { meta: meta as SynthesisMeta, body: body as string };
  } catch {
    return null;
  }
}
