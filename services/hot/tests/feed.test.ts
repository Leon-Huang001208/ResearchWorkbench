import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseFeed } from '../src/feed.ts';

test('Atom alternate links and explicit timestamps are retained', () => {
  const items = parseFeed('<feed><entry><id>tag:one</id><title>A</title><link rel="self" href="/api/one"/><link rel="alternate" href="/news/one"/><published>2026-10-06T00:00:00Z</published><updated>2026-10-06T01:00:00Z</updated><summary>evidence</summary></entry></feed>', 'https://example.com/feed', new Date('2026-10-07T00:00:00Z'));
  assert.equal(items[0].url, 'https://example.com/news/one');
  assert.equal(items[0].publishedAt?.toISOString(), '2026-10-06T00:00:00.000Z');
  assert.equal(items[0].sourceUpdatedAt?.toISOString(), '2026-10-06T01:00:00.000Z');
});

test('invalid or incomplete entries fail the page; watermark cannot skip them', () => {
  assert.throws(() => parseFeed('<rss><channel><item><title>Lost</title></item></channel></rss>', 'https://example.com', new Date()), /feed_entry_invalid/);
  assert.throws(() => parseFeed('<html>blocked</html>', 'https://example.com', new Date()), /feed_shape_invalid/);
  assert.throws(() => parseFeed('<rss><channel>', 'https://example.com', new Date()), /feed_xml_invalid/);
});

test('XML predefined entities decode without allowing document entity declarations', () => {
  const items = parseFeed('<rss><channel><item><title>A &amp; B</title><link>https://example.com/?id=1&amp;edition=2</link></item></channel></rss>', 'https://example.com', new Date());
  assert.equal(items[0].title, 'A & B');
  assert.equal(items[0].url, 'https://example.com/?id=1&edition=2');
  assert.throws(() => parseFeed('<!DOCTYPE rss [<!ENTITY x "secret">]><rss/>', 'https://example.com', new Date()), /feed_xml_invalid/);
});
