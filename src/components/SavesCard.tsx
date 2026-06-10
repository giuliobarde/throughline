"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSaves } from "@/lib/local";

export function SavesCard() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCount(getSaves().length);
  }, []);

  return (
    <Link
      href="/saved"
      className="block rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700"
    >
      <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">your saves</p>
      <p className="mt-1.5 text-sm text-neutral-300">
        {count} item{count === 1 ? "" : "s"}
      </p>
      <p className="mt-1 font-mono text-[10px] text-neutral-600">stored locally · no account needed</p>
    </Link>
  );
}
