# Module: cron_jobs

## Responsibility

`cron_jobs` provides scheduled ingestion, scheduled signal generation, and background automation.

---

## Design Rules

- Scheduled jobs should be idempotent
- Failure handling should be explicit
- Dependencies should be clear
- Add or update tests when job behavior changes

---

## Files

### `cron_jobs/auto_ingest_service.py`

Purpose:
- Scheduled market data and crawl data ingestion pipeline.

Schedule:
- **Crawl ingest**: `ingest_all_sources()` iterates over all enabled sources from `core.source_registry.get_enabled()`, running each through `CrawlOrchestrator.crawl_source()`. Default intervals from each `SourceSpec.interval_minutes`.
- `15:15` — `ingest_stock_master()`: sync stock list via `POST /api/market-data/stocks/sync`.
- `15:30` — `ingest_daily_bars()`: sync daily bars via `POST /api/market-data/daily-bars/sync`.
- `15:45` — `ingest_stock_snapshots()`: trigger asset analysis via `POST /api/assets/analyze`.
- API 调用通过 `RESEARCH_BACKEND_URL` 构造：桌面端默认 `http://127.0.0.1:8765`，Web 开发默认 `http://127.0.0.1:8000`。
- 摄入队列由常驻 Knowledge Worker 消费，而非 cron 定时消费。

Backward-compat aliases: `ingest_cls_data()` delegates to `ingest_all_sources()`. `ingest_cnstock_data()` and `ingest_zq_data()` are no-ops.

Related service:
- `services/market_data_ingestion_service.py`
- `services/crawl_orchestrator.py`
- `core/source_registry.py`

Update this section when:
- Schedule frequency changes.
- Ingestion steps change.
- API endpoints change.
- Failure/retry behavior changes.

---

### `cron_jobs/auto_generate_signals.py`

Purpose:
- Scheduled signal generation from approved events.

Update this section when:
- Signal generation logic changes.
- Schedule frequency changes.
- Signal approval workflow changes.

---

## Required Tests

- Scheduling logic tests
- Mocked job execution tests
- Failure handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/cron_jobs.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`