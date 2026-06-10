import { describe, expect, it } from "vitest";
import type { FeedItem } from "@/lib/feed";
import type { Item, Topic } from "@/lib/types";
import { searchItems } from "@/lib/search";

const base: Omit<Item, "id" | "source" | "title"> = {
  url: "https://example.com/x",
  abstract: "",
  authors: [],
  published_at: "2026-06-08T00:00:00+00:00",
  has_code: false,
  code_url: null,
};

function fi(id: string, title: string, extra: Partial<FeedItem> = {}): FeedItem {
  return { ...base, id, source: "arxiv", title, digestDate: "2026-06-08", ...extra };
}

const topics: Topic[] = [
  { tag: "agents", label: "Agent Safety", item_ids: [] },
  { tag: "training", label: "Training Efficiency", item_ids: [] },
];

describe("searchItems", () => {
  it("empty or whitespace query returns nothing", () => {
    expect(searchItems([fi("1", "LLM stuff")], topics, "")).toEqual({ items: [], topics: [] });
    expect(searchItems([fi("1", "LLM stuff")], topics, "   ")).toEqual({ items: [], topics: [] });
  });

  it("title matches outrank abstract matches", () => {
    const inTitle = fi("t", "Diffusion models go brrr");
    const inBody = fi("b", "Unrelated title", { abstract: "all about diffusion sampling" });
    const { items } = searchItems([inBody, inTitle], topics, "diffusion");
    expect(items.map((i) => i.id)).toEqual(["t", "b"]);
  });

  it("matches items via their topic's label", () => {
    const viaTopic = fi("k", "Plain title", { topic: "agents" });
    const { items } = searchItems([viaTopic], topics, "safety");
    expect(items.map((i) => i.id)).toEqual(["k"]); // matched via topic label "Agent Safety"
  });

  it("multi-term accumulates score and drops non-matches", () => {
    const both = fi("ab", "agent diffusion", {});
    const one = fi("a", "agent only");
    const none = fi("n", "nothing relevant");
    const { items } = searchItems([none, one, both], topics, "agent diffusion");
    expect(items.map((i) => i.id)).toEqual(["ab", "a"]);
  });

  it("ties break by newer published date and limit caps results", () => {
    const older = fi("old", "rag pipeline", { published_at: "2026-06-01T00:00:00+00:00" });
    const newer = fi("new", "rag pipeline", { published_at: "2026-06-08T00:00:00+00:00" });
    const { items } = searchItems([older, newer], topics, "rag");
    expect(items.map((i) => i.id)).toEqual(["new", "old"]);
    expect(searchItems([older, newer], topics, "rag", 1).items).toHaveLength(1);
  });

  it("returns matching topics by tag or label", () => {
    const { topics: matched } = searchItems([], topics, "training");
    expect(matched.map((t) => t.tag)).toEqual(["training"]);
  });
});
