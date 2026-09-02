# Merged Platform PostgreSQL Validation Report

**Date:** 2026-09-01
**Scope:** clean Alembic graph and production-dialect platform semantics

## Changes

- Alembic now reads an explicit `DATABASE_URL`; the checked-in URL is deliberately unreachable and contains no developer credential.
- The clean migration graph creates `document_v1` before PDF foreign keys, uses a PostgreSQL expression for the descending timing index, and treats the legacy-only `signal_outcome` alteration as conditional.
- Added integration coverage for `FOR UPDATE SKIP LOCKED`, lease takeover, fencing-token rejection, workspace creation idempotency, and project isolation.

## Executed evidence

- Created isolated database `alphafoundry_codex_bd12bba2` on local PostgreSQL 18.3 with pgvector 0.8.5.
- Ran the complete Alembic graph from an empty database: `001 → 018`, head `018`.
- Queried the migrated database and confirmed the merged-platform core tables, pgvector 0.8.5, and the `uq_research_session_run_id` database constraint.
- Ran `tests/integration/test_postgresql_smoke.py` together with `tests/integration/test_postgresql_platform_semantics.py`: `3 passed`.
- Ran `tests/unit/test_alembic_migration_graph.py`: `2 passed`.

## Boundaries

- This is a local PostgreSQL integration check, not a production migration, load test, or long-running multi-process soak.
- The isolated validation database must be dropped after final verification.
- Native Windows CI and installed-application smoke remain separate release gates.
