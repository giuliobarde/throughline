export const metadata = { title: "About — Throughline" };

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-bold">About Throughline</h1>

      <div className="mt-6 space-y-4 leading-relaxed text-neutral-400">
        <p>
          Throughline is a self-updating board for AI research and engineering.
          Every three hours a pipeline pulls fresh items from arXiv, Hacker
          News, GitHub, first-party vendor blogs (OpenAI, DeepMind, Google AI,
          Hugging Face), and AI news — then clusters them into topics, writes
          tight summaries with Claude, and ranks everything into the feed.
        </p>
        <p>
          Votes are anonymous and feed a personalization model: the more the
          board gets voted on, the better the{" "}
          <span className="text-amber-400">For You</span> tab gets for
          everyone. Saves stay in your browser — no accounts, no tracking
          profiles.
        </p>
        <p>
          The archive reaches back to January 2026 and is fully searchable —
          try a model name, a company, or a domain like{" "}
          <span className="font-mono text-xs text-sky-400">anthropic.com</span>{" "}
          in the search box.
        </p>
        <p className="font-mono text-xs text-neutral-500">
          Built solo, AI-assisted, in public. Source on{" "}
          <a
            href="https://github.com/giuliobarde/throughline"
            target="_blank"
            rel="noreferrer"
            className="text-neutral-300 underline-offset-4 hover:underline"
          >
            GitHub
          </a>
          .
        </p>
      </div>
    </main>
  );
}
