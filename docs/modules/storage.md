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