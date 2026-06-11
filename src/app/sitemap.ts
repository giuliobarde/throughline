import type { MetadataRoute } from "next";
import { getLatestTopics } from "@/lib/content";

const BASE = "https://throughline-theta.vercel.app";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const topics = await getLatestTopics();
  const now = new Date();
  return [
    { url: `${BASE}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${BASE}/topics`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE}/archive`, lastModified: now, changeFrequency: "daily", priority: 0.5 },
    { url: `${BASE}/synthesis`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.3 },
    ...topics.map((t) => ({
      url: `${BASE}/topics/${t.tag}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];
}
