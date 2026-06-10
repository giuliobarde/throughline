import { Feed } from "@/components/Feed";
import { Sidebar } from "@/components/Sidebar";
import { getIndex, getRecentDigests } from "@/lib/content";
import { mergeDigests, sortFeed } from "@/lib/feed";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 3600; // ISR: rebuild hourly

const POOL_DIGESTS = 7;

export default async function HomePage() {
  const [index, digests, votes] = await Promise.all([
    getIndex(),
    getRecentDigests(POOL_DIGESTS),
    getVoteCounts(),
  ]);
  // eslint-disable-next-line react-hooks/purity
  const nowMs = Date.now();
  const pool = mergeDigests(digests);
  const initialItems = sortFeed(pool, "hot", votes, new Date(nowMs));
  const initialBefore =
    index.length > POOL_DIGESTS && digests.length > 0
      ? digests[digests.length - 1].date
      : null;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {initialItems.length === 0 ? (
        <p className="text-neutral-500">No posts yet. The pipeline runs daily.</p>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px]">
          <Feed
            initialItems={initialItems}
            votes={votes}
            initialBefore={initialBefore}
            nowMs={nowMs}
          />
          <Sidebar latest={digests[0] ?? null} previous={digests[1] ?? null} />
        </div>
      )}
    </main>
  );
}
