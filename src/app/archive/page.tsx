import { getIndex } from "@/lib/content";

export const metadata = { title: "Archive — Throughline" };

export const revalidate = 3600;

export default async function ArchivePage() {
  const index = await getIndex();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Archive</h1>
      {index.length === 0 ? (
        <p className="mt-6 text-neutral-500">No digests yet.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {index.map((entry) => (
            <li
              key={entry.date}
              className="flex items-center justify-between py-3"
            >
              <span className="font-mono text-sm">{entry.date}</span>
              <span className="font-mono text-xs text-neutral-500">
                {entry.item_count} items
                {entry.has_synthesis ? " · synthesis" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
