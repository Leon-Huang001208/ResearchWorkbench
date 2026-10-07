import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomUUID, randomBytes } from 'node:crypto';
import postgres from 'postgres';
import { migrate, ingestPage, versionsAt } from '../src/database.ts';
import { initializeIdentity, activateRuntime, claimTask, heartbeatRuntime } from '../src/control.ts';
import { openQueue, enqueue, processOne, transactionAdapter, superviseOwner } from '../src/queue.ts';
import { parseFeed } from '../src/feed.ts';
import { parseConfig } from '../src/config.ts';
import { runWorker } from '../src/worker.ts';

test('pg-boss and real material writes commit atomically, deduplicate and reuse results after restart', async () => {
  const dir = resolve(import.meta.dirname, '../../../logs/hot-stage-zero');
  const receipt = JSON.parse(await readFile(resolve(dir, 'receipt.json'), 'utf8'));
  const password = await readFile(resolve(dir, 'password'), 'utf8');
  const db = postgres({ host: '127.0.0.1', port: receipt.port, database: 'hot_probe', username: 'postgres', password, max: 3, onnotice: () => {} });
  const schema = `${'h'.repeat(37)}_${randomBytes(5).toString('hex')}`;
  let boss: Awaited<ReturnType<typeof openQueue>> | undefined;
  try {
    await migrate(db, schema);
    const adapter = transactionAdapter(db);
    assert.deepEqual((await adapter.executeSql('select $1::jsonb as payload', [JSON.stringify({ nested: [1, true, 'x'] })])).rows[0].payload, { nested: [1, true, 'x'] });
    const uuid = randomUUID();
    assert.equal((await adapter.executeSql('select $1::uuid as id', [uuid])).rows[0].id, uuid);
    assert.deepEqual((await adapter.executeSql('select 1 as first; select 2 as last')).rows, [{ last: 2 }]);
    const instance = randomUUID();
    const secret = randomBytes(32).toString('hex');
    await initializeIdentity(db, schema, instance, secret);
    const owner = await activateRuntime(db, schema, instance, secret, 'native');
    boss = await openQueue(db, schema, true);
    assert.equal((await boss.getQueue('hot.process'))?.retryLimit, 0);
    assert.equal((await boss.getQueue('hot.research'))?.retryLimit, 0);
    await db`insert into ${db(schema)}.sources (id,operator,config) values('fed','Federal Reserve','{}'::jsonb)`;
    const raw = await readFile(resolve(dir, 'fed.xml'), 'utf8');
    const acquiredAt = new Date();
    const materials = parseFeed(raw, 'https://www.federalreserve.gov/feeds/press_all.xml', acquiredAt).slice(0, 1);
    const id = await enqueue(boss, db, schema, owner, 'hot.parse', 'parse:fed:one', {});
    assert.ok(id);
    assert.equal(await enqueue(boss, db, schema, owner, 'hot.parse', 'parse:fed:one', {}), null);
    let calls = 0;
    const handler = async () => {
      calls++;
      return { result: { identity: materials[0].url }, commit: async (tx: postgres.TransactionSql) => {
        await ingestPage(tx, { source: 'fed', raw, acquiredAt, materials, cursor: { page: 1 } }, schema);
      } };
    };
    assert.equal(await processOne(boss, db, schema, owner, 'hot.parse', handler), 'completed');
    assert.equal(calls, 1);
    assert.equal((await boss.getJobById('hot.parse', id))?.state, 'completed');
    await boss.stop();
    boss = await openQueue(db, schema);
    const replay = await enqueue(boss, db, schema, owner, 'hot.parse', 'parse:fed:one', {});
    assert.ok(replay);
    assert.equal(await processOne(boss, db, schema, owner, 'hot.parse', handler), 'reused');
    assert.equal(calls, 1);
    const stored = await db`select id from ${db(schema)}.materials`;
    assert.equal((await versionsAt(db, [stored[0].id], new Date(), schema)).length, 1);
    const failingJob = await enqueue(boss, db, schema, owner, 'hot.parse', 'parse:fed:fail', {});
    assert.ok(failingJob);
    assert.equal(await processOne(boss, db, schema, owner, 'hot.parse', async () => ({ result: {}, commit: async tx => {
      await tx`insert into ${tx(schema)}.sources(id,operator,config) values('must-rollback','fixture','{}'::jsonb)`;
      throw Error('business commit failed');
    } })), 'failed');
    assert.equal((await db`select count(*)::int n from ${db(schema)}.sources where id='must-rollback'`)[0].n, 0);
    assert.equal((await boss.getJobById('hot.parse', failingJob))?.state, 'retry');
    // Real queue expiry after a fetched executor disappears; a stale supervisor cannot mutate it.
    await boss.updateQueue('hot.collect', { expireInSeconds: 1, retryDelay: 0, retryBackoff: false });
    const crashed = await enqueue(boss, db, schema, owner, 'hot.collect', 'collect:crash', {});
    assert.ok(crashed);
    const fetched = await boss.fetch<{ inputKey: string }>('hot.collect');
    assert.equal(fetched[0].id, crashed);
    assert.equal((await claimTask(db, schema, owner, crashed, fetched[0].data.inputKey, randomUUID(), 1)).state, 'claimed');
    const replacement = await activateRuntime(db, schema, instance, secret, 'docker');
    await db`select pg_sleep(1.15)`;
    await assert.rejects(superviseOwner(db, schema, owner, 'hot.collect'), /hot_owner_stale/);
    assert.equal((await boss.getJobById('hot.collect', crashed))?.state, 'active');
    await superviseOwner(db, schema, replacement, 'hot.collect');
    assert.equal((await boss.getJobById('hot.collect', crashed))?.state, 'retry');
    assert.equal(await processOne(boss, db, schema, replacement, 'hot.collect', async () => ({ result: { recovered: true } })), 'completed');
    const shutdown = new AbortController();
    const workerJob = await enqueue(boss, db, schema, replacement, 'hot.brief', 'brief:loop', {});
    assert.ok(workerJob);
    await runWorker({ db,controllerDb: db,boss,schema,owner: replacement,
      config: parseConfig({ enabled: true,worker: { concurrency: 2 } }),signal: shutdown.signal,
      heartbeat: () => heartbeatRuntime(db, schema, replacement, secret),
      handlers: { 'hot.brief': async () => {
        setTimeout(() => shutdown.abort(), 50);
        return { result: { drained: true } };
      } } });
    assert.equal((await boss.getJobById('hot.brief', workerJob))?.state, 'completed');
  } finally {
    if (boss) await boss.stop();
    await db.end({ timeout: 5 });
  }
});
