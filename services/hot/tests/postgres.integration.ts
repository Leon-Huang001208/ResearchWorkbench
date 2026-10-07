import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import postgres from 'postgres';
import { migrate, ingestPage, versionsAt } from '../src/database.ts';
import { parseFeed } from '../src/feed.ts';

test('real PostgreSQL page transaction, correction history and as-of evidence', async () => {
  const dir = resolve(import.meta.dirname, '../../../logs/hot-stage-zero');
  const receipt = JSON.parse(await readFile(resolve(dir, 'receipt.json'), 'utf8'));
  const password = await readFile(resolve(dir, 'password'), 'utf8');
  const db = postgres({ host: '127.0.0.1', port: receipt.port, database: 'hot_probe', username: 'postgres', password,
    max: 2, onnotice: () => {} });
  const instance = randomUUID();
  try {
    await migrate(db);
    const raw = await readFile(resolve(dir, 'fed.xml'), 'utf8');
    const seen = new Date();
    const materials = parseFeed(raw, 'https://www.federalreserve.gov/feeds/press_all.xml', seen).slice(0, 2);
    const source = `fed-${instance}`;
    await db`insert into hot.sources (id, operator, config) values (${source}, 'Federal Reserve', '{}'::jsonb)`;
    await assert.rejects(ingestPage(db, { source, raw, acquiredAt: seen, materials: [...materials, { ...materials[0], url: 'file:///tmp/invalid' }], cursor: { page: 1 } }));
    assert.equal((await db`select count(*)::int n from hot.discoveries where source_id = ${source}`)[0].n, 0);
    assert.equal((await db`select cursor from hot.sources where id = ${source}`)[0].cursor, null);
    const first = await ingestPage(db, { source, raw, acquiredAt: seen, materials, cursor: { page: 1 } });
    const again = await ingestPage(db, { source, raw, acquiredAt: new Date(), materials, cursor: { page: 1 } });
    assert.deepEqual(again.materialIds, first.materialIds);
    assert.equal(again.newVersions, 0);
    await assert.rejects(ingestPage(db, { source, raw, acquiredAt: seen, materials, cursor: { page: 0 } }), /hot_page_obsolete/);
    assert.deepEqual((await db`select cursor from hot.sources where id=${source}`)[0].cursor, { page: 1 });
    await assert.rejects(ingestPage(db, { source, raw, acquiredAt: new Date(),
      materials: [materials[0], { ...materials[0], title: 'conflicting same identity' }], cursor: { page: 2 } }), /hot_page_identity_conflict/);
    const before = await versionsAt(db, first.materialIds, new Date());
    const oldVersion = before.find(row => row.material_id === first.materialIds[0]);
    const changed = { ...materials[0], title: `${materials[0].title} (test correction ${instance})` };
    const correctionTime = new Date(Math.max(Date.now(), oldVersion.acquired_at.getTime() + 1));
    await ingestPage(db, { source, raw, acquiredAt: correctionTime, materials: [changed], cursor: { page: 2 } });
    const old = await versionsAt(db, [first.materialIds[0]], oldVersion.acquired_at);
    assert.equal(old[0].content_hash, oldVersion.content_hash);
    const current = await versionsAt(db, [first.materialIds[0]], correctionTime);
    assert.notEqual(current[0].content_hash, oldVersion.content_hash);
    await assert.rejects(db`update hot.material_versions set title='overwritten' where material_id=${first.materialIds[0]}`);
    // No accepted raw page or discovery can vanish due to a downstream stage failure.
    assert.equal((await db`select count(*)::int n from hot.raw_pages where source_id=${source}`)[0].n, 3);
    // Temporal regression fixture: later confirmation must be a new immutable version.
    const future = new Date(Date.now() + 86_400_000);
    const feed = `<rss><channel><item><title>Temporal fixture</title><link>https://example.com/${instance}</link><pubDate>${future.toISOString()}</pubDate></item></channel></rss>`;
    const temporalSource = `time-${instance}`;
    await db`insert into hot.sources(id,operator,config) values(${temporalSource},'test fixture','{}'::jsonb)`;
    const t0 = new Date();
    const initial = parseFeed(feed, 'https://example.com', t0);
    assert.equal(initial[0].publishedAt, null);
    const stored = await ingestPage(db, { source: temporalSource, raw: feed, acquiredAt: t0, materials: initial, cursor: {} });
    const confirmed = parseFeed(feed, 'https://example.com', future);
    const confirmedResult = await ingestPage(db, { source: temporalSource, raw: feed, acquiredAt: future, materials: confirmed, cursor: {} });
    assert.equal(confirmedResult.newVersions, 1);
    assert.equal((await versionsAt(db, stored.materialIds, t0))[0].published_at, null);
    assert.equal((await versionsAt(db, stored.materialIds, future))[0].published_at.toISOString(), future.toISOString());
  } finally {
    await db.end({ timeout: 5 });
  }
});
