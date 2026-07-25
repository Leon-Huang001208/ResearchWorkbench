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