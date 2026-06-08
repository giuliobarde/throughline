import ReactMarkdown from "react-markdown";
import { notFound } from "next/navigation";
import { getSyntheses, getSynthesis } from "@/lib/synthesis";

export const revalidate = 3600;

export async function generateStaticParams() {
  const essays = await getSyntheses();
  return essays.map((e) => ({ week: e.week }));
}

export default async function SynthesisReader({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const doc = await getSynthesis(week);
  if (!doc) notFound();

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="font-mono text-xs text-neutral-500">
        {doc.meta.week} · {doc.meta.date}
      </p>
      <h1 className="mt-1 text-2xl font-bold">{doc.meta.title}</h1>
      <div className="mt-6 space-y-4 leading-relaxed text-neutral-300 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-neutral-100">
        <ReactMarkdown>{doc.body}</ReactMarkdown>
      </div>
    </main>
  );
}
