import { notFound } from "next/navigation";
import { ItemCard } from "@/components/ItemCard";
import { getLatestTopics, getTopic } from "@/lib/content";
import { getReadStates } from "@/lib/feedback";
import type { Item } from "@/lib/types";

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
  const topic = await getTopic(tag);
  if (!topic) notFound();
  const readSet = await getReadStates();
  const itemKey = (i: Item) => `${i.source}:${i.id}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <a
        href="/"
        className="font-mono text-xs text-neutral-500 hover:text-neutral-300"
      >
        ← all topics
      </a>
      <h1 className="mt-2 text-2xl font-bold">{topic.label}</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">
        {topic.items.length} items
      </p>
      <div className="mt-6">
        {topic.items.map((item) => (
          <ItemCard
            key={itemKey(item)}
            item={item}
            initialRead={readSet.has(itemKey(item))}
          />
        ))}
      </div>
    </main>
  );
}
