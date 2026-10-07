import { XMLParser, XMLValidator } from 'fast-xml-parser';
import { identityKeyForUrl, publicationTime } from './material.ts';

export interface FeedMaterial {
  url: string;
  title: string;
  excerpt: string;
  upstreamId: string | null;
  publishedRaw: string;
  publishedAt: Date | null;
  updatedRaw: string;
  sourceUpdatedAt: Date | null;
}

function array(value: unknown): any[] {
  return value == null ? [] : Array.isArray(value) ? value : [value];
}

function text(value: any): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return value && typeof value === 'object' ? text(value['#text'] ?? value['#cdata']) : '';
}

export function parseFeed(raw: string, base: string, seen: Date): FeedMaterial[] {
  if (/<!(?:DOCTYPE|ENTITY)\b/i.test(raw) || XMLValidator.validate(raw) !== true) {
    throw Error('feed_xml_invalid');
  }
  const doc = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@',
    cdataPropName: '#cdata', processEntities: true }).parse(raw);
  const atom = doc.feed;
  const rss = doc.rss?.channel;
  const rdf = doc['rdf:RDF'];
  if (!atom && !rss && !rdf) throw Error('feed_shape_invalid');
  const entries = array(atom ? atom.entry : rss ? rss.item : rdf.item);
  if (entries.length > 2000) throw Error('feed_entry_limit');
  return entries.map(entry => {
    const links = array(entry.link);
    const alternate = links.find(link => typeof link === 'object' && (!link['@rel'] || link['@rel'] === 'alternate'));
    const href = atom ? alternate?.['@href'] : text(entry.link);
    let url: string;
    try { url = new URL(href || '', base).href; } catch { throw Error('feed_entry_invalid'); }
    const title = text(entry.title).trim();
    if (!href || !title || !identityKeyForUrl(url)) throw Error('feed_entry_invalid');
    const publishedRaw = text(entry.published ?? entry.pubDate ?? entry['dc:date']);
    const updatedRaw = text(entry.updated);
    return { url, title, excerpt: text(entry.summary ?? entry.description ?? entry['content:encoded'] ?? entry.content),
      upstreamId: text(entry.id ?? entry.guid) || null, publishedRaw,
      publishedAt: publicationTime(publishedRaw, seen), updatedRaw,
      sourceUpdatedAt: publicationTime(updatedRaw, seen) };
  });
}

// Stage-zero source candidates; production catalog ownership stays with DataHub.
export const PROBE_SOURCES = [
  { id: 'openai', operator: 'OpenAI', channel: 'ai', official: true, url: 'https://openai.com/news/rss.xml' },
  { id: 'deepmind', operator: 'Google', channel: 'ai', official: true, url: 'https://deepmind.google/blog/rss.xml' },
  { id: 'fed', operator: 'Federal Reserve', channel: 'macro', official: true, url: 'https://www.federalreserve.gov/feeds/press_all.xml' },
  { id: 'ecb', operator: 'ECB', channel: 'macro', official: true, url: 'https://www.ecb.europa.eu/rss/press.html' },
] as const;
