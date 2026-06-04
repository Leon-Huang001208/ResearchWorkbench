# Stable Connector Ingestion Plan

## Goal

Make every enabled data source enter through the connector layer, then route by asset kind:

- Document/news/report sources go to `ingestion_queue` and are persisted by `knowledge_worker` through `KnowledgePipeline`.
- Market/structured sources go to market repositories through `MarketDataConnector`.
- Scheduler, backfill, and workers must be isolated, non-blocking, restartable, and able to clean stale processes.

## Initial Findings

- `core.connectors.base` already defines the intended unified lifecycle:
  `discover -> fetch -> save_raw -> parse -> normalize -> persist`.
- Several `data_sources` pointed at old adapters instead of connector wrappers:
  `cls`, `cnstock`, `cnstock_flash`, `zhiqiu_reports`, `zhiqiu_wechat`, `zhiqiu_transcript`.
- `CrawlOrchestrator` called the old `adapter.fetch(**kwargs)` path, so registered connector classes such as
  `CninfoDocumentConnector`, `CsindexMarketConnector`, and `SzseMarketConnector` are not used correctly.
- `knowledge_worker` runs `KnowledgePipeline`, but only saves extracted events. It does not save `document_v1`
  or `source_document`, so queue-processed documents are not fully persisted.
- Current `source_document` repository uses the wrong ORM attribute name (`metadata` instead of `doc_metadata`).
- Database table/column audit against PostgreSQL found no missing ORM tables or columns.
- PID/watchdog files can be stale; startup only checks whether a PID exists, not whether the command and heartbeat are valid.

## Completion Notes

This plan has been implemented. Enabled sources now register connector classes with explicit `connector_dataset` and `pipeline_kind`; `CrawlOrchestrator` runs connector-backed sources through `connector.run()`; document connectors enqueue per-document records; `KnowledgeWorker` persists `document_v1`, `source_document`, and events before completing queue items; startup scripts validate stale PID/watchdog state.

## Implementation Steps

1. Source registry alignment
   - Add explicit source kind/dataset metadata to `SourceSpec`.
   - Update all source registrations to point to connector classes.
   - Encode connector dataset names (`telegram`, `news`, `flash`, `announcements`, `report`, `meeting`, market datasets).

2. Connector runner service
   - Add a small service that loads `ConnectorRegistry`, gets the connector for a source, and calls `connector.run(dataset, **params)`.
   - Translate scheduler windows into connector params.
   - Record `crawl_run_v1` and cursor updates from `IngestionResult`.
   - Keep old `CrawlOrchestrator` behavior only as a compatibility fallback for non-connector sources.

3. Document connector persistence
   - Change document connector persistence to enqueue one queue item per original document/envelope when available.
   - Preserve title, source id, URL, published time, raw URI, content hash, and source metadata.
   - Keep dedup by stable document id/content hash.

4. Knowledge worker persistence
   - Fix `DocumentRepositoryImpl` to use `doc_metadata`.
   - Before marking a queue item completed, save:
     - `document_v1`
     - `source_document`
     - extracted events/entities supported by the current repositories
   - Make source/doc type mapping cover all document sources: `cls`, `cnstock`, `cnstock_flash`, `cninfo`,
     `zhiqiu_reports`, `zhiqiu_wechat`, `zhiqiu_transcript`, and `zq`.

5. Scheduler isolation and backfill
   - Schedule only sources with `interval_minutes > 0`.
   - Route document sources through connector queue path and market sources through market connector persistence.
   - Run startup gap backfill in background with concurrency limits and source-level timeouts.
   - Ensure one failing source cannot block other scheduled jobs.

6. Process guard
   - Add shared PID/heartbeat validation helpers.
   - Startup cleans stale PID/watchdog files and terminates stale matching processes before launching.
   - Validate command line and heartbeat age, not just `kill -0`.
   - Keep restart with backoff and log every restart in `logs/`.

7. Verification
   - Unit tests for connector source registration, connector run routing, document queue persistence,
     knowledge worker document/source_document persistence, and process guard stale PID cleanup.
   - Runtime checks:
     - ORM schema audit: zero missing tables/columns.
     - Enabled sources have connector registrations.
     - Document source queue items can be processed into `document_v1` and `source_document`.
     - Market source connector persists to market tables or reports a clear unsupported dataset.
