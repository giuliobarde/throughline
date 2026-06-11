import Link from "next/link";
import { itemKey, type FeedItem } from "@/lib/feed";
import { SaveButton } from "./SaveButton";
import { ShareButton } from "./ShareButton";
import { SourceBadge } from "./SourceBadge";
import { VoteRail } from "./VoteRail";

export function postDate(item: FeedItem): string {
  return (item.published_at || item.digestDate).slice(0, 10);
}

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function PostCard({ item, initialNet }: { item: FeedItem; initialNet: number }) {
  const key = itemKey(item);
  return (
    <article className="flex gap-3 rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700">
      <VoteRail itemKey={key} initialNet={initialNet} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.topic && (
            <Link
              href={`/topics/${item.topic}`}
              className="font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
            >
              t/{item.topic}
            </Link>
          )}
          <SourceBadge source={item.source} />
          <span className="font-mono text-xs text-neutral-500">{domain(item.url)}</span>
          <time className="font-mono text-xs text-neutral-500">{postDate(item)}</time>
        </div>
        <h2 className="mt-1.5 wrap-break-word text-base font-semibold leading-snug tracking-tight">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="decoration-amber-400/60 underline-offset-4 hover:underline"
          >
            {item.title}
          </a>
        </h2>
        <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-neutral-400">
          {item.summary ?? item.abstract}
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-4">
          {item.source === "hackernews" && (
            <a
              href={`https://news.ycombinator.com/item?id=${item.id.replace(/^hn:/, "")}`}
              target="_blank"
              rel="noreferrer"
              className="py-1 font-mono text-xs text-neutral-500 transition-colors hover:text-neutral-300"
            >
              discuss
            </a>
          )}
          <SaveButton
            item={{ key, title: item.title, url: item.url, source: item.source, date: postDate(item) }}
          />
          <ShareButton url={item.url} title={item.title} />
          {item.repro_difficulty && (
            <span className="font-mono text-xs text-amber-500">repro: {item.repro_difficulty}</span>
          )}
          {item.has_code && <span className="font-mono text-xs text-emerald-500">code</span>}
        </div>
      </div>
    </article>
  );
}
