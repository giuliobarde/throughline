import Link from "next/link";
import { notFound } from "next/navigation";
import { Feed } from "@/components/Feed";
import { getLatestDigest, getLatestTopics, getTopic } from "@/lib/content";
import type { FeedItem } from "@/lib/feed";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 3600;

export async function generateStaticParams() {
  const topics = await getLatestTopics();
  return topics.map((t) => ({ tag: t.tag }));
}

export default async function TopicPage({
  params,
}: {
  params: Promise<{ tag: string }>;
}) {
  const { tag } = await params;
  const [topic, digest, votes] = await Promise.all([
    getTopic(tag),
    getLatestDigest(),
    getVoteCounts(),
  ]);
  if (!topic || !digest) notFound();
  const items: FeedItem[] = topic.items.map((i) => ({ ...i, digestDate: digest.date }));
  // eslint-disable-next-line react-hooks/purity
  const nowMs = Date.now();

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link href="/topics" className="font-mono text-xs text-neutral-500 hover:text-neutral-300">
        ← all topics
      </Link>
      <h1 className="mt-2 text-2xl font-bold">
        <span className="font-mono text-lg text-sky-400">t/{tag}</span> · {topic.label}
      </h1>
      <p className="mb-6 mt-1 font-mono text-xs text-neutral-500">{items.length} posts</p>
      <Feed initialItems={items} initialVotes={votes} initialBefore={null} nowMs={nowMs} />
    </main>
  );
}
