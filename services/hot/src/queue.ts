/** One pg-boss backend, using the existing pool and transactions for business commits. */
import type postgres from 'postgres';
import { PgBoss } from 'pg-boss';
import { randomUUID } from 'node:crypto';
import { schemaName } from './config.ts';
import type { HotConfig } from './config.ts';
import { claimTask, commitClaim, failClaim, withOwnerTransaction, type RuntimeOwner, type Tx, type Claim } from './control.ts';
import { logEvent } from './log.ts';

type Sql = ReturnType<typeof postgres>;
type IDatabase = NonNullable<NonNullable<Parameters<PgBoss['complete']>[3]>['db']>;
export const QUEUES = ['hot.collect','hot.parse','hot.process','hot.brief','hot.research'] as const;
export type QueueName = typeof QUEUES[number];
interface Payload { inputKey: string; payload: postgres.JSONValue }
function queueName(name: QueueName) { if (!QUEUES.includes(name)) throw Error('hot_queue_invalid'); }
function inputKey(value: string) { if (!/^[a-zA-Z0-9_.:\-]{1,160}$/.test(value)) throw Error('hot_input_key_invalid'); }

export function transactionAdapter(db: Sql | Tx): IDatabase {
  return { async executeSql(text, values) {
    // SQL text is generated exclusively by the version-locked pg-boss library.
    // node-postgres treats an optional undefined SQL parameter as NULL.
    // Pre-serialized strings must travel as text rather than be JSON-stringified again.
    const parameters = values?.map(value => {
      if (value === undefined) return null;
      if (typeof value === 'string') {
        try { JSON.parse(value); return db.typed(value, 25); } catch { /* UUID/text keeps server inference. */ }
      }
      return value;
    });
    if ('begin' in db) {
      // pg-boss bootstrap scripts own BEGIN/COMMIT; never run those on a shared pool connection.
      const connection = await db.reserve();
      try {
        const rows = await connection.unsafe(text, parameters as Parameters<Sql['unsafe']>[1]);
        const last = Array.isArray(rows[0]) ? rows.at(-1) as unknown as unknown[] : rows;
        return { rows: [...last!] };
      } catch (error) {
        try { await connection.unsafe('ROLLBACK'); } catch { logEvent('queue_failed'); }
        throw error;
      } finally { await connection.release(); }
    }
    // pg-boss monitoring wraps its statements in BEGIN/COMMIT. Here the Host already
    // owns the enclosing transaction, so retain its SQL while removing that exact envelope.
    const envelope = /^\s*BEGIN\s*;([\s\S]*)\bCOMMIT\s*;?\s*$/i.exec(text);
    const statement = envelope ? envelope[1] : text;
    if (/(?:^|;)\s*(?:BEGIN|COMMIT|ROLLBACK)\b/im.test(statement)) throw Error('hot_nested_transaction_denied');
    const rows = await db.unsafe(statement, parameters as Parameters<Sql['unsafe']>[1]);
    const last = Array.isArray(rows[0]) ? rows.at(-1) as unknown as unknown[] : rows;
    return { rows: [...last!] };
  } };
}
export async function openQueue(db: Sql | Tx, schema: string, provision = false, worker?: HotConfig['worker']): Promise<PgBoss> {
  schemaName(schema);
  const retries = worker?.maxRetries ?? 3;
  const leaseSeconds = worker?.leaseSeconds ?? 120;
  if (!Number.isInteger(retries) || retries < 0 || retries > 10 || !Number.isInteger(leaseSeconds) || leaseSeconds < 10 || leaseSeconds > 1800) throw Error('hot_queue_config_invalid');
  // Both business and queue tables stay in the user's explicitly selected schema.
  const queueSchema = schema;
  if (provision) {
    if (!('begin' in db)) throw Error('hot_queue_provision_transaction_denied');
    const [permission] = await db`select has_schema_privilege(current_user,${schema},'CREATE') as allowed`;
    if (!permission.allowed) throw Error('hot_queue_provision_denied');
    await db.begin(async tx => {
      await tx`select pg_advisory_xact_lock(hashtextextended(${queueSchema},231501))`;
      const identity = await tx`select instance_id from ${tx(schema)}.runtime_identity where singleton`;
      if (identity.length !== 1) throw Error('hot_queue_identity_missing');
      const binding = await tx`select * from ${tx(schema)}.queue_binding where singleton`;
      if (binding.length && (binding[0].schema_name !== queueSchema || binding[0].instance_id !== identity[0].instance_id || binding[0].engine !== 'pg-boss@12.34.0')) throw Error('hot_queue_binding_mismatch');
      if (!binding.length) {
        const [existing] = await tx`select to_regclass(${`${queueSchema}.version`}) as queue_version`;
        if (existing.queue_version) throw Error('hot_queue_schema_not_empty');
        await tx`insert into ${tx(schema)}.queue_binding(schema_name,instance_id,engine)
          values(${queueSchema},${identity[0].instance_id},'pg-boss@12.34.0')`;
      }
    });
  } else {
    const bound = await db`select b.singleton from ${db(schema)}.queue_binding b join ${db(schema)}.runtime_identity r on r.singleton=b.singleton
      where b.singleton and b.provisioned and b.schema_name=${queueSchema} and b.instance_id=r.instance_id and b.engine='pg-boss@12.34.0'`;
    if (bound.length !== 1) throw Error('hot_queue_not_provisioned');
  }
  const boss = new PgBoss({ db: transactionAdapter(db), schema: queueSchema,
    migrate: provision, createSchema: false, supervise: false, schedule: false,
    persistWarnings: false, persistQueueStats: false, reindex: false });
  boss.on('error', () => logEvent('queue_failed'));
  try {
    await boss.start();
    if (provision) {
      for (const name of QUEUES) {
        const queueOptions = { policy: 'short' as const,
          // Paid processing and research admission never retry an unknown dispatch automatically.
          retryLimit: ['hot.process','hot.research'].includes(name) ? 0 : retries,
          retryDelay: 10, retryBackoff: true, expireInSeconds: Math.max(300,leaseSeconds + 30) };
        await boss.createQueue(name, queueOptions);
        if ((await boss.getQueue(name))?.policy !== 'short') throw Error('hot_queue_policy_unsupported');
        const { policy: _policy, ...updates } = queueOptions;
        await boss.updateQueue(name, updates);
      }
      await db`update ${db(schema)}.queue_binding set provisioned=true where singleton`;
    } else {
      for (const name of QUEUES) if (!await boss.getQueue(name)) throw Error('hot_queue_not_provisioned');
    }
    return boss;
  } catch (error) {
    try { await boss.stop(); } catch { logEvent('queue_failed'); }
    if (error instanceof Error && /^hot_[a-z_]+$/.test(error.message)) throw error;
    const code = error && typeof error === 'object' && 'code' in error ? error.code : null;
    const known = ['UNDEFINED_VALUE','42601','42P01','42P06','42501','28P01','ECONNREFUSED'].includes(String(code)) ? String(code) : 'unknown';
    throw Error(`hot_queue_unavailable_${known}`);
  }
}
export async function enqueue(boss: PgBoss, db: Sql, schema: string, owner: RuntimeOwner, name: QueueName, key: string, payload: postgres.JSONValue): Promise<string | null> {
  return withOwnerTransaction(db,schema,owner,tx=>enqueueTransaction(boss,tx,name,key,payload));
}
export async function enqueueTransaction(boss:PgBoss,tx:Tx,name:QueueName,key:string,payload:postgres.JSONValue):Promise<string|null>{
  queueName(name); inputKey(key);
  if (`${name}:${key}`.length > 160) throw Error('hot_input_key_invalid');
  if (Buffer.byteLength(JSON.stringify(payload)) > 262144) throw Error('hot_payload_limit');
  return boss.send(name, { inputKey: `${name}:${key}`, payload },
    { singletonKey: key, db: transactionAdapter(tx) });
}

export async function superviseOwner(db: Sql, schema: string, owner: RuntimeOwner, name?: QueueName): Promise<void> {
  if (name) queueName(name);
  await withOwnerTransaction(db, schema, owner, async tx => {
    const supervisor = await openQueue(tx, schema);
    try { await supervisor.supervise(name, { reindex: false }); }
    finally { await supervisor.stop(); }
  });
}

export interface JobOutput { result: postgres.JSONValue; commit?: (tx: Tx) => Promise<void> }
export async function waitForHandler(handler: (signal: AbortSignal) => Promise<JobOutput>, signal: AbortSignal): Promise<JobOutput> {
  return new Promise((resolve, reject) => {
    let finished = false;
    const abort = () => {
      if (finished) return;
      finished = true;
      reject(Error('hot_handler_cancelled'));
    };
    if (signal.aborted) { abort(); return; }
    signal.addEventListener('abort', abort, { once: true });
    Promise.resolve().then(() => handler(signal)).then(output => {
      if (finished) { logEvent('handler_late'); return; }
      finished = true;
      signal.removeEventListener('abort', abort);
      resolve(output);
    }, error => {
      if (finished) { logEvent('handler_late'); return; }
      finished = true;
      signal.removeEventListener('abort', abort);
      reject(error);
    });
  });
}
export async function processOne(boss: PgBoss, db: Sql, schema: string, owner: RuntimeOwner, name: QueueName,
  handler: (payload: postgres.JSONValue, signal: AbortSignal, claim:Claim) => Promise<JobOutput>, workerId = randomUUID(), leaseSeconds = 120,
  signal?: AbortSignal): Promise<'idle' | 'busy' | 'completed' | 'reused' | 'failed'> {
  queueName(name);
  if (signal?.aborted) return 'idle';
  const jobs = await withOwnerTransaction(db, schema, owner, tx => boss.fetch<Payload>(name, { batchSize: 1, db: transactionAdapter(tx) }));
  if (!jobs.length) return 'idle';
  const job = jobs[0];
  if (!job.data || typeof job.data !== 'object' || typeof job.data.inputKey !== 'string' || !('payload' in job.data)
    || !/^[a-zA-Z0-9_.:\-]{1,160}$/.test(job.data.inputKey) || !job.data.inputKey.startsWith(`${name}:`)
    || Object.keys(job.data).some(key => !['inputKey','payload'].includes(key))) {
    await withOwnerTransaction(db, schema, owner, tx => boss.fail(name, job.id, { code: 'hot_payload_invalid' }, { db: transactionAdapter(tx) }));
    return 'failed';
  }
  const acquired = await claimTask(db, schema, owner, job.id, job.data.inputKey, workerId, leaseSeconds);
  const complete = async (tx: Tx, result: postgres.JSONValue) => {
    await boss.complete(name, job.id, { result }, { db: transactionAdapter(tx) });
    const rows = await boss.findJobs(name, { id: job.id, db: transactionAdapter(tx) });
    if (rows.length !== 1 || rows[0].state !== 'completed') throw Error('hot_queue_ack_stale');
  };
  if (acquired.state === 'reused') {
    await withOwnerTransaction(db, schema, owner, tx => complete(tx, acquired.result));
    return 'reused';
  }
  if (acquired.state === 'busy') {
    await withOwnerTransaction(db, schema, owner, tx => boss.fail(name, job.id, { code: 'hot_task_busy' }, { db: transactionAdapter(tx) }));
    return 'busy';
  }
  try {
    const deadline = AbortSignal.timeout(Math.max(1, leaseSeconds - 1) * 1000);
    const handlerSignal = signal ? AbortSignal.any([signal,deadline]) : deadline;
    const output = await waitForHandler(activeSignal => handler(job.data.payload,activeSignal,acquired.claim), handlerSignal);
    await commitClaim(db, schema, acquired.claim, output.result, async tx => {
      if (output.commit) await output.commit(tx);
      await complete(tx, output.result);
    });
    logEvent('job_completed');
    return 'completed';
  } catch (error) {
    // An obsolete executor cannot acknowledge/fail the current executor's job.
    if (error instanceof Error && ['hot_owner_stale','hot_claim_stale'].includes(error.message)) throw error;
    await failClaim(db, schema, acquired.claim, async tx => {
      await boss.fail(name, job.id, { code: 'hot_handler_failed' }, { db: transactionAdapter(tx) });
    });
    logEvent('job_failed');
    return 'failed';
  }
}
