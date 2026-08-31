# Merged Platform Shared Core Delivery Report

**Date:** 2026-08-31
**Scope:** Task 2 — shared contracts, centralized ORM models, and Alembic 015–018

## Delivered scope

- Added the shared identity, provenance, freshness, observation, durable event, and scheduler contracts.
- Added typed contracts for Research Packs, facts-only market home, research workspaces/runtimes/Skills/Agent Teams, and asset observation/alerts.
- Added exactly 20 additive ORM tables and four linear migrations:
  - 015: five shared fact-kernel tables.
  - 016: two theme/market-home tables.
  - 017: eight research workspace/runtime tables.
  - 018: five personal-observation tables.
- Reused existing `research_run` and `research_claim` through foreign keys. No parallel asset fact, Research Run, source-ref, or theme projection tables were added.

## TDD evidence

The contract test was created first. Its initial run failed during collection with the expected missing module:

```text
ModuleNotFoundError: No module named 'core.contracts.asset_observation'
1 error in 0.12s
```

After the contract implementation, the target contract suite passed with `22 passed in 0.06s`.

Migration and ORM tests were then created before the schema implementation. Their initial run produced the expected six failures: migrations 015–018 were absent, merged ORM tables were absent, and the Alembic head remained 014. After implementation, contract/schema/graph tests passed.

## Verification

| Command | Actual result |
| --- | --- |
| `python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py -q` | `32 passed in 0.31s`; latest focused run after Skill alias and source-hash hardening |
| `python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py tests/unit/test_dashboard.py tests/unit/test_asset_analysis_service.py -q` | `81 passed, 6 warnings in 3.55s`; includes actual SQLite upgrade 014→018 and downgrade 018→014 |
| `python -m ruff check` on the five new contract modules, four new migrations, and three target test files | passed |
| `python -m ruff check --ignore RUF012,UP017 data_layer/repositories/models.py` | passed; the unignored run and `HEAD` baseline both report the same 24 `RUF012` + 1 `UP017` findings |
| `python -m black --check` on the changed Python files | passed; 13 files unchanged |
| `python -m isort --check-only` on the changed Python files | passed |
| `python scripts/generate_py_file_index.py` | passed; generated index includes all five contracts and four migrations |
| `python scripts/check_doc_sync.py` | passed |
| `python scripts/check_task_completion.py` | passed |
| `git diff --check` | passed |

## Limits and risks

- No live PostgreSQL instance was migrated in this task. The migration segment was executed against SQLite after stamping the two existing referenced Research tables at revision 014; PostgreSQL integration remains a later acceptance gate.
- Running repository-wide Ruff on `data_layer/repositories/models.py` reports pre-existing `RUF012` mutable `__table_args__` and `UP017` findings outside the new 20-table block. New files and the changed block are formatted and checked separately; unrelated legacy model warnings were not rewritten.
- No dependencies were installed.
