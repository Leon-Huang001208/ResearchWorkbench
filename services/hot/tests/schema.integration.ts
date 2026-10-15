import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomBytes } from 'node:crypto';
import postgres from 'postgres';
import { migrate, ingestPage, versionsAt, SCHEMA_VERSION } from '../src/database.ts';
import { parseFeed } from '../src/feed.ts';
import { parseConfig, poolOptions } from '../src/config.ts';
import { checkDatabase } from '../src/health.ts';
import { grantWorker } from '../src/provision.ts';
import { openQueue,enqueue,processOne } from '../src/queue.ts';
import { initializeIdentity,activateRuntime } from '../src/control.ts';
import { randomUUID } from 'node:crypto';

test('external scoped schema and a non-admin worker can ingest but cannot migrate or edit evidence', async () => {
  const dir = resolve(import.meta.dirname, '../../../logs/hot-stage-zero');
  const receipt = JSON.parse(await readFile(resolve(dir, 'receipt.json'), 'utf8'));
  const password = await readFile(resolve(dir, 'password'), 'utf8');
  const admin = postgres({ host: '127.0.0.1', port: receipt.port, database: 'hot_probe', username: 'postgres', password, onnotice: () => {} });
  const schema = `hot_custom_${randomBytes(5).toString('hex')}`;
  const user = `hot_worker_${randomBytes(5).toString('hex')}`;
  const workerPassword = randomBytes(32).toString('hex');
  let worker: ReturnType<typeof postgres> | undefined;
  try {
    await migrate(admin, schema);
    // Isolated test provisioning, not an arbitrary SQL operation available to product users.
    await admin.unsafe(`create role "${user}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
    const instance = randomUUID();
    const controller = randomBytes(32).toString('hex');
    await initializeIdentity(admin, schema, instance, controller);
    const queue = await openQueue(admin, schema, true);
    await queue.stop();
    await grantWorker(admin, schema, user);
    await admin`insert into ${admin(schema)}.sources (id,operator,config) values ('fed','Federal Reserve','{}'::jsonb)`;
    const config = parseConfig({ enabled: true, database: { mode: 'external',tls: 'disable',port: receipt.port, name: 'hot_probe', schema, user } });
    worker = postgres(poolOptions(config.database, workerPassword));
    const raw = await readFile(resolve(dir, 'fed.xml'), 'utf8');
    const acquiredAt = new Date();
    const materials = parseFeed(raw, 'https://www.federalreserve.gov/feeds/press_all.xml', acquiredAt).slice(0, 1);
    const stored = await ingestPage(worker, { source: 'fed', raw, acquiredAt, materials, cursor: { page: 1 } }, schema);
    assert.equal((await versionsAt(worker, stored.materialIds, new Date(), schema)).length, 1);
    await assert.rejects(migrate(worker, schema), /hot_migration_failed/);
    await assert.rejects(worker`update ${worker(schema)}.material_versions set title='overwritten'`);
    await assert.rejects(worker`delete from ${worker(schema)}.raw_pages`);
    await assert.rejects(worker`update ${worker(schema)}.sources set enabled=false`);
    const health = await checkDatabase(config, async () => workerPassword);
    assert.equal(health.state, 'ready');
    assert.equal(health.schemaVersion, SCHEMA_VERSION);
    await admin`revoke update(last_success_at) on ${admin(schema)}.sources from ${admin(user)}`;
    assert.equal((await checkDatabase(config, async () => workerPassword)).state, 'permission_denied');
    await admin`grant update(last_success_at) on ${admin(schema)}.sources to ${admin(user)}`;
    await assert.rejects(activateRuntime(worker, schema, instance, controller, 'native'), /hot_control_failed/);
    const owner = await activateRuntime(admin, schema, instance, controller, 'native');
    const workerQueue = await openQueue(worker, schema);
    assert.ok(await enqueue(workerQueue, worker, schema, owner, 'hot.process', 'process:role-test', {}));
    assert.equal(await processOne(workerQueue, worker, schema, owner, 'hot.process', async () => ({ result: { scopedRole: true } })), 'completed');
    await workerQueue.stop();
    await admin`grant postgres to ${admin(user)} with inherit false, set true`;
    try {
      assert.equal((await checkDatabase(config, async () => workerPassword)).state, 'permission_denied');
      await assert.rejects(grantWorker(admin, schema, user), /hot_worker_role_not_scoped/);
    } finally {
      await admin`revoke postgres from ${admin(user)}`;
    }
    const foreignSchema = `hot_foreign_${randomBytes(5).toString('hex')}`;
    await admin`create schema ${admin(foreignSchema)}`;
    await admin`create table ${admin(foreignSchema)}.unrelated(id int)`;
    await assert.rejects(migrate(admin, foreignSchema), /hot_schema_not_empty/);
    assert.equal((await admin`select to_regclass(${`${foreignSchema}.migrations`}) as table`)[0].table, null);
    for (const kind of ['view','function'] as const) {
      const foreign = `hot_foreign_${randomBytes(5).toString('hex')}`;
      await admin`create schema ${admin(foreign)}`;
      if (kind === 'view') await admin`create view ${admin(foreign)}.unrelated as select 1 as id`;
      else await admin`create function ${admin(foreign)}.unrelated() returns int language sql as 'select 1'`;
      await assert.rejects(migrate(admin, foreign), /hot_schema_not_empty/);
    }
    const superuserHealth = await checkDatabase(parseConfig({ enabled: true, database: { port: receipt.port, name: 'hot_probe', user: 'postgres' } }), async () => password);
    assert.equal(superuserHealth.state, 'permission_denied');
  } finally {
    if (worker) await worker.end({ timeout: 5 });
    await admin.end({ timeout: 5 });
  }
});
