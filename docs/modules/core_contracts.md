# Module: core/contracts

## Responsibility

`core/contracts` defines Pydantic domain contracts and standardizes cross-layer data exchange.

---

## Design Rules

- Contracts should be immutable by default
- Use Pydantic validation for data integrity
- Keep contracts focused on single responsibility
- Document field semantics clearly
- Add examples for complex contract structures
- Add or update tests when contract structure changes

---

## Files

### `core/contracts/*.py`

Purpose:
- Domain model definitions
- API request/response schemas
- Event and assertion structures
- Report templates and structures

Update this section when:
- New contract types are added
- Field definitions change
- Validation rules change
- Enum variants change

---

## Required Tests

- Validation tests for required fields
- Serialization/deserialization tests
- Enum behavior verification
- Edge case handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/core_contracts.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`