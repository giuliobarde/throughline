export type Density = "cards" | "compact";
export type SavedItem = {
  key: string;
  title: string;
  url: string;
  source: string;
  date: string;
};

const DENSITY = "tl:density";
const VOTES = "tl:votes";
const SAVES = "tl:saves";

function read<T>(key: string, fallback: T): T {
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage full or blocked — degrade silently
  }
}

export function getDensity(): Density {
  return read<Density>(DENSITY, "cards");
}

export function setDensity(d: Density): void {
  write(DENSITY, d);
}

export function getVote(key: string): 1 | -1 | 0 {
  return read<Record<string, 1 | -1>>(VOTES, {})[key] ?? 0;
}

export function setVote(key: string, value: 1 | -1 | 0): void {
  const votes = read<Record<string, 1 | -1>>(VOTES, {});
  if (value === 0) delete votes[key];
  else votes[key] = value;
  write(VOTES, votes);
}

export function getSaves(): SavedItem[] {
  return read<SavedItem[]>(SAVES, []);
}

/** Returns the new saved state for this item. */
export function toggleSave(item: SavedItem): boolean {
  const saves = getSaves();
  const idx = saves.findIndex((s) => s.key === item.key);
  if (idx >= 0) {
    saves.splice(idx, 1);
    write(SAVES, saves);
    return false;
  }
  write(SAVES, [item, ...saves]);
  return true;
}
