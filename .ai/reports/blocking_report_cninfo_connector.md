# Blocking Report: cninfo_connector

## Current Task

- Task ID: cninfo_connector
- Task name: CNINFO wrapper-first connector implementation and source registry/Wind Excel regression fixes
- Date: 2026-06-02

## Completed Work

- Implemented CNINFO three-layer data source structure:
  - crawler layer under `data_layer/crawlers/cninfo/`
  - adapter layer in `data_layer/adapters/cninfo_adapter.py`
  - thin connector wrapper in `connectors/document/cninfo.py`
- Added CNINFO connector unit tests.
- Exported `CninfoAdapter` from `data_layer/adapters/__init__.py`.
- Added missing `SourceType` values required by registered data sources.
- Added `fallback_group` / `fallback_priority` to `SourceSpec` and implemented `get_fallback_groups()`.
- Updated `DatasetRouter` to build deterministic fallback chains ordered by `fallback_priority`.
- Added regression coverage for Wind Excel auto-start when no Excel instance is running.
- Fixed stale tests uncovered by the expanded source registry and source search behavior:
  - `test_crawl_scheduler.py` now compares scheduler status count to `DEFAULT_CRAWL_CONFIGS` instead of hard-coding 6 sources.
  - `test_asset_search_index_service.py` now actually creates an exact-code candidate and a prefix-match candidate.
- Updated module docs and generated Python file index.

## Blocking Reason

- Required completion gate `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/` fails on repository-wide type debt and missing dependency stubs unrelated to the CNINFO implementation.
- Because project rules require this command before marking completion, the task cannot be marked `done`.

## Evidence

- Command: `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`
- Result: failed.
- Representative errors:
  - `core/contracts/outcome_journal.py`: Pydantic `Field(default_factory=...)` type mismatch.
  - `core/contracts/retrieval.py`: missing named arguments for `RetrievalProfile` and default factory typing issues.
  - `core/model_gateway/providers/anthropic.py`: missing `anthropic` stubs/import.
  - `data_layer/adapters/ifind_adapter.py`: missing `iFinDPy` stubs/import.
  - `data_layer/adapters/yahoo_adapter.py` and `data_layer/crawlers/yahoo/base.py`: missing `yfinance` stubs/import.
  - `data_layer/crawlers/zq/zhiqiu/base_fetcher.py`: multiple no-return/no-untyped/union-attr issues.
  - `data_layer/adapters/wind/client.py`: missing return type annotations and optional sheet access typing issues.
- Passing evidence:
  - Full pytest: `1556 passed, 1 skipped, 31 warnings`.
  - `ruff check .`: passed.
  - `black . --check`: passed.
  - `isort . --check-only`: passed.
  - `python scripts/check_doc_sync.py`: passed.
  - `python scripts/check_task_completion.py`: passed.

## Required Human Action

1. Decide whether to open a separate repository-wide mypy remediation task.
2. Decide whether missing optional vendor SDK/stub issues should be fixed via dependency installation/stubs/configuration. Per project rules, no Python packages were installed automatically.
3. After repository-wide mypy is fixed or explicitly waived by project governance, rerun the required completion gates.

## Safe Next Step After Unblocking

- Rerun:
  - `ruff check .`
  - `black . --check`
  - `isort . --check-only`
  - `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`
  - `python -m pytest tests/ -v`
  - `python scripts/generate_py_file_index.py`
  - `python scripts/check_task_completion.py`
  - `python scripts/check_doc_sync.py`

## Files Changed Before Blocking

- See `test_report_cninfo_connector.md` for task-specific changed files and command results.
