"use client";

import { useEffect, useState } from "react";
import { getSaves, toggleSave, type SavedItem } from "@/lib/local";

export default function SavedPage() {
  const [saves, setSaves] = useState<SavedItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSaves(getSaves());
    setLoaded(true);
  }, []);

  function unsave(item: SavedItem) {
    toggleSave(item);
    setSaves(getSaves());
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Saved</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">stored in this browser only</p>
      {loaded && saves.length === 0 ? (
        <p className="mt-6 text-neutral-500">Nothing saved yet. Hit &quot;save&quot; on any post.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {saves.map((s) => (
            <li key={s.key} className="flex items-baseline justify-between gap-4 py-3">
              <div className="min-w-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-semibold decoration-amber-400/60 underline-offset-4 hover:underline"
                >
                  {s.title}
                </a>
                <p className="mt-0.5 font-mono text-[10px] text-neutral-500">
                  {s.source} · {s.date}
                </p>
              </div>
              <button
                type="button"
                onClick={() => unsave(s)}
                className="shrink-0 font-mono text-xs text-neutral-500 transition-colors hover:text-rose-400"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
