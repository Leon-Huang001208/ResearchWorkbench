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
- Creates the process-wide SQLAlchemy engine only after `core.settings` has resolved its runtime configuration.
- Reports PostgreSQL startup failures without returning connection credentials; desktop callers must install PostgreSQL + pgvector instead of receiving a SQLite fallback.

Update this section when:
- Base query methods change.
- Transaction handling changes.

---

### `data_layer/repositories/models.py`

Purpose:
- SQLAlchemy ORM model definitions for all database tables.
- 定义合并平台 20 张新增表：共享事实核 5 张、主题/首页 2 张、研究运行时 8 张、个人观察 5 张；继续复用既有 Research Run 与股票/指数/ETF/基金事实表。
- `domain_event` 是持久事件权威；`scheduled_job` 保存租约与幂等状态，并以命名 CHECK 强制 no-reentry/latest 和完整 lease pair；`theme_observation` 是唯一主题事实表，主题六类读模型不物化。
- `asset_identifier` 在 PostgreSQL 以半开时间范围 exclusion constraint 阻止同一供应商代码的有效期重叠，并要求 `valid_to > valid_from`。
- `research_session` 以 CHECK 强制 mode/scope 一致，`research_message` 通过 Session 推导 Workspace 且 content/content_ref 恰一非空；`agent_schedule` 以 CHECK 强制 no-reentry/latest；`research_note` 以 CHECK 强制 Claim-only 或 Run+paragraph 两种互斥来源并复用既有 Run/Claim，`watchlist_item` 只引用 `asset_registry.asset_id`。

Update this section when:
- New tables are added.
- Table schema changes.

### `data_layer/repositories/research_run_repository.py`

Purpose:

- Persist `ResearchRun`, normalized `ResearchSubject`, evidence input, task state, immutable versioned artifacts, current claim projection, and current quality-gate projection; keep `target_id` as a compatibility index.
- List recent runs by update time for the unified research center.
- Preserve prior attempt artifacts; re-running a blocked task only refreshes current views and appends a new artifact revision.

Related service:
- `services/research_run_service.py`

Update this section when:
- Research state, artifact idempotency, or projection replacement semantics change.

---

### `data_layer/repositories/market_data_repository.py`

Purpose:
- Market data upsert operations (stock master, daily bars, quotes, financial metrics, valuations, shareholders).
- Index structure persistence for CSI/CNI/HSI/WIND providers: index master data, constituent snapshots, stock-to-index membership lookup, index ETF links, and ETF daily scale/flow metrics.
- PostgreSQL `on_conflict_do_update` upsert; SQLite check-then-update-or-insert fallback.
- Query methods for latest bars, latest financials, symbol listing, index constituents, stock index memberships, linked ETFs, and ETF daily metrics.

Related service:
- `services/market_data_ingestion_service.py`
- `services/official_index_structure_ingestion.py`
- `services/wind_index_structure_ingestion.py`

Related contracts:
- `data_layer/normalizers/` (normalized dict input)

Update this section when:
- New upsert or query methods are added.
- Database dialect handling changes.
- Upsert conflict strategy changes.
- Index/ETF table contracts or source precedence rules change.

---

### `data_layer/repositories/fund_repository.py`

Purpose:
- Fund Intelligence MVP persistence for `fund_master`, `fund_nav_daily`, `fund_holding_stock`, and `fund_manager_tenure`.
- `ensure_schema()` creates the MVP fund tables for the active SQLAlchemy bind.
- Upsert methods persist fund master data, NAV history, latest report holdings, and manager tenures.
- Query methods return `core.contracts.funds` Pydantic contracts for fund detail and exposure services.

Related service:
- `services/fund_intelligence_service.py`

Related contracts:
- `core/contracts/funds.py`

Update this section when:
- Fund table schema changes.
- Upsert or query methods are added.
- The MVP table ownership moves into global ORM models or Alembic migrations.

---

### `data_layer/repositories/fund_repository.py`

Purpose:
- Fund Intelligence MVP persistence for `fund_master`, `fund_nav_daily`, `fund_holding_stock`, and `fund_manager_tenure`.
- `ensure_schema()` creates the MVP fund tables for the active SQLAlchemy bind.
- Upsert methods persist fund master data, NAV history, latest report holdings, and manager tenures.
- Query methods return `core.contracts.funds` Pydantic contracts for fund detail and exposure services.

Related service:
- `services/fund_intelligence_service.py`

Related contracts:
- `core/contracts/funds.py`

Update this section when:
- Fund table schema changes.
- Upsert or query methods are added.
- The MVP table ownership moves into global ORM models or Alembic migrations.

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

### `data_layer/repositories/document_repository.py`

Purpose:
- SourceDocument CRUD operations for the `source_document` table.
- Uses ORM field `doc_metadata` for document metadata.
- Upserts existing documents by refreshing title, published time, source name, `content_hash`, `parser_version`, `object_uri`, and metadata.

Related worker:
- `workers/knowledge_worker.py` — persists `source_document` before extracted events are saved.

Update this section when:
- SourceDocument field mapping changes.
- Upsert behavior changes.

---

### `data_layer/repositories/agent_view_repository.py`

Purpose:
- Agent view and blackboard conflict persistence.
- Packs newer `AgentView` extension fields (`assumptions`, `risks`, `invalidation_triggers`, `recommended_next_checks`) into JSON metadata under `_agent_view_extensions`.
- Unpacks metadata with explicit JSONB boundary type narrowing before constructing the domain `AgentView`.

Update this section when:
- Agent view metadata packing/unpacking changes.
- Extension fields move from metadata into first-class table columns.
- Conflict persistence or query behavior changes.

---

### `data_layer/repositories/ingestion_repository.py`

Purpose:
- Ingestion queue item CRUD and statistics.
- `get_processing_stats()` — aggregate processing counts across time windows.
- Queue item lifecycle: pending → processing → completed/failed.
- `processed_at` is set when an item is claimed for processing, cleared when a retry returns to pending, and set to the final failure time for permanently failed items.

Related service:
- `services/ingestion_queue_service.py`

---

### `data_layer/repositories/factor_repository.py`

Purpose:
- 动态多因子数据持久化仓储
- 通用 `_upsert(model, records, key_cols)` 方法：基于 PostgreSQL `ON CONFLICT DO UPDATE`
- `save_definitions()` / `get_definitions()` / `get_all_categories()` — 因子定义 CRUD
- `save_values()` / `get_values()` / `get_values_for_date()` / `get_available_dates()` — 因子值存取
- `save_evaluations()` / `get_evaluations()` / `get_latest_evaluations()` — 因子评估存取
- `save_weights()` / `get_latest_weights()` / `get_weights_history()` — 动态权重存取
- `close()` — 清理数据库 session

Related services:
- `services/factor_store_service.py`
- `services/factor_computation_service.py`

Update this section when:
- 新表或新查询方法添加
- Upsert 逻辑变更
- 索引策略变更

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

---

### `data_layer/repositories/monitoring_repository.py`

Resource monitoring usage:

- 资源监控第二期复用 `alert_payload` 与 `incident_record`，通过 `Subsystem.RESOURCE_MONITORING` 过滤事件，不创建重复告警表。
- 资源事件的任务/来源/PID/置信度归因存放在既有 JSON `metadata`；AlphaFoundry 受控任务事件使用 `source_scope=alphafoundry`，整机 CPU/可用内存容量事件使用 `source_scope=host_capacity`；不得存储秘密、命令参数或异常原文。
- 未解决的资源告警在 API 查询中始终返回，即使其早于默认 90 天历史窗口。
- `update_alert_details_if_unresolved()` 以 `alert_id` 和 `status != resolved` 为条件原子更新 severity、标题、描述、阈值及安全 metadata；它不会写入确认或解决字段，已解决记录仅返回当前值。
- `get_or_create_open_resource_alert()` 按任意资源事件去重键查询未解决事件，并以周期序号确定性主键在 savepoint 中创建；并发主键冲突后使用独立只读事务返回当前未解决事件，避免 SQLite 旧读快照且不回滚调用者事务。已解决历史保留，后续周期生成新 ID。
- 整机容量分钟历史复用 `health_metrics.extra`，且仅持久化 `metric_type=host_capacity` 的白名单 CPU/内存字段；仓储在排序和 `limit` 前按该类型过滤，以稳定 UUIDv5 后缀的分钟主键在 savepoint 内避免重复写入，并按调用方提供的非空 ID 精确删除。24 小时清理查询使用严格早于保留边界的上界，边界点不参与批次限制。

Update this section when:

- 资源事件的持久化、过滤、确认或解决逻辑改变。
- 整机容量历史的保留或精确删除逻辑改变。
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
