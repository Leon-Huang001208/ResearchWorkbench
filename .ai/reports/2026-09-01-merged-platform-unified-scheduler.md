# Merged Platform Unified Scheduler Delivery Report

**Date:** 2026-09-01
**Scope:** market close snapshots and asset alert evaluation on the process-wide durable scheduler

## Delivered scope

- Registered stable market and alert materializers/handlers before the process-wide `DurableSchedulerRuntime` starts; API startup/shutdown owns only that singleton runtime thread.
- Kept `MarketHomeSchedulerRuntime` only as a compatibility surface for existing focused tests; it is no longer wired into production startup.
- Materialized one idempotent Asia/Shanghai 15:05 close job only when the authoritative Cjpy A-share calendar confirms the trading day; missing calendars, provider errors and holidays fail closed. The handler persists five immutable market-home section snapshots in its own transaction.
- Added deterministic discovery of every profile with active alert rules and one idempotent `asset_alert.evaluate` job per profile and UTC minute bucket.
- Evaluated alert jobs with a handler-owned Session so Rule state, Alert Event, and Notification commit atomically; callback failures explicitly rollback and close.
- Preserved the existing evaluator's stale/unavailable/quarantined and quality-blocking skip behavior.
- Added deterministic failed-job retry on the same durable identity (5/10 second backoff, three attempts), preserving attempt and last error, plus locks around both singleton creation and runtime start/stop.
- Exposed poll, batch and conservative jobs-per-minute capacity. Alert materialization measures all due scheduler backlog before commit, records `ready|blocked_capacity`, rolls back an over-capacity minute, and lets existing work drain; a real SQLite test drains three profiles in two 30-second/batch-two ticks.
- Closed the serial-handler timing gap with a configurable per-job execution budget. Capacity now includes poll cadence, batch size and handler upper bound; an actual sleep-based fake proves the within-budget path, while an overrun latches degraded/blocked readiness and stops new materialization.

## TDD evidence

The first test imported `services.asset_alert_scheduler` before that module existed and produced the expected RED result:

```text
ModuleNotFoundError: No module named 'services.asset_alert_scheduler'
```

GREEN tests then exercised stable three-domain registration, authoritative trading-day/holiday/unavailable behavior, 15:05 market idempotency, five-row snapshot persistence, all-profile alert discovery, minute-bucket idempotency, persisted triggered notifications, explicit rollback/close, deterministic retry, concurrent singleton/start safety, capacity rejection, backlog drain, and one real SQLite runtime tick consuming both market and alert jobs.

## Verification

| Command | Actual result |
|---|---|
| `/Users/leon/opt/anaconda3/bin/pytest` on unified domain bindings, all market-home service/repository/API/writer/runtime tests, generic scheduler, asset observation service/API, API readiness lifecycle, and dashboard regression | `142 passed, 4 warnings in 6.54s` |
| Runtime-agnostic Python pytest on scheduler coordinator, platform scheduler domains, market runtime and API setup readiness after review fixes | `47 passed, 4 warnings in 3.63s` |
| Focused retry-budget tests after adding market/alert parametrization and terminal failure | `3 passed in 0.54s` |
| Platform scheduler domains plus scheduler coordinator after execution-budget closure | `39 passed, 4 warnings in 4.90s` |
| Final merged-platform focused regression, including market/alert/Agent registration and crash recovery | `351 passed, 5 warnings in 23.06s` |
| Local PostgreSQL 18.3 + pgvector 0.8.5 smoke and platform semantics | `3 passed`; clean `001 → 018`, `SKIP LOCKED`, lease takeover/fencing and workspace isolation verified |
| Python 3.12 `compileall` on scheduler/domain/startup source and related tests | passed |
| Runtime-agnostic Python `black --check`, `isort --check-only`, and `ruff check --ignore B008` on seven changed scheduler/domain/contract/test files | passed |
| Runtime-agnostic Python `mypy` on the three scheduler services | not completed: the configured checker stops in dependency `numpy/__init__.pyi` with “Type statement is only supported in Python 3.12 and greater” despite the Python 3.12 runtime |
| `/Users/leon/opt/anaconda3/bin/python scripts/check_doc_sync.py` | passed after synchronizing the architecture, core service, storage, data-storage, changelog, and task-report docs |
| `/Users/leon/opt/anaconda3/bin/python scripts/check_task_completion.py` | passed |
| `git diff --check` | passed |

Warnings are the existing FastAPI `on_event` deprecations. No dependency was installed or changed.

## Limits and risks

- Local PostgreSQL verified migration, `SKIP LOCKED`, lease takeover/fencing and workspace isolation. It was not a long-running multi-process soak, load test, or production migration.
- No native Windows CI or installed-app smoke test was run; this backend scheduler change does not claim Windows runtime verification.
- Cjpy is the configured calendar authority. A local deployment without an available/credentialed Cjpy calendar intentionally produces no close job and logs the fail-closed readiness condition; an offline exchange-calendar dataset is not yet bundled.
- `DurableSchedulerRuntime` is process-wide, not cluster-wide. Cross-process single-flight relies on the persisted lease/fencing coordinator and database constraints.
- Scheduler delivery is at-least-once. Market snapshots and alert evaluation are duplicate-safe; Agent jobs use a reservation/takeover/terminal ledger and replay terminal outcomes after acknowledgement loss. External providers must still honor the stable execution/request identity, so this delivery does not claim universal exactly-once behavior outside the platform boundary.
