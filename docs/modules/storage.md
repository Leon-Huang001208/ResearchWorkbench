# Module: storage

## Responsibility

`storage` provides database schema, Alembic migrations, and storage conventions.

---

## Design Rules

- Migrations should be reversible
- Schema changes should be backward compatible when possible
- Storage conventions should be consistent
- Add migration tests when feasible
- Add or update tests when storage behavior changes

---

## Files

### `storage/*.py`

Purpose:
- Database models and schema
- Connection setup
- Storage utilities

Update this section when:
- Schema changes
- Connection logic changes
- Storage utilities change

### `storage/migrations/env.py`

Purpose:
- Alembic environment configuration.
- `target_metadata = Base.metadata` (now uncommented, enabling `--autogenerate` migration generation).

Update this section when:
- Autogenerate configuration changes.
- Migration target metadata changes.
- Migration run-time logic changes.

### `storage/migrations/*`

Purpose:
- Alembic migration files
- Schema versioning
- Data migration scripts

Key migrations:
| 编号 | 文件 | 说明 |
|------|------|------|
| 010 | `010_add_wind_data_tables.py` | Wind 数据表：wind_consensus_estimate, wind_margin_trading, wind_block_trade, wind_daily_bar |
| 011 | `011_add_factor_store_tables.py` | 动态多因子表：factor_definition, factor_value, factor_evaluation, dynamic_factor_weight（含索引和唯一约束） |
| 012 | `012_add_index_structure_tables.py` | 指数发布方、指数主表、成分权重快照、指数 ETF 关系和 ETF 日度规模/资金流表 |
| 013 | `013_add_research_run_tables.py` | 研究运行、任务、不可变产物、当前观点投影和质量门禁表；运行状态与可恢复节点由 `research_run` 权威持久化。 |
| 014 | `014_add_research_subject.py` | 为现有研究任务增加 `subject_type` 与 `subject_payload`；保留 `target_id`，旧数据默认映射为 security subject。 |
| 015 | `015_add_platform_fact_core.py` | 新增 canonical 资产身份、唯一主题 Observation、PostgreSQL 调度租约和持久 `domain_event` 权威记录。 |
| 016 | `016_add_theme_and_market_home.py` | 新增版本化 `theme_pack` Manifest 与不可变 `market_home_snapshot`。 |
| 017 | `017_add_research_workspace_runtime.py` | 新增 Workspace/Session/Message、Runtime、Skill、Agent Team/Schedule 和版本化 Note；复用既有 Research Run/Claim。 |
| 018 | `018_add_asset_observation.py` | 新增 Watchlist、Alert Event 与站内 Notification 五张个人观察表。 |

Update this section when:
- New migrations are added
- Migration logic changes

---

## Required Tests

- Migration tests when feasible
- Schema compatibility tests
- Repository integration tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/storage.md`
- `docs/DATA_STORAGE.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`
