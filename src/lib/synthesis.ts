import { promises as fs } from "fs";
import path from "path";

export type SynthesisMeta = { week: string; title: string; date: string };

const DIR = path.join(process.cwd(), "content", "synthesis");

function parseFrontmatter(raw: string): { meta: SynthesisMeta; body: string } {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  const fields: Record<string, string> = {};
  if (m) {
    for (const line of m[1].split("\n")) {
      const idx = line.indexOf(":");
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      let val = line.slice(idx + 1).trim();
      if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
      fields[key] = val;
    }
  }
  return {
    meta: {
      week: fields.week ?? "",
      title: fields.title ?? "",
      date: fields.date ?? "",
    },
    body: (m ? m[2] : raw).trim(),
  };
}

export async function getSyntheses(): Promise<SynthesisMeta[]> {
  let files: string[];
  try {
    files = await fs.readdir(DIR);
  } catch {
    return [];
  }
  const out: SynthesisMeta[] = [];
  for (const f of files) {
    if (!f.endsWith(".mdx")) continue;
    const raw = await fs.readFile(path.join(DIR, f), "utf-8");
    out.push(parseFrontmatter(raw).meta);
  }
  return out.sort((a, b) => (a.week < b.week ? 1 : -1));
}

export async function getSynthesis(
  week: string,
): Promise<{ meta: SynthesisMeta; body: string } | null> {
  try {
    const raw = await fs.readFile(path.join(DIR, `${week}.mdx`), "utf-8");
    return parseFrontmatter(raw);
  } catch {
    return null;
  }
}
