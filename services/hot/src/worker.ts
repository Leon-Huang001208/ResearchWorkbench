/** Finite-concurrency worker loop. Host owns configuration, credentials and owner heartbeats. */
import type postgres from 'postgres';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import type { PgBoss } from 'pg-boss';
import type { HotConfig } from './config.ts';
import { assertNodeRuntime } from './config.ts';
import type { RuntimeOwner } from './control.ts';
import { processOne, superviseOwner, type QueueName, type JobOutput } from './queue.ts';
import { logEvent } from './log.ts';

type Sql = ReturnType<typeof postgres>;
type Handler = (payload: postgres.JSONValue, signal: AbortSignal) => Promise<JobOutput>;
export interface WorkerOptions {
  db: Sql; controllerDb: Sql; boss: PgBoss; schema: string; owner: RuntimeOwner;
  config: HotConfig; handlers: Partial<Record<QueueName, Handler>>; signal: AbortSignal;
  heartbeat: () => Promise<void>;
}
async function pause(signal: AbortSignal, milliseconds: number) {
  try { await delay(milliseconds, undefined, { signal }); }
  catch (error) { if (!signal.aborted) throw error; }
}
export async function runWorker(options: WorkerOptions): Promise<void> {
  if (!options.config.enabled || options.signal.aborted) return;
  assertNodeRuntime();
  const shutdown = new AbortController();
  const signal = AbortSignal.any([options.signal,shutdown.signal]);
  const names = Object.keys(options.handlers) as QueueName[];
  if (names.length === 0) throw Error('hot_worker_no_handlers');
  const supervisor = async () => {
    while (!signal.aborted) {
      await options.heartbeat();
      await superviseOwner(options.controllerDb, options.schema, options.owner);
      await pause(signal, 10_000);
    }
  };
  const lane = async () => {
    const workerId = randomUUID();
    while (!signal.aborted) {
      let progressed = false;
      for (const name of names) {
        if (signal.aborted) break;
        const state = await processOne(options.boss, options.db, options.schema, options.owner, name,
          options.handlers[name]!, workerId, options.config.worker.leaseSeconds, signal);
        progressed ||= state !== 'idle';
      }
      if (!progressed) await pause(signal, 250);
    }
  };
  const guarded = async (operation: () => Promise<void>) => {
    try { await operation(); }
    catch {
      shutdown.abort();
      logEvent('worker_stopped');
      throw Error('hot_worker_stopped');
    }
  };
  // A failing lane cancels and joins every sibling rather than leaving orphan processing.
  const results = await Promise.allSettled([guarded(supervisor),
    ...Array.from({ length: options.config.worker.concurrency }, () => guarded(lane))]);
  if (results.some(result => result.status === 'rejected')) throw Error('hot_worker_stopped');
  logEvent('worker_drained');
}
