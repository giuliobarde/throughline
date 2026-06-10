import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Throughline",
  description: "The tech wire, ranked daily — AI research & engineering, voted and ranked.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable}`}
    >
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <nav className="sticky top-0 z-10 border-b border-neutral-800 bg-neutral-950/80 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link
              href="/"
              className="group inline-flex items-baseline gap-2 transition-colors"
            >
              <span className="font-mono text-sm font-bold tracking-tight">
                throughline
              </span>
              <span className="hidden font-mono text-[10px] uppercase tracking-widest text-amber-500/80 sm:inline">
                the tech wire, ranked daily
              </span>
            </Link>
            <div className="flex items-center gap-5 font-mono text-xs text-neutral-400">
              <form action="/search">
                <input
                  name="q"
                  placeholder="search"
                  aria-label="Search the board"
                  className="w-24 rounded-md border border-neutral-800 bg-neutral-900/60 px-2.5 py-1 font-mono text-xs text-neutral-200 outline-none transition-all placeholder:text-neutral-600 focus:w-40 focus:border-amber-500/60 sm:w-28 sm:focus:w-48"
                />
              </form>
              <Link href="/topics" className="transition-colors hover:text-neutral-100">
                topics
              </Link>
              <Link href="/archive" className="transition-colors hover:text-neutral-100">
                archive
              </Link>
              <Link href="/synthesis" className="transition-colors hover:text-neutral-100">
                weekly
              </Link>
              <Link href="/about" className="transition-colors hover:text-neutral-100">
                about
              </Link>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
