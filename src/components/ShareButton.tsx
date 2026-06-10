"use client";

import { useState } from "react";

export function ShareButton({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ url, title });
        return;
      } catch {
        // user cancelled or unsupported payload — fall through to copy
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked — nothing sensible to do
    }
  }

  return (
    <button
      type="button"
      aria-label="Share"
      onClick={share}
      className="font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"
    >
      {copied ? "copied!" : "share"}
    </button>
  );
}
