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