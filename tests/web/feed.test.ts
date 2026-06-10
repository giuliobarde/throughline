import { describe, expect, it } from "vitest";
import type { Digest, Item } from "@/lib/types";
import { hotScore, itemKey, mergeDigests, sortFeed } from "@/lib/feed";

const base: Omit<Item, "id" | "source"> = {
  title: "t",
  url: "https://example.com/x",
  abstract: "a",
  authors: [],
  published_at: "2026-06-08T00:00:00+00:00",
  has_code: false,
  code_url: null,
};

function item(id: string, source: Item["source"], extra: Partial<Item> = {}): Item {
  return { ...base, id, source, ...extra };
}

function digest(date: string, items: Item[]): Digest {
  return { date, generated_at: `${date}T12:00:00+00:00`, items, topics: [] };
}

describe("itemKey", () => {
  it("joins source and id", () => {
    expect(itemKey(item("1", "arxiv"))).toBe("arxiv:1");
  });
});

describe("mergeDigests", () => {
  it("dedupes across digests keeping the newest occurrence and tags digestDate", () => {
    const newest = digest("2026-06-08", [item("1", "arxiv", { summary: "new" })]);
    const older = digest("2026-06-07", [item("1", "arxiv", { summary: "old" }), item("2", "github")]);
    const merged = mergeDigests([newest, older]); // newest first, as loaded
    expect(merged).toHaveLength(2);
    expect(merged[0]).toMatchObject({ id: "1", summary: "new", digestDate: "2026-06-08" });
    expect(merged[1]).toMatchObject({ id: "2", digestDate: "2026-06-07" });
  });
});

describe("hotScore", () => {
  it("decays with age and grows with net votes", () => {
    expect(hotScore(10, 1)).toBeGreaterThan(hotScore(10, 24));
    expect(hotScore(10, 5)).toBeGreaterThan(hotScore(0, 5));
  });
});

describe("sortFeed", () => {
  const now = new Date("2026-06-09T00:00:00+00:00");
  const fresh = { ...item("f", "github", { published_at: "2026-06-08T20:00:00+00:00" }), digestDate: "2026-06-08" };
  const popular = { ...item("p", "arxiv", { published_at: "2026-06-06T00:00:00+00:00" }), digestDate: "2026-06-06" };
  const stale = { ...item("s", "news", { published_at: "2026-05-01T00:00:00+00:00", for_you_score: 0.9 }), digestDate: "2026-05-02" };

  it("hot: heavy votes beat freshness with zero votes", () => {
    const out = sortFeed([fresh, popular], "hot", { "arxiv:p": 50 }, now);
    expect(out.map((i) => i.id)).toEqual(["p", "f"]);
  });

  it("new: newest published first", () => {
    const out = sortFeed([popular, fresh], "new", {}, now);
    expect(out[0].id).toBe("f");
  });

  it("foryou: for_you_score desc", () => {
    const out = sortFeed([fresh, stale], "foryou", {}, now);
    expect(out[0].id).toBe("s");
  });

  it("top: net votes desc, excludes items older than 7 days", () => {
    const out = sortFeed([fresh, popular, stale], "top", { "news:s": 100, "arxiv:p": 5 }, now);
    expect(out.map((i) => i.id)).toEqual(["p", "f"]); // stale excluded despite 100 votes
  });
});
