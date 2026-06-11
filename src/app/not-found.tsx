import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 px-6 py-24">
      <p className="font-mono text-6xl font-bold text-amber-400">404</p>
      <p className="text-neutral-400">this thread doesn&rsquo;t exist.</p>
      <Link
        href="/"
        className="font-mono text-xs text-neutral-500 underline-offset-4 transition-colors hover:text-neutral-200 hover:underline"
      >
        ← back to the board
      </Link>
    </main>
  );
}
