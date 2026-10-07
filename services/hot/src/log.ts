/** Supervisor captures stderr in the existing project logs/ stream.
 * Never accept publisher text, URLs, account names, DSNs or provider errors.
 */
export function logEvent(event: 'migration_failed' | 'migration_ready' | 'ingest_failed' | 'page_committed' | 'database_check_failed' | 'control_rejected' | 'claim_rejected' | 'queue_failed' | 'job_completed' | 'job_failed' | 'worker_stopped' | 'worker_drained' | 'handler_late' | 'rpc_failed', count?: number): void {
  console.error(JSON.stringify({ subsystem: 'hot', event,
    ...(count === undefined ? {} : { count }), time: new Date().toISOString() }));
}
