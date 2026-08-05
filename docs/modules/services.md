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

### `services/resource_monitor_runtime.py`、`resource_task_registry.py` 与 `resource_monitor_alert_service.py`

Purpose:

- `ResourceTaskRegistry` 为 AlphaFoundry 的抓取、PDF、知识处理、Wind 和报告任务记录受控运行上下文，并以每 PID 原子 JSON 快照供 API 进程读取。
- `ResourceMonitoringService` 只合并 API 进程树、既有调度器/知识 Worker PID 和这些任务快照；同时读取整机 CPU 容量与内存汇总。API 内任务标记为共享资源估算，独立 Worker 标记为精确进程资源。
- `ResourceMonitorRuntime` 在数据库就绪的 API 生命周期内以单一可停止线程每分钟采集一次快照；同一数据库会话内写入主机容量历史并评估资源事件。采样、历史或告警失败只记录安全的结构化异常类型，下一周期继续运行。
- `ResourceHostHistoryService.list_history(hours=24)` 以当前 UTC 时间减去请求窗口传入仓储 `since` 过滤；它将仓储读取失败封装为不含原始错误内容的 `ResourceHostHistoryUnavailable`。API 将它明确映射为主机历史不可用，空点位仍是正常的空历史响应。运行时只调用写入路径，不受该读取信号影响。
- `ResourceAlertState` 在运行时的连续采样周期之间共享压力与恢复计数；每周期创建的 `ResourceMonitorAlertService` 显式消费该状态，因此持续压力仍在第三个样本触发现有事件规则。
- `ResourceMonitorAlertService` 将任务失败、受控进程缺失、采样失败和持续资源压力以 `source_scope=alphafoundry` 保存为既有 Monitoring 告警/事件状态机中的 `resource_monitoring` 事件；另以 `source_scope=host_capacity` 评估整机 CPU（85%/95%）和可用内存（15%/8%）容量压力。两类容量均需连续三个有限且处于 0–100 的样本触发或恢复；无效字段会中断该指标的连续计数。主机事件通过仓储的确定性周期 ID 和 savepoint 冲突恢复，确保并发周期至多一个未解决事件；warning 升为 critical 时调用条件更新，仅更新详情且保留确认/解决状态。

Safety boundary:

- 不枚举全系统进程；主机汇总仅调用 `psutil.cpu_percent(interval=None)`、`psutil.cpu_count(logical=True)` 和 `psutil.virtual_memory()`，不保存命令参数、请求内容或异常原文。
- 首个非阻塞主机 CPU 样本仅用于预热；采集异常或无效主机字段使用 `host_field_unavailable` 降级为 `None`。
- 未恢复事件不受历史查询窗口限制；原始实时资源样本仍仅保留在内存短窗口中。
- 运行时只在持久化就绪且非 `ALPHAFOUNDRY_PREVIEW=1` 时启动；关闭 API 时先以可配置的有限超时停止资源采样线程，再停止其他调度器。超时仅记录 `RuntimeStopTimeout` warning，不阻断关闭。

Update this section when:

- 受控 PID 来源、任务种类、异常阈值或归因置信度改变。
- 资源事件元数据或恢复语义改变。

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

### `services/market_data_scheduler.py`

Purpose:

- Schedules structured market-data refresh through APScheduler.
- Daily quote ingest runs after market close. Gap detection/backfill remains available on `MarketDataScheduler(enable_gap_check=True)`, but the standalone worker starts with it disabled so the older backfill connector chain cannot take down the scheduler process.
- Official index structure ingest runs daily at 18:10, discovers CSI/CNI active index codes from official catalogs when no fixed code list is configured, and writes constituents through `services.official_index_structure_ingestion`.
- `get_status()` reports daily ingest, gap check, and index-structure job statistics.

Related files:

- `workers/market_data_scheduler_worker.py`
- `scripts/run_official_index_structure_ingestion.py`
- `services/official_index_structure_ingestion.py`
- `app/cli/commands/data.py`

Update this section when:

- Market data job scheduling intervals change.
- Index structure provider universe, discovery cap, or default timing changes.
- Scheduler status fields change.

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
- Reads the Wind realtime workbook through a bounded backend cache. The market UI may poll
  more frequently than the cache TTL, but cache hits must not drive another Excel/xlwings
  request. Workbook read failures and timeouts are surfaced without automatically triggering
  formula re-priming.

Related files:

- `services/wind_workbook_manager.py` — creates or opens the workbook; only newly built,
  rebuilt, or explicitly manual repair flows prime Wind formulas.
- `services/wind_realtime_workbook.py` — reads the already-open workbook snapshot through
  xlwings; it does not own realtime formula refresh.

Related API:

- `app/api/routes/dashboard.py`

Related contracts:

- `core/contracts/dashboard.py`

Tests:

- Add or update dashboard service tests when dashboard fields or aggregation logic changes.

Update this section when:

- Dashboard output changes.
- Market summary logic changes.
- Wind workbook cache, recovery, or Excel automation behavior changes.
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

### `services/official_index_structure_ingestion.py`

Purpose:

- Orchestrates official CSI/CNI constituent ingestion into the index structure database.
- `ingest_csi_index_components(repo, index_code)` calls AKShare's CSIndex official-download wrapper, normalizes full constituent weights, creates `CSI:{code}` master rows, and writes `csindex_official_akshare` snapshots.
- `ingest_cni_index_components(repo, index_code)` calls AKShare's CNIndex official-download wrapper, looks up the CNI catalog name when available, and writes `cnindex_official_akshare` snapshots.
- `discover_official_index_codes(provider, max_count=...)` reads CSI/CNI official catalogs for active index code batches.
- Calls AKShare with proxy environment variables temporarily removed, matching the local market-data behavior where stale proxy settings can block official downloads.

Related files:

- `scripts/run_official_index_structure_ingestion.py`
- `data_layer/repositories/market_data_repository.py`
- `tests/unit/test_official_index_structure_ingestion.py`

Update this section when:

- CSI/CNI official source fields change.
- Additional index providers are added to the official ingestion path.
- Proxy/network handling changes.

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

### `services/wind_index_structure_probe.py`

Purpose:

- Builds a fixed Wind Excel probe workbook for CSI/CNI/HSI/WIND index structure fields and ETF scale/flow fields.
- Keeps candidate formulas in a versioned `FormulaCatalog` sheet and writes probe formulas into `ProbeResults`.
- `prime_index_structure_probe_workbook()` opens Excel through xlwings in hidden mode by default, triggers calculation, saves cached values, and logs failures instead of blocking downstream storage work.
- `read_index_structure_probe_snapshot()` reads saved workbook cache values and classifies successful formulas vs formula errors.

Related scripts:

- `scripts/run_wind_index_structure_probe.py`

Update this section when:

- Wind candidate formula keys change.
- Probe workbook sheet contracts change.
- Hidden Excel priming behavior changes.

---

### `services/wind_index_structure_ingestion.py`

Purpose:

- Converts successful Wind index structure probe rows into repository-ready rows.
- Infers provider-prefixed index ids (`CSI:000300`, `CNI:399001`, `HSI:HSI`, `WIND:8841701`) from Wind codes.
- Persists validated index names, ETF names, ETF tracking-index links, ETF NAV, ETF shares, and ETF AUM through `MarketDataRepository`.
- Does not persist failed/unknown constituent formulas; full index constituents still require a verified Wind field or official-source fallback.

Related files:

- `services/wind_index_structure_probe.py`
- `data_layer/repositories/market_data_repository.py`
- `scripts/run_wind_index_structure_probe.py`

Update this section when:

- Probe formula keys mapped to database fields change.
- Provider inference rules change.
- ETF daily metric mapping changes.

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

### `services/web_search_service.py`

Purpose:

- 联网搜索内核：协调 `WebSearchProvider` 执行网页搜索，必要时补抓网页正文，并将结果格式化为带编号的参考资料文本。
- `search(query, max_results, fetch_content)` — 调 provider 搜索，对缺正文的结果用 `data_layer/web_search/page_fetcher.py` 补抓（抓取失败优雅降级为 None，不阻塞）。
- `format_for_prompt(results)` — 输出 `[1] 标题\nURL\n正文/摘要` 格式，供 LLM 标注引用。
- 不引入 tool-calling 循环：用户要求"始终先联网"，是确定性检索增强，每次提问必搜。

Related files:

- `core/interfaces/web_search.py` — `WebSearchProvider` / `WebSearchResult` 抽象
- `data_layer/web_search/` — Tavily / Bing provider + page_fetcher + factory
- `services/ask_service.py` — 消费方

Update this section when:

- 搜索结果格式变化。
- 补抓正文策略变化。
- 新增 provider。

---

### `services/ask_service.py`

Purpose:

- 统一问答内核：联网搜索 → 注入 prompt → `ModelGateway` 生成带引用答案。
- `ask(question, max_results, fetch_content, ...)` — 始终先调 `WebSearchService.search`，将参考资料注入 user message，system prompt 要求模型标注 `[n]` 引用、未查到时如实说明。
- 降级路径：未配置搜索 API key 或搜索失败（`online=False`）时，不联网直答并在答案前标注 `[未联网]`，不报错。
- `fetch_content` 是搜索参数，不透传给 `ModelGateway.chat`（避免污染底层 SDK）。

Related files:

- `services/ask_factory.py` — `build_ask_service()` 装配工厂（CLI / API 共用，单例 ModelGateway）
- `services/web_search_service.py`
- `core/model_gateway/gateway.py`

Update this section when:

- system prompt 变化。
- 降级策略变化。
- 新增问答入口接入。

接入方：

- CLI `af ask` / API `POST /api/llm/ask`（直接调 AskService）。
- **认知代理**：`AgentWorkflowRunner`（`cognitive_agents/workflow.py`）在信息收集阶段 evidence 不足时自动调 `WebSearchService` 补充。
- **报告生成**：`ReportProjectGenerationService`（`reporting/projects/generation.py`）库内检索无结果时调 `WebSearchService` 补充。

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
