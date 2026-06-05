import type { Item } from "@/lib/types";

const LABELS: Record<Item["source"], string> = {
  arxiv: "arXiv",
  hackernews: "HN",
  github: "GitHub",
};

export function SourceBadge({ source }: { source: Item["source"] }) {
  return (
    <span className="font-mono text-xs uppercase tracking-wider text-neutral-500">
      {LABELS[source]}
    </span>
  );
}
