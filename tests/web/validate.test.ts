import { describe, expect, it } from "vitest";
import { isValidItemId } from "@/lib/validate";

describe("isValidItemId", () => {
  it("accepts real key shapes from all five sources", () => {
    for (const id of [
      "arxiv:2606.07515",
      "hackernews:hn:48443258",
      "github:gh:owner/repo-name.py",
      "blog:blog:2be94cf79940",
      "news:news:abc123def456",
    ]) {
      expect(isValidItemId(id)).toBe(true);
    }
  });

  it("rejects junk", () => {
    for (const id of [
      "",
      "noprefix",
      "arxiv:has space",
      "UPPER:abc",
      "<script>alert(1)</script>",
      "arxiv:" + "x".repeat(120),
    ]) {
      expect(isValidItemId(id)).toBe(false);
    }
  });
});
