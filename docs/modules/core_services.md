# Module: core/services

## Responsibility

`core/services` contains AlphaFoundry's business orchestration logic.

Services coordinate:

- Contracts
- Repositories
- Crawlers
- Retrieval
- Reasoning
- Timing
- Signal generation
- Memory
- Reporting
- API/CLI use cases

---

## Design Rules

- Keep API route files thin.
- Put business logic in services.
- Use Pydantic contracts from `core/contracts`.
- Delegate persistence to repositories or storage utilities.
- Mock external dependencies in tests.
- Avoid UI-specific assumptions.
- Avoid direct network calls unless wrapped by adapters/gateways.
- Add or update tests when service behavior changes.

---

## Data Flow

Typical flow:

```text
app/api or app/cli
→ core/services
→ core/contracts
→ data_layer / knowledge_layer / reasoning / signal_lab / timing_engine / memory_learning
→ storage or repositories
→ response contract
```

---

## Files

### `core/services/dashboard_service.py`

Purpose:

- Aggregates dashboard data for the Web Workbench.
- Provides market status, recent news, signal summary, and research queue summary.

Related API:

- `app/api/routes/dashboard.py`

Related contracts:

- `core/contracts/dashboard.py`

Tests:

- Add or update dashboard service tests when dashboard fields or aggregation logic changes.

Update this section when:

- Dashboard output changes.
- Market summary logic changes.
- New dashboard panel is added.
- Dashboard API dependency changes.

---

### `core/services/ingest_service.py`

Purpose:

- Orchestrates document and event ingestion.
- All entry points (`ingest_file`, `ingest_text`, `ingest_envelope`) unified through `ingest_envelope()`.
- Short text (≤1000 chars): one-shot combined LLM extraction (assertions + events).
- Long text (>1000 chars): auto chunking → concurrent LLM extraction (ThreadPoolExecutor 16 workers) → deduplication.
- Coordinates quality gate, storage, and vector indexing.

Related files:

- `core/services/document_chunker.py`
- `core/services/document_classifier.py`
- `core/services/entity_extractor.py`
- `core/services/event_extractor.py`
- `core/services/raw_storage_service.py`
- `knowledge_layer/extraction/concurrent_extractor.py`
- `knowledge_layer/extraction/text_chunker.py`

Tests:

- Add ingestion service tests when pipeline order, input type, or extraction behavior changes.

Update this section when:

- Ingestion pipeline changes.
- New document type is added.
- Concurrency or chunking parameters change.
- Extraction behavior changes.
- Storage/indexing behavior changes.

---

### `core/services/asset_analysis_service.py`

Purpose:

- Generates `AssetAnalysisSnapshot` and `AssetAnalysisCard` for a given asset.
- Structured-first: queries `stock_daily_bar`, `stock_valuation`, `stock_financial_metric`, `stock_shareholder` tables.
- `_has_enough_structured_data()` guards against empty tables — if no price/valuation/financial/shareholder data found, falls back to coordinator.
- Falls back to `MultiSourceCoordinator` when structured tables have no data or fail.

Data source priority:

1. Structured SQL tables (fastest, via `MarketDataRepository`)
2. `MultiSourceCoordinator` with automatic degradation chain: iFinD → AKShare → Local

Dependencies:

- `data_layer/repositories/market_data_repository.py` — structured data access
- `data_layer/coordinator/multi_source_coordinator.py` — fallback data source

Update this section when:

- Snapshot assembly logic changes.
- Data source priority changes.
- Structured table query logic changes.
- Fallback behavior changes.

---

### `core/services/market_data_ingestion_service.py`

Purpose:

- Orchestrates ETL pipeline for market data: crawler → normalizer → structured SQL tables → ETL run tracking.
- `ingest_stock_master(limit)`: fetch stock list from AKShare, normalize, upsert to `stock_master` table.
- `ingest_daily_bars(symbols, start_date, end_date)`: fetch daily bars, normalize, upsert to `stock_daily_bar` table.

Related files:

- `data_layer/normalizers/akshare_market.py`
- `data_layer/repositories/market_data_repository.py`
- `data_layer/repositories/etl_run_repository.py`
- `data_layer/adapters/akshare_adapter.py`

Related API:

- `app/api/routes/market_data.py`

Tests:

- Add ingestion service tests when ETL pipeline order, input type, or failure recovery behavior changes.

Update this section when:

- ETL steps change.
- Normalizer adapter changes.
- New ingestion target is added.
- Failure/retry behavior changes.

---

### `core/services/crawler_ingestion_bridge.py`

Purpose:

- Bridges crawler output to the ingestion queue.
- Converts crawler results into `DocumentEnvelope` → `EnqueueRequest` → ingestion queue items.
- Supports `submit_crawled_item()` for single items and `submit_batch()` for batch processing.
- Infers priority by source type (e.g., CLS news = high priority).

Related files:

- `core/services/ingestion_queue_service.py`
- `core/contracts/documents_v1.py`
- `core/contracts/ingestion.py`

Tests:

- `tests/unit/core/services/test_crawler_ingestion_bridge.py`

Update this section when:

- Bridge conversion logic changes.
- New source types are added.
- Priority inference rules change.

---

### `core/services/system_event_bus.py`

Purpose:

- System-wide event bus for SSE (Server-Sent Events) real-time push.
- Tracks worker heartbeats for health monitoring.
- Implements pub/sub pattern with `asyncio.Queue`.
- Maintains a sliding window of the last 500 events.
- Supports optional JSONL file persistence (`.data/event_log.jsonl`) with automatic replay on restart.
- `get_events_after(after_id)` returns events after the matched ID for SSE reconnection replay.

Key API:

- `event_bus.publish(event_type, payload)` — publish an event to all subscribers.
- `event_bus.subscribe()` — create a subscriber queue.
- `event_bus.get_events_after(after_id)` — get events after a given event ID for reconnection replay.
- `event_bus.record_worker_heartbeat(worker_name)` — record worker heartbeat.
- `event_bus.get_worker_heartbeats()` — get all worker heartbeat timestamps.

Related files:

- `app/api/routes/realtime.py`
- `app/api/routes/system.py`
- `workers/knowledge_worker.py`

Tests:

- `tests/unit/core/services/test_system_event_bus.py`

Update this section when:

- Event types change.
- Subscriber model changes.
- Heartbeat tracking changes.
- Event retention policy changes or persistence format changes.

---

## Common Pitfalls

- Do not put API-specific response formatting inside services.
- Do not bypass contracts.
- Do not make live external calls in unit tests.
- Do not update service behavior without updating tests and docs.

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/core_services.md`
- `docs/FILE_GUIDE.md`
- `docs/ARCHITECTURE.md` if flow or boundary changes
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`