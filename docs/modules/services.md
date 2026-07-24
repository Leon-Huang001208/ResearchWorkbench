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

`SourceSpec` frozen dataclass 是数据源的唯一自描述入口。所有下游模块（调度器、编排器、分类器、仪表盘、PDF 转换）通过 `get()` / `get_all()` / `get_enabled()` 动态读取。`data_sources/` 目录下的每个 `.py` 文件在 import 时调用 `register()`。新数据源使用 `connector_class` 指向 `BaseConnector` 子类；`adapter_class` 仅为历史兼容别名。

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

- Orchestrates multi-source crawling through a connector-first path. Connector-backed sources run `connector.run(spec.connector_dataset, **params)`; document connectors enqueue per-document records for `KnowledgeWorker`, while market connectors persist through market repositories. The older adapter fetch path remains only as a compatibility fallback for non-connector sources.
- `_enqueue_items(source_type, items)` — static method that converts raw items to `DocumentEnvelope` and submits to IngestionBridge via batch.
- `_sync_dedup_state(source_type)` — syncs file-based crawler dedup state against database, removing orphan entries for documents deleted from DB.
- `deep_backfill_step()` — backfills historical documents and enqueues them for LLM extraction.
- `crawl_source()` step ordering for current sources: resolve `SourceSpec` → run connector → record `crawl_run_v1`/cursor → let document or market connector persist according to `pipeline_kind`.

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

- Schedules periodic crawl, PDF conversion, and closed loop jobs via APScheduler.
- Crawl jobs: `_run_crawl_job()` loops over `source_registry.get_enabled()` sources with staggered intervals.
- Gap backfill: `check_and_backfill_gap()` detects missed crawl periods and backfills. Blocking `orchestrator.backfill_source()` calls are delegated to thread executor via `await loop.run_in_executor()` so that per-source timeouts (via `asyncio.wait_for`) can fire instead of being blocked by sync I/O.
- PDF conversion job: `_run_pdf_conversion_job()` runs every 5 minutes, calls `PDFConversionService.convert_pending(limit=5)` + `retry_failed(limit=3)`.
- Closed loop job: `_run_closed_loop_job()` runs every 10 minutes with 60s jitter, creates `ClosedLoopService` and calls `run_full_loop()`.
- All jobs wrapped in try/except to ensure single job failure does not affect scheduler.

Related files:

- `services/crawl_orchestrator.py`
- `services/pdf_conversion_service.py`
- `workers/crawl_scheduler_worker.py` — standalone process, manages startup backfill with per-source and global timeouts
- `core/source_registry.py`

Update this section when:

- Job scheduling intervals change.
- New scheduled jobs are added.
- PDF conversion batch size or retry limits change.
- Gap backfill timeout or concurrency model changes.

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
- Price-bar enrichment first gives Cjpy/Tinysoft a short window for same-day bars, then tries Wind Excel WSS realtime quotes, then falls back to `MultiSourceCoordinator`; coordinator may return recent cache immediately when only the latest calendar tail is missing, so asset pages are not blocked by live backfill.
- `generate_analysis_card(..., time_range=...)` supports Wind-style K-line windows (`1M`/`3M`/`6M`/`1Y`/`2Y`/`3Y`/`5Y`/`ALL`) and passes the resolved date window into Cjpy/Wind/coordinator price-bar enrichment.

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

### `services/fund_intelligence_service.py`

Purpose:

- Builds Fund Intelligence views from repository data.
- `get_fund_detail(symbol)` assembles fund master data, latest NAV, managers, latest holdings, and calculated return/risk metrics.
- `get_fund_exposure(symbol)` aggregates latest disclosed holdings into single-fund stock, industry, and theme exposure.
- `calculate_portfolio_exposure(positions)` normalizes fund weights and calculates weighted portfolio exposure across funds.

Related API:

- `app/api/routes/funds.py`

Related repository:

- `data_layer/repositories/fund_repository.py`

Related contracts:

- `core/contracts/funds.py`

Update this section when:

- Fund performance metric formulas change.
- Exposure aggregation dimensions change.
- Fund portfolio weighting behavior changes.

---

### `services/fund_data_ingestion_service.py`

Purpose:

- Ingest local fund data rows or UTF-8 CSV files into the Fund Intelligence repository.
- Supports `master`, `nav`, `holdings`, and `managers` datasets.
- Normalizes ISO date strings and numeric fields into `core.contracts.funds` models before persistence.
- Optionally records ETL lifecycle through `ETLRunRepository`-compatible `start` / `finish` / `fail` methods.

Related repository:

- `data_layer/repositories/fund_repository.py`

Related contracts:

- `core/contracts/funds.py`

Update this section when:

- Supported fund ingestion datasets change.
- CSV column contracts change.
- Wind/AKShare adapters begin feeding this service.

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

### `services/asset_search_index_service.py`

Purpose:

- Builds and queries a unified asset candidate search index for the asset analysis page.
- Supports match types: exact code, code prefix, pinyin abbreviation (exact/prefix/contains), name contains.
- Candidate sources in priority order:
  1. StockMasterDB (A-share equities)
  2. Entity table (vendor-mapped assets)
  3. AKShare `fund_etf_spot_em()` (ETF列表，24h模块级缓存)
  4. Seeded assets (贵州茅台, 绿色煤炭)
- Scoring: exact code match (1000) > code prefix (900) > pinyin exact (850) > pinyin prefix (800) > name contains (700) > code contains (600) > pinyin contains (500)
- Asset type ranking for sort: equity (0) > company (1) > index (2) > asset (3) > other (9)

Related files:

- `core/contracts/assets.py`
- `data_layer/repositories/models.py` (StockMasterDB, Entity)
- `data_layer/normalizers/symbol.py`
- `tests/unit/test_asset_search_index_service.py`

Update this section when:

- New candidate source is added.
- Scoring or ranking rules change.
- ETF cache TTL or source changes.

---

### `services/crawler_ingestion_bridge.py`

Purpose:

- Bridges crawler output to the ingestion queue.
- Converts crawler results into `DocumentEnvelope` → `EnqueueRequest` → ingestion queue items.
- Supports `submit_crawled_item()` for single items and `submit_batch()` for batch processing.
- Infers priority by source type (e.g., ZQ reports are higher priority than default news).

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

### `services/pipeline_monitor.py`

Purpose:

- Lightweight in-memory singleton tracking 9 pipeline stages with thread-safe activity logging (max 200 items).
- Aggregates DB stats from `DocumentV1DB`, `CanonicalEvent`, `AlphaSignalDB`, `SignalOutcomeDB` for ingestion, knowledge, signal, backtest, and learning stages.
- Records events from `SystemEventBus` and provides `get_full_status()` for API consumption.
- `record_event(event_type, payload)` — thread-safe append to activity log with automatic stage mapping.
- `get_full_status()` — returns stages (with DB counts), closed_loop status, and recent activity (20 items).
- `get_recent_activity(limit)` — returns most recent activity items in reverse chronological order.
- `_query_db_stats()` — queries DB for cumulative counts with Asia/Shanghai timezone alignment.

Related files:

- `services/system_event_bus.py`
- `services/closed_loop_service.py`
- `services/pipeline_service.py`
- `app/api/routes/pipeline.py`
- `app/web/static/js/pipeline-monitor.js`

Update this section when:

- New pipeline stage is added.
- DB stats query logic changes.
- Activity retention limit changes.
- Event-to-stage mapping changes.

---

### `services/pipeline_service.py`

Purpose:

- Orchestrates the 7-layer research pipeline: event → signal → reasoning → agent swarm → timing evaluation.
- Each step publishes events via `SystemEventBus` and `PipelineMonitor` for real-time observability.
- `_analyze_propagation()` — runs `PropagationAnalyzer` for industry chain impact propagation.
- `_run_reasoning()` — runs `ReasoningEngine` with scenario generation.
- `_run_agent_swarm()` — runs `AgentOrchestrator` multi-agent debate.
- `_evaluate_timing()` — runs `MetaTimingEngine` for market timing evaluation.

Related files:

- `services/closed_loop_service.py`
- `services/pipeline_monitor.py`
- `reasoning/`
- `cognitive_agents/`
- `timing_engine/`

Update this section when:

- Pipeline step order changes.
- New pipeline step is added.
- Event publishing at any step changes.

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
