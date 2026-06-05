import { promises as fs } from "fs";
import path from "path";
import type { Digest, IndexEntry } from "./types";

const CONTENT = path.join(process.cwd(), "content");

export async function getIndex(): Promise<IndexEntry[]> {
  try {
    const raw = await fs.readFile(path.join(CONTENT, "index.json"), "utf-8");
    return JSON.parse(raw) as IndexEntry[];
  } catch {
    return [];
  }
}

export async function getDigest(date: string): Promise<Digest | null> {
  try {
    const raw = await fs.readFile(
      path.join(CONTENT, "digests", `${date}.json`),
      "utf-8",
    );
    return JSON.parse(raw) as Digest;
  } catch {
    return null;
  }
}

export async function getLatestDigest(): Promise<Digest | null> {
  const index = await getIndex();
  if (index.length === 0) return null;
  return getDigest(index[0].date);
}
