# Merged Platform Asset Observation Delivery Report

**Date:** 2026-09-01
**Scope:** Task 3 — canonical asset observation, watchlists, deterministic alerts, persisted notifications, and Tauri delivery bridge

## Delivered scope

- Added a request-scoped Repository/Service/API vertical slice under `/api/asset-observation`.
- Reused the existing stock, index, ETF, and active-fund fact stores; no parallel price, NAV, index, ETF, or fund fact table was introduced.
- Kept Watchlist Items on stable canonical `asset_id`, with idempotent membership independent of vendor-code changes.
- Added explicit peer rules for stock industry, index category, ETF tracking index/theme, and active-fund classification/benchmark.
- Implemented fresh-only, unit-compatible false-to-true alert edges, continuous-true deduplication, false resolution, and cooldown-gated subsequent edges. Skipped/unusable evaluations are retained in Rule state; triggered Event and Notification records are persisted.
- Registered the official Tauri notification plugin on Rust and JavaScript sides, added exactly three notification capabilities, and exposed a Rust command that accepts only bounded persisted summaries without logging message text.

## TDD evidence

The three task test files were written before implementation. The first run produced the expected RED result: `20 failed, 10 errors`; service/repository/route modules were missing and the desktop plugin, capabilities, and bridge were absent. Repository tests were added before the repository and separately failed with the expected missing-module result. After implementation, the focused Python slice passed with `29 passed`, and the desktop bridge passed with `3 passed`.

One GREEN run exposed a partial-schema history lookup failure (`no such table: stock_daily_bar`). The repository was hardened to keep the latest fact projection available when optional history storage is absent; the unchanged behavior test then passed.

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

## Dependency record

- User explicitly authorized installation of the official notification plugin.
- Added `@tauri-apps/plugin-notification` `2.4.0` as a locked JavaScript runtime dependency and `tauri-plugin-notification = "2"` as a Rust dependency.
- No Python package was installed or changed.

## Limits and risks

- No live PostgreSQL integration test was run in this task. SQLite verifies repository reuse/idempotency and the existing migration suite verifies 015→018→014.
- Local macOS compilation is not Windows verification. Native Windows CI must build the sidecar and installed application, and release acceptance must test notification permission allow/deny and delivery on a real Windows installed app.
- The Rust bridge is implemented without a new UI. A client must first read the persisted Notification, request or inspect native permission through the three allowed plugin operations, invoke the bounded bridge, and persist the resulting delivery state.
