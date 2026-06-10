export type Item = {
  id: string;
  source: "arxiv" | "hackernews" | "github" | "news" | "blog";
  title: string;
  url: string;
  abstract: string;
  authors: string[];
  published_at: string;
  has_code: boolean;
  code_url: string | null;
  summary?: string;
  topic?: string;
  repro_difficulty?: "low" | "med" | "high";
  for_you_score?: number;
};

export type Topic = { tag: string; label: string; item_ids: string[] };

export type Digest = {
  date: string;
  generated_at: string;
  items: Item[];
  topics: Topic[];
};

export type IndexEntry = {
  date: string;
  item_count: number;
  has_synthesis: boolean;
};
