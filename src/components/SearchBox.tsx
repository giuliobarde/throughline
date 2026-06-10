"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Hit = { key: string; title: string; url: string; source: string; date: string };

export function SearchBox() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setHits([]);
      setOpen(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      return;
    }
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
          signal: ctrl.signal,
        });
        if (!res.ok) return;
        const data = (await res.json()) as { items: Hit[] };
        setHits(data.items);
        setOpen(data.items.length > 0);
      } catch {
        // aborted or offline — dropdown just stays as-is
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    function onDocMousedown(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocMousedown);
    return () => document.removeEventListener("mousedown", onDocMousedown);
  }, []);

  return (
    <div ref={boxRef} className="relative" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-controls="search-listbox" aria-label="Search the board">
      <form action="/search">
        <input
          name="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          placeholder="search"
          aria-label="Search the board"
          autoComplete="off"
          className="w-24 rounded-md border border-neutral-800 bg-neutral-900/60 px-2.5 py-1 font-mono text-xs text-neutral-200 outline-none transition-all placeholder:text-neutral-600 focus:w-40 focus:border-amber-500/60 sm:w-28 sm:focus:w-48"
        />
      </form>
      {open && hits.length > 0 && (
        <div
          id="search-listbox"
          role="listbox"
          aria-label="Search results"
          className="absolute right-0 top-full z-20 mt-2 w-72 rounded-xl border border-neutral-800 bg-neutral-950/95 p-1 shadow-xl backdrop-blur"
        >
          {hits.map((h) => (
            <a
              key={h.key}
              href={h.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg px-3 py-2 transition-colors hover:bg-neutral-900"
            >
              <span className="block truncate text-xs font-semibold text-neutral-200">
                {h.title}
              </span>
              <span className="font-mono text-[10px] uppercase text-neutral-500">
                {h.source} · {h.date}
              </span>
            </a>
          ))}
          <Link
            href={`/search?q=${encodeURIComponent(q.trim())}`}
            className="block rounded-lg px-3 py-2 font-mono text-[11px] text-amber-400 transition-colors hover:bg-neutral-900"
            onClick={() => setOpen(false)}
          >
            all results for &ldquo;{q.trim()}&rdquo; →
          </Link>
        </div>
      )}
    </div>
  );
}
