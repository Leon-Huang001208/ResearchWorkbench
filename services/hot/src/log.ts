/** Supervisor captures stderr in the existing project logs/ stream.
 * Never accept publisher text, URLs, account names, DSNs or provider errors.
 */
export function logEvent(event: 'research_run_prepared' | 'research_run_advanced' | 'research_run_failed' | 'research_evidence_frozen' | 'research_evidence_failed' | 'research_original_failed' | 'brief_saved' | 'brief_frozen' | 'brief_failed' | 'model_controlled' | 'model_ready' | 'model_blocked' | 'migration_failed' | 'migration_ready' | 'ingest_failed' | 'page_committed' | 'database_check_failed' | 'control_rejected' | 'claim_rejected' | 'queue_failed' | 'job_completed' | 'job_failed' | 'worker_stopped' | 'worker_drained' | 'handler_late' | 'rpc_failed' | 'collection_failed' | 'collection_acquired' | 'source_configured' | 'model_reserved' | 'model_unknown' | 'model_receipt_saved' | 'event_saved' | 'channel_configured' | 'event_corrected' | 'processing_failed' | 'processing_applied' | 'channels_evaluated', count?: number, code?:string): void {
  console.error(JSON.stringify({ subsystem: 'hot', event,
    ...(count === undefined ? {} : { count }),...(code&&/^[A-Z0-9]{5}$/.test(code)?{code}:{}), time: new Date().toISOString() }));
}
