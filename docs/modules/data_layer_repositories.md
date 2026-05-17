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

### `data_layer/repositories/*.py`

Purpose:
- Database access implementations
- Query abstraction
- CRUD operations
- Connection management

Update this section when:
- New repository methods are added
- Query behavior changes
- Persistence strategies change
- Transaction handling changes

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