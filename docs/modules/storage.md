# Module: storage

## Responsibility

`storage` provides database schema, Alembic migrations, and storage conventions.

## PostgreSQL test safety

Tests marked `postgresql` are excluded from the default offline suite. They require `ALPHAFOUNDRY_RUN_POSTGRES_TESTS=1` and `ALPHAFOUNDRY_TEST_DATABASE_URL`; the configured database name must contain `test`. This prevents bootstrap and CRUD smoke tests from using the runtime `DATABASE_URL` or a production database.

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