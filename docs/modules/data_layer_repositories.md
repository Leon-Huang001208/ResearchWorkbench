# Module: data_layer/repositories

## Responsibility

`data_layer/repositories` provides persistence and query access, isolating storage access from services.

---

## Design Rules

- Repository pattern for consistent data access
- Keep business logic out of repositories
- Use explicit transaction boundaries
- Handle connection lifecycle properly
- Add or update tests when repository behavior changes

---

## Files

### `data_layer/repositories/base.py`

Purpose:
- Base repository class providing common database access patterns.

Update this section when:
- Base query methods change.
- Transaction handling changes.

---

### `data_layer/repositories/models.py`

Purpose:
- SQLAlchemy ORM model definitions for all database tables.

Update this section when:
- New tables are added.
- Table schema changes.

---

### `data_layer/repositories/market_data_repository.py`

Purpose:
- Market data upsert operations (stock master, daily bars, quotes, financial metrics, valuations, shareholders, index components).
- PostgreSQL `on_conflict_do_update` upsert; SQLite check-then-update-or-insert fallback.
- Query methods for latest bars, latest financials, symbol listing.

Related service:
- `services/market_data_ingestion_service.py`

Related contracts:
- `data_layer/normalizers/` (normalized dict input)

Update this section when:
- New upsert or query methods are added.
- Database dialect handling changes.
- Upsert conflict strategy changes.

---

### `data_layer/repositories/etl_run_repository.py`

Purpose:
- ETL run tracking (start, finish, fail).
- Query recent run history.

Related service:
- `services/market_data_ingestion_service.py`

Update this section when:
- ETL tracking fields change.
- Query behavior changes.

---

---

### `data_layer/repositories/dashboard_data.py`

Purpose:
- Dashboard data aggregation repository.
- `get_crawl_history(source_type)` — returns crawl history items with `last_crawled_at` timestamp (queried from `ingestion_queue_item` table).
- `get_processing_stats()` — returns processing statistics (today, last_7_days, last_30_days, total, yesterday_same_time, daily_avg_7d).
- `has_enough_data()` — checks if enough real data exists.

Related service:
- `services/dashboard_service.py`

Update this section when:
- Dashboard query metrics change.
- New aggregation queries are added.

---

### `data_layer/repositories/documents_v1.py`

Purpose:
- DocumentV1 CRUD operations.
- `list_by_time_range(start_time, end_time)` — filters by `created_at` (not `available_time`).
- Dedup by `content_hash`.

Update this section when:
- Document query fields change.
- Dedup logic changes.

---

### `data_layer/repositories/ingestion_repository.py`

Purpose:
- Ingestion queue item CRUD and statistics.
- `get_processing_stats()` — aggregate processing counts across time windows.
- Queue item lifecycle: pending → processing → completed/failed.

Related service:
- `services/ingestion_queue_service.py`

Update this section when:
- Queue item status flow changes.
- Statistics aggregation changes.

---

### `data_layer/repositories/pdf_artifact_repository.py`

Purpose:
- PDF artifact CRUD and status tracking.
- `get_conversion_stats()` — aggregate stats by `parse_status`.
- `add_pdf_artifact()` — register new PDF artifact with hash-based dedup.
- Pending PDFs queried by `parse_status='pending'` for automatic conversion.

Related service:
- `services/pdf_conversion_service.py`

Update this section when:
- PDF artifact schema changes.
- Conversion status tracking changes.

### `data_layer/repositories/wind_repository.py`

Purpose:
- `WindRepository` - PostgreSQL upsert 持久化层，支持 Wind 四类数据的批量保存和查询
- `save_consensus_estimates` / `get_consensus_estimates` - 一致预期
- `save_margin_trading` / `get_margin_trading` - 融资融券
- `save_block_trades` / `get_block_trades` - 龙虎榜
- `save_daily_bars` / `get_daily_bars` - 日行情

Update this section when:
- Wind 数据表结构变更
- 查询接口参数变更

---

## Required Tests

- Repository CRUD operation tests
- Query behavior verification
- Error handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/data_layer_repositories.md`
- `docs/DATA_STORAGE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Related Subsystems

- `core/connectors/` — 连接器通过 `DocumentConnector.persist()` 将 `IngestionRecord` 入队到 `IngestionQueueRepository`，最终由 `KnowledgeWorker` 消费
- `connectors/` — 具体连接器在 `persist()` 中调用本模块的仓储进行数据库写入