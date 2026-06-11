"use client";

import Link from "next/link";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 px-6 py-24">
      <p className="font-mono text-6xl font-bold text-rose-400">500</p>
      <p className="text-neutral-400">something broke. it&rsquo;s not you.</p>
      <div className="flex gap-4">
        <button
          type="button"
          onClick={reset}
          className="font-mono text-xs text-amber-400 underline-offset-4 hover:underline"
        >
          try again
        </button>
        <Link
          href="/"
          className="font-mono text-xs text-neutral-500 underline-offset-4 transition-colors hover:text-neutral-200 hover:underline"
        >
          ← back to the board
        </Link>
      </div>
    </main>
  );
}
