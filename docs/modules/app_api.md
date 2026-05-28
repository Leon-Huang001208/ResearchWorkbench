# Module: app/api

## Responsibility

`app/api` exposes AlphaFoundry capabilities through FastAPI.

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

- Create FastAPI app.
- Register routes.
- Configure middleware and health checks.

Update this section when:

- App initialization changes.
- Middleware changes.
- Route registration changes.

---

### `app/api/models.py`

Purpose:

- Define API-level request/response models when not using core contracts directly.

Update this section when:

- API schema changes.
- Request/response models are added or modified.

---

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
- `POST /api/assets/analysis-card` — generate full analysis card with K-line data, capital flow, shareholders, etc.

Dependency injection:

- `get_asset_service()` creates `AssetAnalysisService` with `MarketDataRepository` injected via `market_repo` parameter.
- Structured tables (stock_daily_bar, stock_valuation, etc.) queried first before falling back to `MultiSourceCoordinator`.

Related contracts:

- `core/contracts/assets.py`

Update this section when:

- Asset analysis endpoint changes.
- Dependency injection configuration changes.
- Structured data fallback logic changes.

---

### `app/api/routes/system.py`

Purpose:

- System health check, worker status, status bar, and event publishing endpoints.
- `GET /api/system/health` — full health check with queue depth, pending/processing/completed/failed counts, and worker heartbeats.
- `GET /api/system/health/minimal` — lightweight health check without database query.
- `GET /api/system/workers/status` — aggregated worker/scheduler status + queue stats + processing stats (today, last_7_days, last_30_days, total, yesterday_same_time, daily_avg_7d).
- `GET /api/system/status-bar` — dashboard status bar data (git branch, DB type, LLM provider, document count, error/warning counts).
- `POST /api/system/event` — publish a system event to the event bus (for external integration/testing).

Related service:

- `services/system_event_bus.py`
- `services/ingestion_queue_service.py`

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
- `docs/generated/py_file_index.md`