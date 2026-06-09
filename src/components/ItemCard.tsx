import type { Item } from "@/lib/types";
import { SourceBadge } from "./SourceBadge";
import { ItemActions } from "./ItemActions";

export function ItemCard({
  item,
  initialRead = false,
}: {
  item: Item;
  initialRead?: boolean;
}) {
  return (
    <article
      className={`group border-b border-neutral-800/80 py-6 transition-opacity ${initialRead ? "opacity-50 hover:opacity-80" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <SourceBadge source={item.source} />
        {item.has_code && (
          <span className="font-mono text-xs text-emerald-500">code</span>
        )}
        {item.repro_difficulty && (
          <span className="font-mono text-xs text-amber-500">
            repro: {item.repro_difficulty}
          </span>
        )}
        {item.topic && (
          <a
            href={`/topics/${item.topic}`}
            className="font-mono text-xs text-neutral-500 transition-colors hover:text-amber-400"
          >
            #{item.topic}
          </a>
        )}
        <time className="font-mono text-xs text-neutral-500">
          {item.published_at.slice(0, 10)}
        </time>
      </div>
      <h2 className="mt-2 text-lg font-semibold leading-snug tracking-tight">
        <a
          href={item.url}
          className="decoration-amber-400/60 underline-offset-4 transition-colors group-hover:text-white hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          {item.title}
        </a>
      </h2>
      <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-neutral-400">
        {item.summary ?? item.abstract}
      </p>
      {item.authors.length > 0 && (
        <p className="mt-2 font-mono text-xs text-neutral-500">
          {item.authors.slice(0, 4).join(", ")}
          {item.authors.length > 4 ? " et al." : ""}
        </p>
      )}
      <ItemActions
        itemId={`${item.source}:${item.id}`}
        initialRead={initialRead}
      />
    </article>
  );
}
