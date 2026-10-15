/** Database-backed runtime generation and finite commit fences; no queue scheduling here. */
import type postgres from 'postgres';
import { randomUUID } from 'node:crypto';
import { schemaName } from './config.ts';
import { sha256 } from './material.ts';
import { logEvent } from './log.ts';

type Sql = ReturnType<typeof postgres>;
export type Tx = postgres.TransactionSql;
export interface RuntimeOwner { instanceId: string; mode: 'native' | 'docker'; generation: string }
export interface Claim { inputKey: string; jobId: string; workerId: string; leaseToken: string; owner: RuntimeOwner }
export type ClaimResult = { state: 'claimed'; claim: Claim } | { state: 'busy' } | { state: 'reused'; result: postgres.JSONValue };
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function identity(value: string) { if (!UUID.test(value)) throw Error('hot_identity_invalid'); }
function duration(seconds: number) { if (!Number.isInteger(seconds) || seconds < 1 || seconds > 1800) throw Error('hot_lease_invalid'); }
function token(value: string) { if (!/^[A-Za-z0-9_\-]{32,128}$/.test(value)) throw Error('hot_controller_token_invalid'); }
function safeError(error: unknown, fallback: string) {
  if (error instanceof Error && /^hot_[a-z_]+$/.test(error.message)) return error;
  return Error(fallback);
}
function ownerValid(owner: RuntimeOwner) {
  identity(owner.instanceId);
  if (!['native','docker'].includes(owner.mode) || !/^\d{1,18}$/.test(owner.generation)) throw Error('hot_owner_invalid');
}
async function lock(tx: Tx, schema: string) {
  // Activation and commit use this same lock without granting worker UPDATE on identity.
  await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
}
async function active(tx: Tx, schema: string, owner: RuntimeOwner) {
  const rows = await tx`select singleton from ${tx(schema)}.runtime_identity where singleton
    and instance_id=${owner.instanceId} and mode=${owner.mode} and generation=${owner.generation}
    and not paused and owner_until > clock_timestamp()`;
  if (rows.length !== 1) throw Error('hot_owner_stale');
}
export async function withOwnerTransaction<T>(db: Sql, schema: string, owner: RuntimeOwner, operation: (tx: Tx) => Promise<T>): Promise<T> {
  schemaName(schema); ownerValid(owner);
  return db.begin(async tx => {
    await lock(tx, schema);
    await active(tx, schema, owner);
    const result = await operation(tx);
    await active(tx, schema, owner);
    return result;
  }) as Promise<T>;
}
export async function initializeIdentity(db: Sql, schema: string, instanceId: string, controllerToken: string): Promise<void> {
  schemaName(schema); identity(instanceId); token(controllerToken);
  await db.begin(async tx => {
    await lock(tx, schema);
    const [permission] = await tx`select has_schema_privilege(current_user,${schema},'CREATE') as allowed`;
    if (!permission.allowed) throw Error('hot_identity_provision_denied');
    await tx`insert into ${tx(schema)}.runtime_identity(instance_id,controller_token_hash)
      values (${instanceId},${sha256(controllerToken)}) on conflict(singleton) do nothing`;
    const [row] = await tx`select instance_id,controller_token_hash from ${tx(schema)}.runtime_identity where singleton`;
    if (row.instance_id !== instanceId || row.controller_token_hash !== sha256(controllerToken)) throw Error('hot_instance_mismatch');
  });
}
export async function activateRuntime(db: Sql, schema: string, instanceId: string, controllerToken: string, mode: RuntimeOwner['mode'], seconds = 300, requireIdle = false): Promise<RuntimeOwner> {
  schemaName(schema); identity(instanceId); token(controllerToken); duration(seconds);
  if (!['native','docker'].includes(mode)) throw Error('hot_owner_invalid');
  try {
    return await db.begin(async tx => {
      await lock(tx, schema);
      const rows = await tx`update ${tx(schema)}.runtime_identity set mode=${mode}, generation=generation+1, paused=false,
        owner_until=clock_timestamp()+${seconds}*interval '1 second'
        where singleton and instance_id=${instanceId} and controller_token_hash=${sha256(controllerToken)}
        and (${!requireIdle} or paused or owner_until<=clock_timestamp() or owner_until is null) returning generation`;
      if (rows.length !== 1) throw Error('hot_control_denied');
      return { instanceId, mode, generation: String(rows[0].generation) };
    });
  } catch (error) {
    logEvent('control_rejected');
    throw safeError(error, 'hot_control_failed');
  }
}
export async function heartbeatRuntime(db: Sql, schema: string, owner: RuntimeOwner, controllerToken: string, seconds = 300): Promise<void> {
  schemaName(schema); ownerValid(owner); token(controllerToken); duration(seconds);
  await db.begin(async tx => {
    await lock(tx, schema);
    await active(tx, schema, owner);
    const rows = await tx`update ${tx(schema)}.runtime_identity set owner_until=clock_timestamp()+${seconds}*interval '1 second'
      where singleton and controller_token_hash=${sha256(controllerToken)} returning singleton`;
    if (rows.length !== 1) throw Error('hot_control_denied');
  });
}
export async function pauseRuntime(db: Sql, schema: string, owner: RuntimeOwner, controllerToken: string): Promise<void> {
  schemaName(schema); ownerValid(owner); token(controllerToken);
  await db.begin(async tx => {
    await lock(tx, schema);
    const rows = await tx`update ${tx(schema)}.runtime_identity set paused=true,generation=generation+1,owner_until=null
      where singleton and instance_id=${owner.instanceId} and generation=${owner.generation}
      and controller_token_hash=${sha256(controllerToken)} returning singleton`;
    if (rows.length !== 1) throw Error('hot_control_denied');
  });
}
export async function claimTask(db: Sql, schema: string, owner: RuntimeOwner, jobId: string, inputKey: string, workerId: string, leaseSeconds = 120): Promise<ClaimResult> {
  schemaName(schema); ownerValid(owner); identity(jobId); identity(workerId); duration(leaseSeconds);
  if (!/^[a-zA-Z0-9_.:\-]{1,160}$/.test(inputKey)) throw Error('hot_input_key_invalid');
  return db.begin(async tx => {
    await lock(tx, schema);
    await active(tx, schema, owner);
    await tx`insert into ${tx(schema)}.job_claims(input_key,job_id) values(${inputKey},${jobId}) on conflict do nothing`;
    const [row] = await tx`select *,lease_until>clock_timestamp() as live from ${tx(schema)}.job_claims where input_key=${inputKey} for update`;
    if (row.state === 'completed') { await active(tx, schema, owner); return { state: 'reused', result: row.result }; }
    if (row.state === 'running' && row.live && String(row.generation) === owner.generation) { await active(tx, schema, owner); return { state: 'busy' }; }
    if (row.state === 'running') {
      await tx`update ${tx(schema)}.job_attempts set finished_at=clock_timestamp(),
        outcome=${String(row.generation) === owner.generation ? 'expired' : 'superseded'}
        where input_key=${inputKey} and attempt=${row.attempt} and outcome='running'`;
    }
    const leaseToken = randomUUID();
    const attempt = row.attempt + 1;
    await tx`update ${tx(schema)}.job_claims set job_id=${jobId},attempt=${attempt},lease_token=${leaseToken},worker_id=${workerId},generation=${owner.generation},
      lease_until=clock_timestamp()+${leaseSeconds}*interval '1 second',state='running',result=null,completed_at=null where input_key=${inputKey}`;
    await tx`insert into ${tx(schema)}.job_attempts(input_key,attempt,job_id,worker_id,lease_token,generation)
      values(${inputKey},${attempt},${jobId},${workerId},${leaseToken},${owner.generation})`;
    await active(tx, schema, owner);
    return { state: 'claimed', claim: { inputKey, jobId, workerId, leaseToken, owner } };
  });
}
export async function commitClaim(db: Sql, schema: string, claim: Claim, result: postgres.JSONValue, commit: (tx: Tx) => Promise<void> = async () => {}): Promise<void> {
  schemaName(schema); ownerValid(claim.owner); identity(claim.jobId); identity(claim.leaseToken); identity(claim.workerId);
  if (Buffer.byteLength(JSON.stringify(result)) > 262144) throw Error('hot_result_limit');
  try {
    await db.begin(async tx => {
      await lock(tx, schema);
      await active(tx, schema, claim.owner);
      const rows = await tx`select attempt from ${tx(schema)}.job_claims where input_key=${claim.inputKey} and job_id=${claim.jobId}
        and lease_token=${claim.leaseToken} and worker_id=${claim.workerId} and generation=${claim.owner.generation}
        and state='running' and lease_until>clock_timestamp() for update`;
      if (rows.length !== 1) throw Error('hot_claim_stale');
      // Business output and the caller's pg-boss completion can share this transaction.
      await commit(tx);
      await active(tx, schema, claim.owner);
      const accepted = await tx`update ${tx(schema)}.job_claims set state='completed',result=${tx.json(result)},completed_at=clock_timestamp()
        where input_key=${claim.inputKey} and lease_token=${claim.leaseToken} and lease_until>clock_timestamp() returning input_key`;
      if (accepted.length !== 1) throw Error('hot_claim_stale');
      await tx`update ${tx(schema)}.job_attempts set outcome='completed',finished_at=clock_timestamp()
        where input_key=${claim.inputKey} and attempt=${rows[0].attempt}`;
    });
  } catch (error) {
    logEvent('claim_rejected');
    throw safeError(error, 'hot_commit_failed');
  }
}

export async function renewClaim(db: Sql, schema: string, claim: Claim, seconds = 120): Promise<void> {
  schemaName(schema); ownerValid(claim.owner); duration(seconds); identity(claim.leaseToken);
  await db.begin(async tx => {
    await lock(tx, schema);
    await active(tx, schema, claim.owner);
    const rows = await tx`update ${tx(schema)}.job_claims set lease_until=clock_timestamp()+${seconds}*interval '1 second'
      where input_key=${claim.inputKey} and job_id=${claim.jobId} and lease_token=${claim.leaseToken}
      and worker_id=${claim.workerId} and generation=${claim.owner.generation}
      and state='running' and lease_until>clock_timestamp() returning input_key`;
    if (rows.length !== 1) throw Error('hot_claim_stale');
  });
}

export async function failClaim(db: Sql, schema: string, claim: Claim, operation: (tx: Tx) => Promise<void>): Promise<void> {
  await withOwnerTransaction(db, schema, claim.owner, async tx => {
    const rows = await tx`update ${tx(schema)}.job_claims set state='failed'
      where input_key=${claim.inputKey} and job_id=${claim.jobId} and lease_token=${claim.leaseToken}
      and worker_id=${claim.workerId} and generation=${claim.owner.generation}
      and state='running' and lease_until>clock_timestamp() returning attempt`;
    if (rows.length !== 1) throw Error('hot_claim_stale');
    await operation(tx);
    const stillLive = await tx`select input_key from ${tx(schema)}.job_claims where input_key=${claim.inputKey}
      and job_id=${claim.jobId} and lease_token=${claim.leaseToken} and worker_id=${claim.workerId}
      and generation=${claim.owner.generation} and state='failed' and lease_until>clock_timestamp()`;
    if (stillLive.length !== 1) throw Error('hot_claim_stale');
    await tx`update ${tx(schema)}.job_attempts set outcome='failed',finished_at=clock_timestamp()
      where input_key=${claim.inputKey} and attempt=${rows[0].attempt}`;
  });
}
