import { describe, expect, it } from "vitest";
import { clientIp, createRateLimiter } from "@/lib/ratelimit";

describe("createRateLimiter", () => {
  it("allows up to limit within window, then blocks", () => {
    let t = 0;
    const rl = createRateLimiter(2, 1000, () => t);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
  });

  it("re-allows after the window slides past old hits", () => {
    let t = 0;
    const rl = createRateLimiter(2, 1000, () => t);
    rl.allow("a");
    rl.allow("a");
    t = 1001;
    expect(rl.allow("a")).toBe(true);
  });

  it("isolates keys", () => {
    let t = 0;
    const rl = createRateLimiter(1, 1000, () => t);
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
    expect(rl.allow("b")).toBe(true);
  });
});

describe("clientIp", () => {
  it("takes the first x-forwarded-for hop", () => {
    const req = new Request("http://x", {
      headers: { "x-forwarded-for": "1.2.3.4, 5.6.7.8" },
    });
    expect(clientIp(req)).toBe("1.2.3.4");
  });

  it("falls back to x-real-ip then unknown", () => {
    expect(clientIp(new Request("http://x", { headers: { "x-real-ip": "9.9.9.9" } }))).toBe("9.9.9.9");
    expect(clientIp(new Request("http://x"))).toBe("unknown");
  });
});
