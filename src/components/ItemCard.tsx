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
      className={`border-b border-neutral-800 py-6 ${initialRead ? "opacity-60" : ""}`}
    >
      <div className="flex items-center gap-3">
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
            className="font-mono text-xs text-neutral-600 hover:text-neutral-300"
          >
            #{item.topic}
          </a>
        )}
        <time className="font-mono text-xs text-neutral-600">
          {item.published_at.slice(0, 10)}
        </time>
      </div>
      <h2 className="mt-2 text-lg font-semibold leading-snug">
        <a
          href={item.url}
          className="hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          {item.title}
        </a>
      </h2>
      <p className="mt-2 line-clamp-3 text-sm text-neutral-400">
        {item.summary ?? item.abstract}
      </p>
      {item.authors.length > 0 && (
        <p className="mt-2 font-mono text-xs text-neutral-600">
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
