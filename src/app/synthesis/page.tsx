import { getSyntheses } from "@/lib/synthesis";

export const revalidate = 3600;

export default async function SynthesisPage() {
  const essays = await getSyntheses();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">Synthesis</h1>
      <p className="mt-1 font-mono text-xs text-neutral-500">
        Weekly throughlines across the digest.
      </p>
      {essays.length === 0 ? (
        <p className="mt-6 text-neutral-500">No synthesis essays yet.</p>
      ) : (
        <ul className="mt-6 divide-y divide-neutral-800">
          {essays.map((e) => (
            <li key={e.week} className="py-3">
              <a href={`/synthesis/${e.week}`} className="group block">
                <span className="font-mono text-xs text-neutral-500">
                  {e.week} · {e.date}
                </span>
                <span className="mt-1 block font-semibold group-hover:underline">
                  {e.title}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
