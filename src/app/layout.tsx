import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { SearchBox } from "@/components/SearchBox";
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
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-y-2 px-4 py-3 sm:px-6 sm:py-4">
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
            <div className="ml-auto">
              <SearchBox />
            </div>
            <div className="order-last flex w-full items-center justify-between font-mono text-xs text-neutral-400 sm:order-0 sm:ml-5 sm:w-auto sm:justify-start sm:gap-6">
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
