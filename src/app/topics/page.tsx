import { getLatestTopics } from "@/lib/content";

export const revalidate = 3600;

export default async function TopicsPage() {
  const topics = await getLatestTopics();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Topics</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">communities from today&rsquo;s board</p>
      {topics.length === 0 ? (
        <p className="mt-6 text-neutral-500">No topics yet.</p>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {topics.map((t) => (
            <a
              key={t.tag}
              href={`/topics/${t.tag}`}
              className="rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4 transition-colors hover:border-neutral-700"
            >
              <p className="font-mono text-xs text-sky-400">t/{t.tag}</p>
              <p className="mt-1 text-sm font-semibold">{t.label}</p>
              <p className="mt-1 font-mono text-[10px] text-neutral-500">{t.item_ids.length} posts</p>
            </a>
          ))}
        </div>
      )}
    </main>
  );
}
