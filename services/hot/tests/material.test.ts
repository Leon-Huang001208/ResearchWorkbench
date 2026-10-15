import { test } from 'node:test';
import assert from 'node:assert/strict';
import { identityKeyForUrl, contentHash, publicationTime } from '../src/material.ts';

test('tracking links share identity; real query and section identity are preserved', () => {
  assert.equal(identityKeyForUrl('https://www.EXAMPLE.com/news/1?utm_source=rss'),
    identityKeyForUrl('https://example.com/news/1'));
  assert.notEqual(identityKeyForUrl('https://example.com/item?id=1'),
    identityKeyForUrl('https://example.com/item?id=2'));
  assert.notEqual(identityKeyForUrl('https://example.com/releases#one', true),
    identityKeyForUrl('https://example.com/releases#two', true));
  assert.equal(identityKeyForUrl('file:///tmp/news'), null);
  assert.equal(identityKeyForUrl('https://user:password@example.com/news'), null);
});

test('substantive correction changes version hash while layout does not', () => {
  assert.equal(contentHash({ title: 'A  policy', bodyText: 'one\n two' }),
    contentHash({ title: 'A policy', bodyText: 'one two' }));
  assert.notEqual(contentHash({ title: 'A policy', bodyText: 'effective today' }),
    contentHash({ title: 'A policy', bodyText: 'effective tomorrow' }));
});

test('unknown, timezone-less and future dates stay unknown', () => {
  const seen = new Date('2026-10-07T00:00:00Z');
  assert.equal(publicationTime('', seen), null);
  assert.equal(publicationTime('unavailable', seen), null);
  assert.equal(publicationTime('2026-10-06T20:00:00', seen), null);
  assert.equal(publicationTime('2026-10-09T00:00:00Z', seen), null);
  assert.equal(publicationTime('2026-02-30T00:00:00Z', seen), null);
  assert.equal(publicationTime('31 Feb 2026 00:00:00 GMT', seen), null);
  assert.equal(publicationTime('2026-09-01T00:00:00Z', seen)?.toISOString(), '2026-09-01T00:00:00.000Z');
});
