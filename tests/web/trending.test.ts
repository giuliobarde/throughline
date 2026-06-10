import { describe, expect, it } from "vitest";
import type { Digest } from "@/lib/types";
import { trendingTopics } from "@/lib/trending";

function digest(date: string, topics: Digest["topics"]): Digest {
  return { date, generated_at: `${date}T12:00:00+00:00`, items: [], topics };
}

describe("trendingTopics", () => {
  it("ranks by count with delta vs previous digest", () => {
    const latest = digest("2026-06-08", [
      { tag: "agents", label: "Agents", item_ids: ["a", "b", "c"] },
      { tag: "training", label: "Training", item_ids: ["d"] },
    ]);
    const previous = digest("2026-06-07", [
      { tag: "agents", label: "Agents", item_ids: ["a"] },
    ]);
    expect(trendingTopics(latest, previous)).toEqual([
      { tag: "agents", label: "Agents", count: 3, delta: 2 },
      { tag: "training", label: "Training", count: 1, delta: 1 },
    ]);
  });

  it("handles null inputs", () => {
    expect(trendingTopics(null, null)).toEqual([]);
  });
});
