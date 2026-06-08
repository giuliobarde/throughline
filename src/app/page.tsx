import { ItemCard } from "@/components/ItemCard";
import { getLatestDigest } from "@/lib/content";
import { getReadStates } from "@/lib/feedback";
import type { Item } from "@/lib/types";

export const revalidate = 3600; // ISR: rebuild hourly

export default async function HomePage() {
  const digest = await getLatestDigest();
  const readSet = await getReadStates();
  const itemKey = (i: Item) => `${i.source}:${i.id}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Today&rsquo;s digest</h1>
        {digest && (
          <p className="mt-1 font-mono text-xs text-neutral-500">
            {digest.date} · {digest.items.length} items
          </p>
        )}
      </header>

      {!digest || digest.items.length === 0 ? (
        <p className="text-neutral-500">
          No digest yet. The pipeline runs daily.
        </p>
      ) : digest.topics.length > 0 ? (
        <div className="space-y-12">
          {digest.topics.map((topic) => {
            const byKey = new Map(digest.items.map((i) => [itemKey(i), i]));
            const topicItems = topic.item_ids
              .map((id) => byKey.get(id))
              .filter((i): i is Item => Boolean(i));
            if (topicItems.length === 0) return null;
            return (
              <section key={topic.tag}>
                <h2 className="mb-2 font-mono text-xs uppercase tracking-wider text-neutral-500">
                  {topic.label}
                </h2>
                <div>
                  {topicItems.map((item) => (
                    <ItemCard
                      key={itemKey(item)}
                      item={item}
                      initialRead={readSet.has(itemKey(item))}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div>
          {digest.items.map((item) => (
            <ItemCard
              key={itemKey(item)}
              item={item}
              initialRead={readSet.has(itemKey(item))}
            />
          ))}
        </div>
      )}
    </main>
  );
}
