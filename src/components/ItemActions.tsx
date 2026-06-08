"use client";

import { useState } from "react";

export function ItemActions({
  itemId,
  initialRead,
}: {
  itemId: string;
  initialRead: boolean;
}) {
  const [signal, setSignal] = useState<1 | -1 | 0>(0);
  const [read, setRead] = useState(initialRead);
  const [busy, setBusy] = useState(false);

  async function sendFeedback(next: 1 | -1) {
    const prev = signal;
    const value = signal === next ? 0 : next; // toggle off if same
    setSignal(value);
    if (value === 0) return; // nothing to record when clearing
    setBusy(true);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemId, signal: value }),
      });
      if (!res.ok) setSignal(prev);
    } catch {
      setSignal(prev);
    } finally {
      setBusy(false);
    }
  }

  async function toggleRead() {
    const next = !read;
    setRead(next);
    setBusy(true);
    try {
      const res = await fetch("/api/read", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: itemId, read: next }),
      });
      if (!res.ok) setRead(!next);
    } catch {
      setRead(!next);
    } finally {
      setBusy(false);
    }
  }

  const base = "font-mono text-xs transition-colors disabled:opacity-50";
  return (
    <div className="mt-3 flex items-center gap-4">
      <button
        type="button"
        aria-label="Interesting"
        disabled={busy}
        onClick={() => sendFeedback(1)}
        className={`${base} ${signal === 1 ? "text-emerald-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▲ interesting
      </button>
      <button
        type="button"
        aria-label="Not interesting"
        disabled={busy}
        onClick={() => sendFeedback(-1)}
        className={`${base} ${signal === -1 ? "text-rose-400" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        ▼ not
      </button>
      <button
        type="button"
        aria-label="Toggle read"
        disabled={busy}
        onClick={toggleRead}
        className={`${base} ${read ? "text-neutral-300" : "text-neutral-600 hover:text-neutral-300"}`}
      >
        {read ? "✓ read" : "mark read"}
      </button>
    </div>
  );
}
