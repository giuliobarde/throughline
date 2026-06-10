import type { Digest } from "@/lib/types";
import { getSyntheses } from "@/lib/synthesis";
import { trendingTopics } from "@/lib/trending";
import { SavesCard } from "./SavesCard";

export async function Sidebar({
  latest,
  previous,
}: {
  latest: Digest | null;
  previous: Digest | null;
}) {
  const [synthesis] = await getSyntheses();
  const trending = trendingTopics(latest, previous);

  return (
    <aside className="space-y-4">
      {synthesis && (
        <a
          href={`/synthesis/${synthesis.week}`}
          className="block rounded-xl border border-amber-500/30 bg-neutral-900/40 p-4 transition-colors hover:border-amber-500/60"
        >
          <p className="font-mono text-[10px] uppercase tracking-widest text-amber-500">📌 this week</p>
          <p className="mt-1.5 text-sm font-semibold leading-snug">{synthesis.title}</p>
          <p className="mt-1 font-mono text-[10px] text-neutral-500">weekly synthesis · {synthesis.date}</p>
        </a>
      )}

      {trending.length > 0 && (
        <div className="rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-4">
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">trending topics</p>
          <ul className="mt-2 space-y-1.5">
            {trending.map((t) => (
              <li key={t.tag} className="flex items-baseline justify-between gap-2">
                <a
                  href={`/topics/${t.tag}`}
                  className="truncate font-mono text-xs text-sky-400 transition-colors hover:text-sky-300"
                >
                  t/{t.tag}
                </a>
                <span className="font-mono text-[10px] text-neutral-500">
                  {t.count}
                  {t.delta > 0 ? ` ↑${t.delta}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <SavesCard />
    </aside>
  );
}
