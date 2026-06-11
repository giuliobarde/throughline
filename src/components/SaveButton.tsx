"use client";

import { useEffect, useState } from "react";
import { getSaves, toggleSave, type SavedItem } from "@/lib/local";

export function SaveButton({ item }: { item: SavedItem }) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSaved(getSaves().some((s) => s.key === item.key));
  }, [item.key]);

  return (
    <button
      type="button"
      aria-label={saved ? "Unsave" : "Save"}
      onClick={() => setSaved(toggleSave(item))}
      className={`py-1 font-mono text-xs transition-colors ${saved ? "text-amber-400" : "text-neutral-500 hover:text-neutral-300"}`}
    >
      {saved ? "✓ saved" : "save"}
    </button>
  );
}
