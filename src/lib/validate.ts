/** source-prefixed item key, e.g. "hackernews:hn:48443258". */
export const ITEM_ID_RE = /^[a-z]+:[A-Za-z0-9._:/-]+$/;

export function isValidItemId(s: string): boolean {
  return s.length > 0 && s.length <= 120 && ITEM_ID_RE.test(s);
}
