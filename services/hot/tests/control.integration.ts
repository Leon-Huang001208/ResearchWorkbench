import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomUUID, randomBytes } from 'node:crypto';
import postgres from 'postgres';
import { migrate } from '../src/database.ts';
import { initializeIdentity, activateRuntime, heartbeatRuntime, pauseRuntime, claimTask, commitClaim, renewClaim, failClaim } from '../src/control.ts';

test('runtime generations, real expiry, transactional commit and cache reuse reject old owners', async () => {
  const dir = resolve(import.meta.dirname, '../../../logs/hot-stage-zero');
  const receipt = JSON.parse(await readFile(resolve(dir, 'receipt.json'), 'utf8'));
  const password = await readFile(resolve(dir, 'password'), 'utf8');
  const db = postgres({ host: '127.0.0.1', port: receipt.port, database: 'hot_probe', username: 'postgres', password, max: 3, onnotice: () => {} });
  const schema = `hot_fences_${randomBytes(5).toString('hex')}`;
  const instance = randomUUID();
  const secret = randomBytes(32).toString('hex');
  try {
    await migrate(db, schema);
    await initializeIdentity(db, schema, instance, secret);
    await assert.rejects(initializeIdentity(db, schema, randomUUID(), secret), /hot_instance_mismatch/);
    await assert.rejects(activateRuntime(db, schema, instance, randomBytes(32).toString('hex'), 'native'), /hot_control_denied/);
    const native = await activateRuntime(db, schema, instance, secret, 'native');
    await heartbeatRuntime(db, schema, native, secret);
    const first = await claimTask(db, schema, native, randomUUID(), 'source:one', randomUUID());
    assert.equal(first.state, 'claimed');
    if (first.state !== 'claimed') throw Error('expected claim');
    const concurrent = await claimTask(db, schema, native, randomUUID(), 'source:one', randomUUID());
    assert.equal(concurrent.state, 'busy');
    const docker = await activateRuntime(db, schema, instance, secret, 'docker');
    let wrote = false;
    await assert.rejects(commitClaim(db, schema, first.claim, { old: true }, async () => { wrote = true; }), /hot_owner_stale/);
    assert.equal(wrote, false);
    const replacement = await claimTask(db, schema, docker, randomUUID(), 'source:one', randomUUID());
    assert.equal(replacement.state, 'claimed');
    if (replacement.state !== 'claimed') throw Error('expected replacement');
    await assert.rejects(commitClaim(db, schema, { ...first.claim, owner: docker }, { forged: true }), /hot_claim_stale/);
    await assert.rejects(commitClaim(db, schema, replacement.claim, { result: 1 }, async tx => {
      await tx`insert into ${tx(schema)}.sources (id,operator,config) values('rolled-back','fixture','{}'::jsonb)`;
      throw Error('business failure must roll back');
    }), /hot_commit_failed/);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.sources where id='rolled-back'`)[0].n, 0);
    await commitClaim(db, schema, replacement.claim, { result: 1 });
    const cached = await claimTask(db, schema, docker, randomUUID(), 'source:one', randomUUID());
    assert.deepEqual(cached, { state: 'reused', result: { result: 1 } });
    const expires = await claimTask(db, schema, docker, randomUUID(), 'source:expires', randomUUID(), 1);
    if (expires.state !== 'claimed') throw Error('expected expiry claim');
    await db`select pg_sleep(1.05)`;
    await assert.rejects(renewClaim(db, schema, expires.claim), /hot_claim_stale/);
    await assert.rejects(commitClaim(db, schema, expires.claim, {}), /hot_claim_stale/);
    const recovered = await claimTask(db, schema, docker, randomUUID(), 'source:expires', randomUUID());
    assert.equal(recovered.state, 'claimed');
    const slowFailure = await claimTask(db, schema, docker, randomUUID(), 'source:slow-fail', randomUUID(), 1);
    if (slowFailure.state !== 'claimed') throw Error('expected slow claim');
    await assert.rejects(failClaim(db, schema, slowFailure.claim, async tx => {
      await tx`insert into ${tx(schema)}.sources (id,operator,config) values('late-failure','fixture','{}'::jsonb)`;
      await tx`select pg_sleep(1.05)`;
    }), /hot_claim_stale/);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.sources where id='late-failure'`)[0].n, 0);
    await pauseRuntime(db, schema, docker, secret);
    if (recovered.state !== 'claimed') throw Error('expected recovery');
    await assert.rejects(commitClaim(db, schema, recovered.claim, {}), /hot_owner_stale/);
    const [attempts] = await db`select count(*)::int n from ${db(schema)}.job_attempts where outcome in ('expired','superseded')`;
    assert.equal(attempts.n, 2);
    await db`create function ${db(schema)}.slow_claim() returns trigger language plpgsql as
      'BEGIN IF NEW.input_key = ''source:slow-owner'' THEN PERFORM pg_sleep(1.05); END IF; RETURN NEW; END'`;
    await db`create trigger slow_claim before insert on ${db(schema)}.job_claims for each row execute function ${db(schema)}.slow_claim()`;
    const shortOwner = await activateRuntime(db, schema, instance, secret, 'native', 1);
    await assert.rejects(claimTask(db, schema, shortOwner, randomUUID(), 'source:slow-owner', randomUUID()), /hot_owner_stale/);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.job_claims where input_key='source:slow-owner'`)[0].n, 0);
  } finally {
    await db.end({ timeout: 5 });
  }
});
