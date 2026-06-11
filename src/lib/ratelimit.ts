export type RateLimiter = { allow(key: string): boolean };

const MAX_KEYS = 10_000;

/** Sliding-window in-memory limiter. Per-instance only (Fluid Compute reuses
 *  instances, so this is a real but not distributed guard). */
export function createRateLimiter(
  limit: number,
  windowMs: number,
  now: () => number = Date.now,
): RateLimiter {
  const hits = new Map<string, number[]>();
  return {
    allow(key: string): boolean {
      const t = now();
      const cutoff = t - windowMs;
      if (hits.size > MAX_KEYS) {
        for (const [k, ts] of hits) {
          if (ts[ts.length - 1] <= cutoff) hits.delete(k);
        }
      }
      const ts = (hits.get(key) ?? []).filter((x) => x > cutoff);
      if (ts.length >= limit) {
        hits.set(key, ts);
        return false;
      }
      ts.push(t);
      hits.set(key, ts);
      return true;
    },
  };
}

export function clientIp(request: Request): string {
  const fwd = request.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return request.headers.get("x-real-ip") ?? "unknown";
}
