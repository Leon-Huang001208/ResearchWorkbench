# Module: app/api

## Responsibility

`app/api` exposes Research Workbench capabilities through FastAPI.

API routes should be thin and delegate business logic to `services`.

---

## Design Rules

- Route files should not contain business logic.
- Request/response schemas should use `app/api/models.py` or `core/contracts`.
- Service dependencies should be explicit.
- API behavior changes must update `docs/REFERENCE.md`.
- Add or update API tests when endpoint behavior changes.

---

## Files

### `app/api/main.py`

Purpose:

- Creates and configures the FastAPI application lifecycle.
- Performs startup health initialization and registers API routes.
- Returns only the stable `ready` or `unavailable` persistence state from `/health`; underlying database exceptions remain in server-side structured logs rather than HTTP responses.
- In an explicit `RESEARCH_PREVIEW=1` desktop process, preserves the readiness contract but skips schema initialization and automatic Wind/market/crawl background services, so branch acceptance does not mutate the shared runtime.

Update this section when:

- Application lifecycle behavior changes.
- Health response or error-disclosure behavior changes.
- Route registration changes.

---

### `app/api/models.py`

Purpose:

- Define API-level request/response models when not using core contracts directly.

Update this section when:

- API schema changes.
- Request/response models are added or modified.

---

### `app/api/routes/ingest_admin.py`

Purpose:

- Expose manual ingestion administration under `/api/ingest/admin` for trigger, pause, resume, reset, and source configuration operations.
- `POST /{source_type}/trigger` with `dry_run=true` validates the trigger request and returns a non-triggered response without reading or writing the database. A real trigger checks the source pause state before it can be queued.

Update this section when:

- Ingestion administration endpoints or dry-run semantics change.
- Request/response schemas or database side effects change.

---

### `app/api/routes/wind.py`

Purpose:
- Wind Excel 数据查询 API（8 个端点，`/api/wind` 前缀）
- `GET /api/wind/health` - 连接健康检查
- `POST /api/wind/consensus` - 一致预期查询
- `POST /api/wind/margin-trading` - 融资融券查询
- `POST /api/wind/block-trades` - 龙虎榜查询
- `POST /api/wind/prices` - 日行情查询
- `POST /api/wind/financials` - 财务报表查询
- `POST /api/wind/industry` - 行业分类查询
- `POST /api/wind/fund-flow` - 资金流向查询
- `POST /api/wind/holders` - 持有人数据查询

Related adapter:
- `data_layer/adapters/wind/wind_adapter.py`

Update this section when:
- Wind API 端点增删或参数变更
- 请求/响应模型变更

---

### `app/api/routes/factors.py`

Purpose:
- 动态多因子 REST API（10 个端点，`/api/factors` 前缀）
- `GET /api/factors/definitions` - 列出已注册的因子定义
- `POST /api/factors/definitions` - 注册或更新因子定义
- `GET /api/factors/values` - 查询因子值（点日期/范围查询）
- `POST /api/factors/values` - 批量存储因子值
- `GET /api/factors/evaluations` - 查询因子评估记录
- `POST /api/factors/evaluations` - 批量存储因子评估指标
- `GET /api/factors/weights/latest` - 获取最新动态权重
- `POST /api/factors/weights` - 保存动态权重快照
- `GET /api/factors/weights/history` - 查询动态权重历史
- `GET /api/factors/available-dates` - 获取有因子数据的日期列表
- `GET /api/factors/categories` - 获取所有已注册的因子类别

Related services:
- `services/factor_store_service.py`
- `services/factor_computation_service.py`

Update this section when:
- Factor API 端点增删或参数变更
- 请求/响应模型变更

### `app/api/routes/dashboard.py`

Purpose:

- Expose dashboard endpoints.

Related service:

- `services/dashboard_service.py`

Related contracts:

- `core/contracts/dashboard.py`

Update this section when:

- Dashboard endpoint changes.
- Response schema changes.
- Dashboard route dependency changes.

---

### `app/api/routes/market_data.py`

Purpose:

- Expose market data ETL endpoints.

Endpoints:

- `POST /api/market-data/stocks/sync` — trigger stock master sync.
- `POST /api/market-data/daily-bars/sync` — trigger daily bars sync.
- `GET /api/market-data/{symbol}/daily-bars` — query daily bars for a symbol.
- `GET /api/market-data/etl-runs` — query ETL run history.

Related service:

- `services/market_data_ingestion_service.py`

Related repositories:

- `data_layer/repositories/market_data_repository.py`
- `data_layer/repositories/etl_run_repository.py`

Update this section when:

- Market data endpoint changes.
- Request/response schema changes.
- Market data route dependency changes.

---

### `app/api/routes/pdf_admin.py`

Purpose:

- PDF 转换管理 API。
- `GET /api/admin/pdf/pending` — 列出待转换的 PDF（直接查询 `pdf_artifact_v1` 表 `parse_status='pending'`）。
- `GET /api/admin/pdf/stats` — 获取转换统计。
- `POST /api/admin/pdf/convert` — 触发指定 PDF 转换。
- `POST /api/admin/pdf/retry` — 重试失败的转换。

Related service:

- `services/pdf_conversion_service.py`

Related repositories:

- `data_layer/repositories/pdf_artifact_repository.py`

Update this section when:

- PDF admin endpoints change.
- Response schema changes.

---

### `app/api/routes/assets.py`

Purpose:

- Asset analysis endpoints.

Endpoints:

- `POST /api/assets/analyze` — generate asset analysis snapshot.
- `GET /api/assets/{canonical_id}` — query latest snapshot.
- `POST /api/assets/analysis-card` — generate full analysis card with K-line data, capital flow, shareholders, etc.; request supports optional `time_range` (`1M`/`3M`/`6M`/`1Y`/`2Y`/`3Y`/`5Y`/`ALL`) for K-line history windows.

Dependency injection:

- `get_asset_service()` creates `AssetAnalysisService` with `MarketDataRepository` injected via `market_repo` parameter.
- `get_wind_adapter()` creates `WindAdapter` (injected into `AssetAnalysisService`).
- Data source priority: Wind Excel → structured tables (`stock_daily_bar`, `stock_valuation`, etc.) → `MultiSourceCoordinator` (AKShare/BaoStock/Yahoo).
- Wind 不可用时静默降级到后续数据源。

Related contracts:

- `core/contracts/assets.py`

Update this section when:

- Asset analysis endpoint changes.
- Dependency injection configuration changes.
- Structured data fallback logic changes.

### `app/api/routes/asset_observation.py`

Purpose:

- Expose the canonical asset-observation API under `/api/asset-observation`.
- Return four typed asset families through `AssetSnapshotEnvelope` without creating parallel fact tables.
- Expose transparent peer-set metadata, multiple profile watchlists, Alert Rule/Event lifecycle, and persisted Notification delivery state.
- Keep route handling thin, record structured write identifiers, and map failures to safe 400/404/409/500 responses without leaking internal exception strings.

Related services and repository:

- `services/asset_observation_service.py`
- `services/alert_evaluation_service.py`
- `data_layer/repositories/asset_observation_repository.py`

Update this section when:

- Asset-observation paths, request models, response contracts, or error mapping change.
- Watchlist/Alert/Notification lifecycle behavior changes.

---

### `app/api/routes/funds.py`

Purpose:

- Fund Intelligence API endpoints.
- `POST /api/funds/ingest` — ingest structured fund rows for `master`, `nav`, `holdings`, or `managers` datasets through `FundDataIngestionService`.
- `GET /api/funds/{symbol}` — return fund master data, latest NAV, calculated performance metrics, managers, and latest disclosed holdings.
- `GET /api/funds/{symbol}/exposure` — return latest single-fund stock, industry, and theme exposure from disclosed holdings.
- `POST /api/funds/portfolio/exposure` — calculate weighted stock, industry, and theme exposure for a fund portfolio.

Related service:

- `services/fund_intelligence_service.py`
- `services/fund_data_ingestion_service.py`

Related repository:

- `data_layer/repositories/fund_repository.py`

Related contracts:

- `core/contracts/funds.py`

Update this section when:

- Fund Intelligence endpoint paths, request models, or response models change.
- Fund service dependency injection changes.
- Supported fund ingest datasets or row contracts change.

---

### `app/api/routes/report_projects.py`

Purpose:

- Report project workbench API for project folders under `report_projects/`.
- `GET /api/report-projects/` — list report projects with `project_type`, template asset metadata, Word/PPT placeholders, report config, prompt template source, compiled generation readiness plan, Excel sheet summaries, generated reports, output directory, and run-log directory.
- `GET /api/report-projects/{slug}` — load one project, preserve placeholder first-seen order from the DOCX body/header/footer XML or PPT slide XML, and return `compiled_plan` for frontend preflight checks.
- `POST /api/report-projects/order` — persist one complete report-project display order; every currently available project slug must appear exactly once.
- `POST /api/report-projects/upload` — create a Word project from `.docx` or a PPT project from `.pptx`, with optional Excel, report config, prompt templates, and data files.
- `PUT /api/report-projects/{slug}` — rename a report project.
- `PUT /api/report-projects/{slug}/source` — persist editable project source files. `source_kind=report_config` writes `config/report_config.yaml`; `source_kind=prompt_templates` writes or attaches `config/prompt_templates.md`.
- `POST /api/report-projects/{slug}/render` — render a Word project to DOCX or a static PPT project to PPTX. By default it reads `report_config.yaml` + `prompt_templates.md`, then delegates the render run to `ReportProjectRunService`, which retrieves database evidence when configured, generates placeholders, projects into the active template, attaches deterministic Word tables/charts, and writes a JSON run log.
- `GET /api/report-projects/{slug}/preview/{file_name}` — convert a generated DOCX into lightweight inline HTML; PPTX currently returns a lightweight generated-file placeholder.
- `GET /api/report-projects/{slug}/download/{file_name}` — download one generated DOCX or PPTX with the matching Office MIME type.

Related services:

- `reporting/projects/project_manager.py`
- `reporting/projects/plan.py`
- `reporting/projects/run.py`
- `reporting/projects/generation.py`
- `reporting/projects/chart_generation.py`
- `reporting/projections/ppt.py`
- `reporting/projections/word.py`

Update this section when:

- Report project request/response models change.
- Source editing, generation, preview, run-log, or chart embedding behavior changes.
- Project folder asset conventions change.

---

### `app/api/routes/research_runs.py`

Purpose:

- Cross-domain, evidence-first research-center API. `ResearchRun` in PostgreSQL is the sole run-state authority; the route delegates template validation and domain behavior to `ResearchRunService`.
- `GET /api/research-templates` — list framework-free metadata for available and planned templates. `GET /api/research-runs` lists recent runs inside the supplied project/workspace scope.
- Compatibility `POST /api/research-runs` remains additive, while the product path uses `POST /api/research-sessions/{session_id}/runs` so Session ownership and Run creation bind atomically under one project/workspace scope.
- `POST /api/research-sessions/{session_id}/runs/{run_id}/execute` — execute through `RuntimeProvider` routing; FinGPT may fall back from DSH to built-in LangGraph, while Claw persists `blocked_runtime` instead of silently changing semantics.
- `GET /api/research-runs/{run_id}` / `GET /api/research-runs/{run_id}/outputs` — return state, source plan, blockers, gates, immutable artifacts, current claims, decision card, notes, and Markdown projection.
- `POST /api/research-runs/{run_id}/evidence` and `POST /api/research-runs/{run_id}/resume` — append corrective evidence then resume only a blocked run.
- `GET /api/research-runs/{run_id}/downloads/markdown` and `/downloads/word` — export only a completed run; no trade instruction, position, or order is produced.

Related services and contracts:

- `services/research_run_service.py`
- `services/research_graph.py`
- `services/research_templates.py`
- `data_layer/repositories/research_run_repository.py`
- `core/contracts/research.py`

Update this section when:

- Research-run status, quality gates, export eligibility, or data-source fallback semantics change.
- Request/response contracts or output projections change.

---

### Merged research runtime route groups

Purpose:

- `research_workspaces.py` / `research_sessions.py` own project-scoped Workspaces, one-Run Sessions, idempotent Messages, atomic Session→Run creation and scoped execution.
- `runtime_providers.py` owns provider declarations and typed, idempotent DSH result callbacks that are correlated to the originating request and Run.
- `research_skills.py` owns declarative Skill manifests. Execution revalidates the closed internal/MCP registry, input/output JSON Schema, budget and deadline before accepting output.
- `agent_teams.py` owns Supervisor-led team definitions and bounded shared-blackboard execution.
- `agent_schedules.py` owns persistent no-reentry/latest-coalesced schedules; due schedules materialize into leased `scheduled_job` work.
- `research_runs.py` streams durable ordered stage events with `Last-Event-ID`; scoped Run reads require both `X-Project-ID` and `X-Workspace-ID`.

The public route set is additive:

```text
/api/research-workspaces
/api/research-sessions
/api/research-runs
/api/runtime-providers
/api/research-skills
/api/agent-teams
/api/agent-schedules
```

Create, execute, resume and schedule-trigger operations require an `Idempotency-Key`. Runtime failures are returned without rolling back their persisted `blocked_runtime`/`failed` state.

---

### `app/api/routes/theme_research.py`

Purpose:

- Expose the four installed Research Packs through catalog, snapshot, KPI, value-chain, event, related-asset and data-health read models.
- Create only a research Workspace prefill from a theme; the route never writes model output into theme facts.
- Keep `theme_observation` ingestion behind the migration/service boundary rather than accepting arbitrary fact writes over HTTP.

---

### `app/api/routes/system.py`

Purpose:

- System health check, worker status, status bar, event publishing, and scoped process-resource endpoints.
- `GET /api/system/health` — full health check with queue depth, pending/processing/completed/failed counts, and worker heartbeats.
- `GET /api/system/health/minimal` — lightweight health check without database query.
- `GET /api/system/workers/status` — aggregated worker/scheduler status + queue stats + processing stats (today, last_7_days, last_30_days, total, yesterday_same_time, daily_avg_7d).
- `GET /api/system/status-bar` — dashboard status bar data (git branch, DB type, LLM provider, document count, error/warning counts).
- `POST /api/system/event` — publish a system event to the event bus (for external integration/testing).
- `GET /api/system/resource-usage` — current Research Workbench process snapshot plus a seven-field machine-capacity aggregate; it never enumerates or returns machine-wide process details, and its remaining-memory fields use the host `available` value.
- `GET /api/system/resource-usage/history?window_seconds=` — bounded in-memory snapshot history; `window_seconds` defaults to `300` and must be in the inclusive range `2`–`300`.
- `GET /api/system/resource-usage/host-history?hours=` — persisted minute-level host-capacity history; `hours` defaults to `24` and must be in the inclusive range `1`–`24`.

Resource usage dependency:

- `get_resource_monitoring_service()` lazy-imports and retains one `ResourceMonitoringService` instance on first request, avoiding an eager `psutil` import at API startup.
- 数据库就绪且不是 `RESEARCH_PREVIEW=1` 时，启动钩子会以函数内延迟导入创建并缓存一个 `ResourceMonitorRuntime`。它每分钟在单独数据库会话内采样、写入主机历史并评估既有资源告警；预览明确不启动该常驻线程。关闭钩子先安全停止该线程，运行时启动或停止失败只记录 `error_type`，不阻断 API。
- Responses redact command arguments and map collection failures to public warning codes only: `field_unavailable`, `root_process_unavailable`, or `partial_data`. Internal exception classes and details are not exposed; per-process `unavailable_reason` is the stable `field_unavailable` value when data is unavailable. The `host` object always contains only CPU/available-memory capacity fields, and long-term history exposes only those fields plus Research Workbench CPU/memory proportions.

Related service:

- `services/system_event_bus.py`
- `services/ingestion_queue_service.py`
- `services/resource_monitor_service.py`
- `services/resource_monitor_runtime.py`

Update this section when:

- Health check response format changes.
- New metrics are added to health check or worker status.
- New system management endpoints are added.

---

### `app/api/routes/realtime.py`

Purpose:

- SSE (Server-Sent Events) endpoint for real-time frontend updates.
- `GET /api/realtime/stream` — subscribes to SystemEventBus, pushes events with 2-second heartbeat.
- Supports `Last-Event-ID` header for reconnection replay of missed events.
- Each SSE message includes an `id:` field for automatic reconnection tracking by browsers.

Related service:

- `services/system_event_bus.py`

Update this section when:

- SSE event types change.
- Heartbeat interval changes.
- Event format changes.
- Reconnection/replay behavior changes.

---

### `app/api/routes/market_home.py`

Purpose:

- Expose the facts-only five-section live aggregate, one-section drill-down, and immutable close snapshots.
- Stream only `event_id`, `section_key`, and `as_of` invalidation references from durable `domain_event` records, including `Last-Event-ID` replay.
- Map invalid close dates, missing snapshots, immutable conflicts, and internal failures to stable public errors without leaking exception text.
- Start one durable close-snapshot consumer after database readiness and stop it during API shutdown; branch preview and setup-required modes do not start background work.

Related modules:

- `services/market_home_service.py`
- `data_layer/repositories/market_home_repository.py`
- `core/contracts/market_home.py`

Update this section when the five-section set, mainline formula, SLA, snapshot, or SSE replay contract changes.

---

### `app/api/routes/knowledge.py`

Purpose:

- Knowledge Worker 进程管理 API（启动/停止/状态查询），支持多进程水平扩展。
- `GET /api/knowledge/status` — 查询所有 worker 进程存活状态。
- `POST /api/knowledge/start?workers=N` — 启动 N 个 worker 子进程（默认 1，最大 16）。
- `POST /api/knowledge/stop` — 停止所有运行中的 worker 进程。

Related service:

- `workers/knowledge_worker.py`
- `services/system_event_bus.py`

Update this section when:

- Knowledge Worker API 端点变更。
- 启动/停止机制变更。
- PID 文件路径变更。

---

## Required Tests

- API route tests
- Error response tests
- Request/response schema tests

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/app_api.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`

---

## Resource monitoring endpoints

`app/api/routes/system.py` provides the Research Workbench-only resource monitoring API:

- `GET /api/system/resource-usage` returns the API process tree plus explicitly registered scheduler and knowledge Worker PIDs, together with a seven-field host-capacity aggregate. API in-process tasks are marked as shared estimates; independent Worker processes are marked as exact process measurements.
- `GET /api/system/resource-usage/history` remains the in-memory, five-minute diagnostic series.
- `GET /api/system/resource-usage/host-history` returns the persisted, sorted minute-level host-capacity series for the requested 1–24 hour window. The route forwards `hours` as the repository `since` filter; each point is limited to `sampled_at`, safe `host` capacity fields, and safe Research Workbench CPU/memory proportion fields. A repository read failure is distinct from valid no-data: it returns the stable 503 contract rather than an empty 200 series.
- `GET /api/system/resource-events` returns persisted resource events for the requested history window and always includes unresolved events.
- `POST /api/system/resource-events/{alert_id}/acknowledge` and `POST /api/system/resource-events/{alert_id}/resolve` apply the existing alert lifecycle.

`/resource-usage` only collects and returns its snapshot; the runtime continuously evaluates resource events. API responses expose only whitelisted task attribution metadata and never exception text, commands, request bodies, secrets, or internal deduplication keys. Research Workbench events have `source_scope=research_workbench`; host CPU/available-memory events have `source_scope=host_capacity`. These endpoints do not emit native desktop notifications.

The route opens a database session only for the individual resource-event or host-history operation; no monitoring repository session is retained between HTTP requests.
- `docs/generated/py_file_index.md`

---

## Related Subsystems

- `core/connectors/` — 连接器通过 `ConnectorRegistry` 向 API 暴露数据源状态和摄入能力
- `connectors/` — 具体连接器实现（如 `WindMarketConnector`），通过 `app/api/routes/wind.py` 暴露 Wind 数据 API

---

## Recent Changes

- 2026-06-04: 收敛 API 路由层 mypy 历史债务，补齐上传流、监控响应、模板 section 拼装的显式类型，保持现有请求/响应行为不变。
