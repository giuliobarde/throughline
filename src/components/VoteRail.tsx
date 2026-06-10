"use client";

import { useEffect, useState } from "react";
import { getVote, setVote } from "@/lib/local";

export function VoteRail({
  itemKey,
  initialNet,
}: {
  itemKey: string;
  initialNet: number;
}) {
  const [mine, setMine] = useState<1 | -1 | 0>(0);
  const [delta, setDelta] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMine(getVote(itemKey));
  }, [itemKey]);

  async function vote(next: 1 | -1) {
    if (busy) return;
    const prevMine = mine;
    const prevDelta = delta;
    const value = mine === next ? 0 : next;
    setMine(value);
    setVote(itemKey, value);
    setDelta(delta + value - prevMine);
    if (value === 0) return; // clearing is local-only, like ItemActions did
    setBusy(true);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemKey, signal: value }),
      });
      if (!res.ok && res.status !== 503) {
        setMine(prevMine);
        setVote(itemKey, prevMine);
        setDelta(prevDelta);
      }
    } catch {
      setMine(prevMine);
      setVote(itemKey, prevMine);
      setDelta(prevDelta);
    } finally {
      setBusy(false);
    }
  }

  const btn = "leading-none transition-colors disabled:opacity-50";
  return (
    <div className="flex w-8 shrink-0 flex-col items-center gap-0.5 pt-0.5 font-mono text-xs">
      <button
        type="button"
        aria-label="Upvote"
        disabled={busy}
        onClick={() => vote(1)}
        className={`${btn} ${mine === 1 ? "text-amber-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▲
      </button>
      <span className="font-semibold text-neutral-300">{initialNet + delta}</span>
      <button
        type="button"
        aria-label="Downvote"
        disabled={busy}
        onClick={() => vote(-1)}
        className={`${btn} ${mine === -1 ? "text-rose-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▼
      </button>
    </div>
  );
}
