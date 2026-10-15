// Adapted from AIHOT lib/url.ts and content/materials.ts at 8e34e05f (MIT).
// Deliberate changes: reject credentials, preserve transport scheme, never invent a date.
import { createHash } from 'node:crypto';

const TRACKING = /^(utm_[a-z]+|spm|from|ref|ref_src|ref_url|source|share_source|share_token|fbclid|gclid|igshid|mc_cid|mc_eid|_hsenc|_hsmi|scene|chksm|sessionid|srcid|clicktime|enterid|mkt_tok)$/i;

export function identityKeyForUrl(input: string, keepFragment = false): string | null {
  let url: URL;
  try { url = new URL(input.trim()); } catch { return null; }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
  const fragment = keepFragment ? url.hash : '';
  url.hash = '';
  url.hostname = url.hostname.toLowerCase().replace(/^www\./, '');
  if (url.hostname === 'mp.weixin.qq.com') {
    const params = new URLSearchParams();
    for (const key of ['__biz', 'mid', 'idx', 'sn']) {
      const value = url.searchParams.get(key);
      if (value) params.set(key, value);
    }
    url.search = params.toString();
  } else {
    for (const key of [...url.searchParams.keys()]) if (TRACKING.test(key)) url.searchParams.delete(key);
    url.searchParams.sort();
  }
  let value = url.toString();
  if (value.endsWith('/') && url.pathname !== '/') value = value.slice(0, -1);
  return `url:${value}${fragment}`;
}

export function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

export function contentHash(content: { title: string; bodyText?: string | null; excerpt?: string | null }): string {
  return sha256([content.title, content.bodyText ?? '', content.excerpt ?? '']
    .map(value => value.replace(/\s+/g, ' ').trim()).join('\u0001'));
}

export function publicationTime(raw: string, seen: Date): Date | null {
  // A day or local timestamp without a zone is not a trusted instant.
  if (!/(?:Z|[+-]\d{2}:?\d{2}|GMT|UTC)\s*$/i.test(raw)) return null;
  const iso = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/i.exec(raw);
  const rfc = /^(?:[A-Za-z]{3},\s*)?(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?\s+(?:GMT|UTC|[+-]\d{4})$/i.exec(raw);
  let year: number, month: number, day: number, hour: number, minute: number, second: number;
  if (iso) {
    [, year, month, day, hour, minute, second] = iso.map(Number);
  } else if (rfc) {
    year = Number(rfc[3]); day = Number(rfc[1]);
    month = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].indexOf(rfc[2].toLowerCase()) + 1;
    hour = Number(rfc[4]); minute = Number(rfc[5]); second = Number(rfc[6] ?? 0);
  } else return null;
  if (year < 100 || month < 1 || month > 12 || day < 1 ||
    day > new Date(Date.UTC(year, month, 0)).getUTCDate() || hour > 23 || minute > 59 || second > 59) return null;
  const time = Date.parse(raw);
  if (!Number.isFinite(time) || time > seen.getTime() + 300_000) return null;
  return new Date(time);
}
