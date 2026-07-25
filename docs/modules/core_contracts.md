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

## Current Notes

Recent reporting-contract updates are format-only/type-safety maintenance. They preserve existing document, report, compiler, retrieval, asset, ingestion, and backtest contract behavior while keeping the repository compatible with the configured Black and mypy baselines.

---

## Files

### `core/contracts/*.py`

Purpose:

- Defines Pydantic v2 contracts shared by API, services, reporting, ingestion, and Signal Lab.
- Keeps serialization and validation boundaries explicit across the modular monolith.

Update this module document when a contract field, validation rule, serialization behavior, or exported contract changes.
