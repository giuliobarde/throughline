import type { Item } from "@/lib/types";

const LABELS: Record<Item["source"], string> = {
  arxiv: "arXiv",
  hackernews: "HN",
  github: "GitHub",
  news: "NEWS",
  blog: "BLOG",
};

// Each source gets a restrained accent so the feed is scannable at a glance.
const COLORS: Record<Item["source"], string> = {
  arxiv: "text-red-400",
  hackernews: "text-orange-400",
  github: "text-neutral-300",
  news: "text-sky-400",
  blog: "text-violet-400",
};

export function SourceBadge({ source }: { source: Item["source"] }) {
  return (
    <span
      className={`font-mono text-xs font-medium uppercase tracking-wider ${COLORS[source]}`}
    >
      {LABELS[source]}
    </span>
  );
}
