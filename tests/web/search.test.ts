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

  it("alias: 'claude' finds anthropic items via hostname and authors", () => {
    const viaHost = fi("h", "New model drops", { url: "https://www.anthropic.com/news/x" });
    const viaAuthor = fi("a", "Some announcement", {
      source: "blog",
      authors: ["Anthropic"],
      url: "https://example.org/y",
    });
    const miss = fi("m", "Unrelated", { url: "https://other.com/z" });
    const { items } = searchItems([miss, viaHost, viaAuthor], topics, "claude");
    expect(items.map((i) => i.id).sort()).toEqual(["a", "h"]);
  });

  it("alias works in reverse: 'openai' matches gpt in title", () => {
    const gptTitle = fi("g", "GPT-6 rumors intensify");
    const { items } = searchItems([gptTitle], topics, "openai");
    expect(items.map((i) => i.id)).toEqual(["g"]);
  });

  it("domain query matches hostname only", () => {
    const fromSite = fi("s", "Anything", { url: "https://anthropic.com/research/q" });
    const mentions = fi("m", "anthropic.com mentioned in title", { url: "https://other.com/p" });
    const { items } = searchItems([fromSite, mentions], topics, "anthropic.com");
    expect(items.map((i) => i.id)).toEqual(["s"]);
  });

  it("hostname match scores like a title match", () => {
    const hostHit = fi("hh", "Plain words", { url: "https://huggingface.co/blog/z" });
    const bodyHit = fi("bb", "Plain words", { abstract: "huggingface release notes" });
    const { items } = searchItems([bodyHit, hostHit], topics, "huggingface");
    expect(items.map((i) => i.id)).toEqual(["hh", "bb"]);
  });
});
