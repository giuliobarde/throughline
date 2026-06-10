import Link from "next/link";
import { PostCard } from "@/components/PostCard";
import { getRecentDigests } from "@/lib/content";
import { itemKey, mergeDigests } from "@/lib/feed";
import { searchItems } from "@/lib/search";
import { getVoteCounts } from "@/lib/votes";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();
  const [digests, votes] = await Promise.all([getRecentDigests(7), getVoteCounts()]);
  const pool = mergeDigests(digests);
  const topics = digests[0]?.topics ?? [];
  const { items, topics: matchedTopics } = searchItems(pool, topics, query);

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-bold">
        {query ? (
          <>
            results for <span className="text-amber-400">&ldquo;{query}&rdquo;</span>
          </>
        ) : (
          "Search"
        )}
      </h1>
      {!query ? (
        <p className="mt-6 text-neutral-500">Type something in the search box up top.</p>
      ) : (
        <>
          {matchedTopics.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {matchedTopics.map((t) => (
                <Link
                  key={t.tag}
                  href={`/topics/${t.tag}`}
                  className="rounded-full border border-neutral-800 px-3 py-1 font-mono text-xs text-sky-400 transition-colors hover:border-neutral-700"
                >
                  t/{t.tag} · {t.label}
                </Link>
              ))}
            </div>
          )}
          {items.length === 0 ? (
            <p className="mt-6 text-neutral-500">Nothing found in the current pool.</p>
          ) : (
            <div className="mt-6 space-y-3">
              {items.map((item) => (
                <PostCard
                  key={itemKey(item)}
                  item={item}
                  initialNet={votes[itemKey(item)] ?? 0}
                />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
