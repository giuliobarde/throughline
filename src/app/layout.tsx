import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  description: "Self-updating AI research & engineering intelligence hub.",
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
          <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
            <a
              href="/"
              className="group inline-flex items-baseline gap-2 transition-colors"
            >
              <span className="font-mono text-sm font-bold tracking-tight">
                throughline
              </span>
              <span className="hidden font-mono text-[10px] uppercase tracking-widest text-amber-500/80 sm:inline">
                the daily AI throughline
              </span>
            </a>
            <div className="flex gap-6 font-mono text-xs text-neutral-400">
              <a href="/archive" className="transition-colors hover:text-neutral-100">
                archive
              </a>
              <a
                href="/synthesis"
                className="transition-colors hover:text-neutral-100"
              >
                synthesis
              </a>
              <a href="/about" className="transition-colors hover:text-neutral-100">
                about
              </a>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
