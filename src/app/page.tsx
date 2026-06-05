import { ItemCard } from "@/components/ItemCard";
import { getLatestDigest } from "@/lib/content";

export const revalidate = 3600; // ISR: rebuild hourly

export default async function HomePage() {
  const digest = await getLatestDigest();

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
      ) : (
        <div>
          {digest.items.map((item) => (
            <ItemCard key={`${item.source}:${item.id}`} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
