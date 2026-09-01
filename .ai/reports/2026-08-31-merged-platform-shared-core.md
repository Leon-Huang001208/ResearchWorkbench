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

The specification-review follow-up also used explicit RED→GREEN cycles. After adding the review cases, the contract suite reported `23 failed, 21 passed`: the trusted Skill registry entry point, mutually exclusive Note sources, Session-derived Message scope, and timezone-aware public fields were all absent. The corrected migration suite reported `2 failed, 4 passed`: `research_message.workspace_id` remained and a real overlapping SQLite insert was accepted. After the implementation, the focused contract/migration/graph suite passed with `54 passed in 0.34s`.

The follow-up removes Manifest self-authorization and requires Task 6 services to call `SkillManifest.validate_tool_registry()` with platform-owned authorized tool IDs. It also enforces half-open asset-identifier validity windows with a PostgreSQL GiST exclusion constraint and SQLite insert/update triggers, enforces the two Research Note source shapes in Pydantic and SQL, derives Message scope through Session, and rejects naive datetimes throughout the new merged-platform public contracts.

A final security review showed that a string blacklist still trusted a misconfigured registry. A new RED test demonstrated that `internal:bash`, `internal:sh`, `internal:cmd`, `internal:os_system`, and `internal:file_write` all passed when the caller registered them (`5 failed, 47 deselected`). The implementation now uses a closed immutable `SAFE_INTERNAL_TOOL_IDS` set: internal tools must be in that set and in the platform registry, while MCP references require registry authorization. The focused Skill tests then passed with `15 passed, 37 deselected`.

The independent quality review was also resolved through RED→GREEN checks. Source URL and Skill-extra cases first reported `5 failed, 1 passed`; structured HTTP validation and `extra="forbid"` made all six pass. The market-home exact-section test failed before its set validator and passed after it. ORM metadata checks failed before the seven named constraints were added. Actual SQLite migration tests then demonstrated that invalid scheduler rows, invalid Session/Message shapes, and overlapping identifier updates were accepted before the relevant migration checks/triggers and rejected afterward. A final malformed IPv6 URL case first failed because `urlsplit` leaked an uncontrolled error (`1 failed, 4 passed`), then passed after explicit normalization to the public `source_url` validation error (`5 passed`).

## Verification

| Command | Actual result |
| --- | --- |
| `python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py -q --tb=short` | `73 passed in 0.45s`; includes structured URL and strict market-home cases, actual SQLite overlap insert/update rejection, database schedule/session/message/note constraints, and 014→018→014 migration |
| `python -m pytest tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py tests/unit/test_dashboard.py tests/unit/test_asset_analysis_service.py -q` | `123 passed, 6 warnings in 4.39s`; existing Research Run service/API regression remains green |
| `python -m ruff check` on the three changed contract modules, two changed migrations, and two target test files | passed |
| `python -m ruff check --ignore RUF012,UP017 data_layer/repositories/models.py` | passed; the unignored run and `HEAD` baseline both report the same 24 `RUF012` + 1 `UP017` findings |
| `python -m black --check` on the changed Python files | passed; 8 files unchanged |
| `python -m isort --check-only` on the changed Python files | passed |
| `python scripts/generate_py_file_index.py` | passed; generated index includes all five contracts and four migrations |
| `python scripts/check_doc_sync.py` | passed |
| `python scripts/check_task_completion.py` | passed |
| `git diff --check` | passed |

## Limits and risks

- No live PostgreSQL instance was migrated in this task. The migration segment was executed against SQLite after stamping the two existing referenced Research tables at revision 014; PostgreSQL integration remains a later acceptance gate.
- PostgreSQL DDL compilation confirms the named `ex_asset_identifier_no_overlap` GiST exclusion constraint, but a live PostgreSQL overlap insert has not been executed. The migration creates the required `btree_gist` extension when running on PostgreSQL.
- Timezone-aware validation is complete for the new merged-platform public contracts. Existing `core/contracts/research.py` remains compatible with SQLite's naive datetime readback; unifying the older Research Run persistence path requires a later service/repository migration and is not claimed by this task.
- Running repository-wide Ruff on `data_layer/repositories/models.py` reports pre-existing `RUF012` mutable `__table_args__` and `UP017` findings outside the new 20-table block. New files and the changed block are formatted and checked separately; unrelated legacy model warnings were not rewritten.
- No dependencies were installed.
