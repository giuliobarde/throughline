"use client";

import { useEffect, useRef, useState } from "react";
import { itemKey, sortFeed, type FeedItem, type FeedSort, type VoteCounts } from "@/lib/feed";
import { getDensity, setDensity, type Density } from "@/lib/local";
import { PostCard } from "./PostCard";
import { PostRow } from "./PostRow";

const TABS: { id: FeedSort; label: string }[] = [
  { id: "hot", label: "Hot" },
  { id: "new", label: "New" },
  { id: "foryou", label: "For You" },
  { id: "top", label: "Top" },
];

export function Feed({
  initialItems,
  votes,
  initialBefore,
  nowMs,
}: {
  initialItems: FeedItem[];
  votes: VoteCounts;
  initialBefore: string | null;
  nowMs: number;
}) {
  const [sort, setSort] = useState<FeedSort>("hot");
  const [density, setDens] = useState<Density>("cards");
  const [pool, setPool] = useState<FeedItem[]>(initialItems);
  const [before, setBefore] = useState<string | null>(initialBefore);
  const [loading, setLoading] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDens(getDensity());
  }, []);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || !before) return;
    const io = new IntersectionObserver(async (entries) => {
      if (!entries[0].isIntersecting || loading) return;
      setLoading(true);
      try {
        const res = await fetch(`/api/feed?before=${before}`);
        if (!res.ok) {
          setBefore(null);
          return;
        }
        const data = (await res.json()) as { items: FeedItem[]; nextBefore: string | null };
        setPool((p) => {
          const seen = new Set(p.map(itemKey));
          return [...p, ...data.items.filter((i) => !seen.has(itemKey(i)))];
        });
        setBefore(data.nextBefore);
      } catch {
        setBefore(null);
      } finally {
        setLoading(false);
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, [before, loading]);

  function pickDensity(d: Density) {
    setDens(d);
    setDensity(d);
  }

  const items = sortFeed(pool, sort, votes, new Date(nowMs));
  const toggle = (active: boolean) =>
    `px-2 py-1 font-mono text-[11px] transition-colors sm:px-2.5 sm:text-xs ${active ? "bg-neutral-800 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`;

  return (
    <div className="min-w-0">
      <div className="mb-4 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2">
        <div className="flex gap-1" role="tablist" aria-label="Sort feed">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={sort === t.id}
              onClick={() => setSort(t.id)}
              className={`whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[11px] transition-colors sm:px-3 sm:text-xs ${
                sort === t.id
                  ? "bg-amber-500 font-bold text-neutral-950"
                  : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex overflow-hidden rounded-md border border-neutral-800">
          <button type="button" onClick={() => pickDensity("cards")} className={toggle(density === "cards")}>
            cards
          </button>
          <button type="button" onClick={() => pickDensity("compact")} className={toggle(density === "compact")}>
            compact
          </button>
        </div>
      </div>

      {sort === "top" && items.length === 0 ? (
        <p className="py-8 text-sm text-neutral-500">Nothing voted up in the last 7 days yet.</p>
      ) : density === "cards" ? (
        <div className="space-y-3">
          {items.map((item) => (
            <PostCard key={itemKey(item)} item={item} initialNet={votes[itemKey(item)] ?? 0} />
          ))}
        </div>
      ) : (
        <div>
          {items.map((item) => (
            <PostRow key={itemKey(item)} item={item} initialNet={votes[itemKey(item)] ?? 0} />
          ))}
        </div>
      )}

      <div ref={sentinel} className="h-8" aria-hidden="true" />
      {loading && <p className="pb-6 text-center font-mono text-xs text-neutral-500">loading…</p>}
    </div>
  );
}
