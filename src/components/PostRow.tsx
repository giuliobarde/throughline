import { itemKey, type FeedItem } from "@/lib/feed";
import { domain, postDate } from "./PostCard";
import { SaveButton } from "./SaveButton";
import { SourceBadge } from "./SourceBadge";
import { VoteRail } from "./VoteRail";

export function PostRow({ item, initialNet }: { item: FeedItem; initialNet: number }) {
  const key = itemKey(item);
  return (
    <article className="flex gap-3 border-b border-neutral-800/80 py-2.5">
      <VoteRail itemKey={key} initialNet={initialNet} />
      <div className="min-w-0 flex-1">
        <h2 className="text-sm font-semibold leading-snug">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="decoration-amber-400/60 underline-offset-4 hover:underline"
          >
            {item.title}
          </a>{" "}
          {domain(item.url) && (
            <span className="font-mono text-xs font-normal text-neutral-500">({domain(item.url)})</span>
          )}
        </h2>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.topic && (
            <a
              href={`/topics/${item.topic}`}
              className="font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
            >
              t/{item.topic}
            </a>
          )}
          <SourceBadge source={item.source} />
          <time className="font-mono text-xs text-neutral-500">{postDate(item)}</time>
          <SaveButton
            item={{ key, title: item.title, url: item.url, source: item.source, date: postDate(item) }}
          />
        </div>
      </div>
    </article>
  );
}
