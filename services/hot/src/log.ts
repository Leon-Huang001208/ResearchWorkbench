/** Supervisor captures stderr in the existing project logs/ stream.
 * Never accept publisher text, URLs, account names, DSNs or provider errors.
 */
export function logEvent(event: 'migration_failed' | 'migration_ready' | 'ingest_failed' | 'page_committed', count?: number): void {
  console.error(JSON.stringify({ subsystem: 'hot', event,
    ...(count === undefined ? {} : { count }), time: new Date().toISOString() }));
}
