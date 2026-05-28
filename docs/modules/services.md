# Module: services

## Responsibility

`services` contains AlphaFoundry's business orchestration logic.

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
- Use `core.source_registry` for data source metadata — never hardcode source lists or if/elif adapter dispatch.

---

## Source Registry (`core/source_registry.py`)

`SourceSpec` frozen dataclass 是数据源的唯一自描述入口。所有下游模块（调度器、编排器、分类器、仪表盘、PDF 转换）通过 `get()` / `get_all()` / `get_enabled()` 动态读取。`data_sources/` 目录下的每个 `.py` 文件在 import 时调用 `register()`。

添加新爬取源 = 在 `data_sources/` 下新建一个 `.py` 文件，无需修改任何其他代码。
- Add or update tests when service behavior changes.

---

## Data Flow

Typical flow:

```text
app/api or app/cli
→ services
→ core/contracts
→ data_layer / knowledge_layer / reasoning / signal_lab / timing_engine / memory_learning
→ storage or repositories
→ response contract
```

---

## Files

### `services/crawl_orchestrator.py`

Purpose:

- Orchestrates multi-source crawling: fetch → normalize → dedup → store → enqueue.
- `_enqueue_items(source_type, items)` — static method that converts raw items to `DocumentEnvelope` and submits to IngestionBridge via batch.
- `_sync_dedup_state(source_type)` — syncs file-based crawler dedup state against database, removing orphan entries for documents deleted from DB.
- `deep_backfill_step()` — backfills historical documents and enqueues them for LLM extraction.
- `crawl_source()` step ordering: resolve spec → fetch → normalize → sync dedup → store → enqueue → mark complete.

Related files:

- `services/crawl_scheduler.py`
- `services/crawler_ingestion_bridge.py`
- `data_layer/crawlers/cls/utils/deduplication.py`
- `core/source_registry.py`

Update this section when:

- Crawl orchestration logic changes.
- New crawl step is added.
- Dedup sync behavior changes.
- Enqueue batching changes.

---

### `services/crawl_scheduler.py`

Purpose:

- Schedules periodic crawl and PDF conversion jobs via APScheduler.
- Crawl jobs: `_run_crawl_job()` loops over `source_registry.get_enabled()` sources with staggered intervals.
- PDF conversion job: `_run_pdf_conversion_job()` runs every 5 minutes, calls `PDFConversionService.convert_pending(limit=5)` + `retry_failed(limit=3)`.

Related files:

- `services/crawl_orchestrator.py`
- `services/pdf_conversion_service.py`
- `core/source_registry.py`

Update this section when:

- Job scheduling intervals change.
- New scheduled jobs are added.
- PDF conversion batch size or retry limits change.

---

### `services/pdf_conversion_service.py`

Purpose:

- Orchestrates PDF-to-Markdown/text conversion with multi-strategy fallback (MinerU → MarkItDown → RawText).
- `convert_pdf(pdf_id)` — converts a single PDF, persists results to disk (`data/markdown/`, `data/raw_text/`), creates `DocumentV1` + chunks.
- `convert_pending(limit)` — queries `PDFArtifactV1DB` with `parse_status='pending'`, converts up to `limit` PDFs.
- `retry_failed(limit)` — retries conversions where `parse_status != 'completed'`.
- Automatic `DocumentV1` creation with content hash dedup (can be disabled via `create_document=False`).

Related files:

- `ingestion/converters/mineru.py`
- `ingestion/converters/markitdown.py`
- `ingestion/converters/raw_text.py`
- `ingestion/converters/persistence.py`
- `data_layer/repositories/pdf_artifact_repository.py`
- `data_layer/repositories/documents_v1.py`

Update this section when:

- Conversion strategy priority changes.
- File persistence paths change.
- Document creation logic changes.

---

### `services/dashboard_service.py`

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

### `services/ingest_service.py`

Purpose:

- Orchestrates document and event ingestion.
- All entry points (`ingest_file`, `ingest_text`, `ingest_envelope`) unified through `ingest_envelope()`.
- Short text (≤1000 chars): one-shot combined LLM extraction (assertions + events).
- Long text (>1000 chars): auto chunking → concurrent LLM extraction (ThreadPoolExecutor 16 workers) → deduplication.
- Coordinates quality gate, storage, and vector indexing.

Related files:

- `services/document_chunker.py`
- `services/document_classifier.py`
- `services/entity_extractor.py`
- `services/event_extractor.py`
- `services/raw_storage_service.py`
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

### `services/asset_analysis_service.py`

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

### `services/market_data_ingestion_service.py`

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

### `services/crawler_ingestion_bridge.py`

Purpose:

- Bridges crawler output to the ingestion queue.
- Converts crawler results into `DocumentEnvelope` → `EnqueueRequest` → ingestion queue items.
- Supports `submit_crawled_item()` for single items and `submit_batch()` for batch processing.
- Infers priority by source type (e.g., CLS news = high priority).

Related files:

- `services/ingestion_queue_service.py`
- `core/contracts/documents_v1.py`
- `core/contracts/ingestion.py`

Tests:

- `tests/unit/services/test_crawler_ingestion_bridge.py`

Update this section when:

- Bridge conversion logic changes.
- New source types are added.
- Priority inference rules change.

---

### `services/system_event_bus.py`

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

- `tests/unit/services/test_system_event_bus.py`

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