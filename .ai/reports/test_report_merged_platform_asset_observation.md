# Merged Platform Asset Observation Delivery Report

**Date:** 2026-09-01
**Scope:** Task 3 — canonical asset observation, watchlists, deterministic alerts, persisted notifications, and Tauri delivery bridge

## Delivered scope

- Added a request-scoped Repository/Service/API vertical slice under `/api/asset-observation`.
- Reused the existing stock, index, ETF, and active-fund fact stores; no parallel price, NAV, index, ETF, or fund fact table was introduced.
- Kept Watchlist Items on stable canonical `asset_id`, with idempotent membership independent of vendor-code changes.
- Added explicit peer rules for stock industry, index category, ETF tracking index/theme, and active-fund classification/benchmark.
- Implemented fresh-only, unit-compatible false-to-true alert edges, continuous-true deduplication, false resolution, and cooldown-gated subsequent edges. Skipped/unusable evaluations are retained in Rule state; triggered Event and Notification records are persisted.
- Registered the official Tauri notification plugin, added exactly three notification capabilities, and enabled its no-bundler Tauri v2 global API. The frontend reads only persisted pending records, sends their API-provided title/body, persists delivery/denial/failure, and is a no-op outside Tauri; no Rust title/body command remains.
- Serialized Alert evaluation through a Rule row lock and re-read, with an active-event partial unique index for PostgreSQL/SQLite and savepoint recovery that deduplicates conflicts without writing a Notification.
- Preserved identifier scheme/value/market internally and validates prioritized candidates against the matching fact table instead of trusting the first alias.

## TDD evidence

The three task test files were written before implementation. The first run produced the expected RED result: `20 failed, 10 errors`; service/repository/route modules were missing and the desktop plugin, capabilities, and bridge were absent. Repository tests were added before the repository and separately failed with the expected missing-module result. After implementation, the focused Python slice passed with `29 passed`, and the desktop bridge passed with `3 passed`.

One GREEN run exposed a partial-schema history lookup failure (`no such table: stock_daily_bar`). The repository was hardened to keep the latest fact projection available when optional history storage is absent; the unchanged behavior test then passed.

The independent follow-up review was also resolved through RED→GREEN. The added executable notification, active-event concurrency, API filter, and multi-identifier tests first reported `9 failed, 34 passed`; after the fixes the same target reported `43 passed`. The Node suite uses mocked `fetch` and `window.__TAURI__.notification` to execute granted, denied, failed, and Web no-op behavior rather than relying on static source checks.

The release capability review found that the packaged bootstrap's `http://127.0.0.1:8765/` navigation is a Tauri remote origin. A new exact-origin test first failed because the capability had no `remote` entry, then passed after adding only `http://127.0.0.1:8765/*`; notification permission scope remains exactly three operations and no wildcard port or `localhost` alias is authorized.

## Verification

| Command | Actual result |
|---|---|
| `python -m pytest tests/unit/test_asset_observation_service.py tests/unit/test_asset_observation_api.py tests/unit/test_desktop_notification_bridge.py tests/unit/test_asset_analysis_service.py tests/unit/test_funds_api.py tests/unit/test_merged_platform_contracts.py tests/unit/test_merged_platform_migration.py tests/unit/test_alembic_migration_graph.py -q` | `125 passed, 5 warnings in 3.38s`; warnings are existing FastAPI `on_event` and legacy `datetime.utcnow()` deprecations |
| `python -m ruff check` on the three new Python modules, route, and three task tests | passed |
| `python -m black --check` on the same changed Python files | passed; 7 files unchanged |
| `python -m isort --check-only` on the same changed Python files | passed |
| `cargo fmt --manifest-path src-tauri/Cargo.toml -- --check` | passed |
| `cargo check --locked --manifest-path src-tauri/Cargo.toml` | passed on local macOS in 0.58s after the initial dependency build |
| `npm ci --ignore-scripts` | passed; lock file installed 4 packages, audit reported 0 vulnerabilities |
| `python scripts/generate_py_file_index.py` | passed; generated index includes the new route, repository, and services |
| `git diff --check` | passed |
| `node --test tests/js/desktop_notifications.test.mjs` | `4 passed`; covered Web no-op, granted delivery, permission denial with inbox retention, and native delivery failure |
| Follow-up related regression: Task 3 tests plus asset analysis, funds, merged contracts/migrations, and Alembic graph | `129 passed, 5 warnings in 3.79s`; warnings are existing FastAPI `on_event` and legacy `datetime.utcnow()` deprecations |
| Follow-up `ruff check`, `black --check`, and `isort --check-only` on changed Python files | passed; the repository-wide legacy `models.py` rules `UP017,RUF012` remain explicitly ignored as pre-existing debt |
| Follow-up `npm ci` | passed; 4 packages installed from lock, 0 vulnerabilities |
| Follow-up `cargo fmt --check` and `cargo check --locked` | passed on local macOS; compile completed in 3.67s |
| Release capability gate: Node behavior + Python bridge + Cargo format/check | `4` Node tests and `4` Python tests passed; locked macOS Cargo check completed in 3.64s; generated schemas had no diff |

## Dependency record

- User explicitly authorized installation of the official notification plugin.
- Added `@tauri-apps/plugin-notification` `2.4.0` as a locked JavaScript runtime dependency and `tauri-plugin-notification = "2"` as a Rust dependency.
- No Python package was installed or changed.

## Limits and risks

- No live PostgreSQL server integration test was run in this task. SQLite verifies a real active-event uniqueness conflict and recoverable savepoint, the migration suite verifies 015→018→014 including the partial index, and PostgreSQL offline DDL compilation verifies the corresponding filtered unique-index statement.
- Local macOS compilation is not Windows verification. Native Windows CI must build the sidecar and installed application, and release acceptance must test notification permission allow/deny and delivery on a real Windows installed app.
- The existing no-bundler frontend initializes the global Tauri notification bridge after setup readiness. Native Windows delivery remains intentionally unclaimed until installed-app evidence exists.
