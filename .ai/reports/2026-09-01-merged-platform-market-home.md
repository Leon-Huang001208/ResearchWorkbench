# Merged Platform Market Home Delivery Report

**Date:** 2026-09-01
**Scope:** Task 4 — facts-only market home vertical slice

## Delivered scope

- Added a five-section live market-home service with independent degradation and no AI or zero-fill fallback.
- Added Asia/Shanghai A-share session resolution for `pre_open`, `open`, `lunch_break`, `closed`, and `non_trading_day`.
- Added transparent `mainline-v1` peer percentiles and fixed `0.35/0.30/0.25/0.10` weights, including components, sample size, formula version, deterministic ties, and leading/weakening projections.
- Added section SLA enforcement: 30 seconds for quotes/asset moves, 60 seconds for global aggregates/mainlines, and 15 seconds for events.
- Added immutable close snapshot reads/writes. Historical reads only access `market_home_snapshot`; they never call the live provider. Repeated close creation returns the existing five rows.
- Added durable `domain_event` invalidation replay. SSE exposes only `event_id`, `section_key`, and `as_of`, honors `Last-Event-ID`, and never transports section data.
- Added `/api/market-home/live`, `/drill-down/{section_key}`, `/snapshots/{trading_day}` GET/POST, and `/events`.

## TDD evidence

The first service test run failed during collection with the expected missing implementation:

```text
ModuleNotFoundError: No module named 'services.market_home_service'
```

After the service implementation, 17 service tests passed. Repository tests were then written first and failed with the expected missing repository module. After implementation, service and repository tests passed. API tests were written before the route and failed with the expected missing `app.api.routes.market_home`; after route registration, the API suite passed. Drill-down, the strict three-field SSE payload, latest-100 ordered replay, and original document provenance each had explicit failing tests before their implementations.

## Verification

| Command | Actual result |
| --- | --- |
| `python -m pytest tests/unit/test_market_home_service.py tests/unit/test_market_home_repository.py tests/unit/test_market_home_api.py tests/unit/test_dashboard.py tests/unit/core/services/test_system_event_bus.py tests/unit/app/api/routes/test_system_realtime.py -q` | `58 passed, 5 warnings in 3.31s` |
| `python -m ruff check --ignore B008` on the seven new/changed market-home Python and test files | passed |
| `python -m black --check` on the seven new/changed market-home Python and test files | passed |
| `python -m isort --check-only` on the seven new/changed market-home Python and test files | passed |
| `python scripts/generate_py_file_index.py` | passed |
| `python scripts/check_doc_sync.py` / `python scripts/check_task_completion.py` / `git diff --check` | passed |

Warnings are existing FastAPI `on_event` and legacy dashboard naive-UTC deprecations; this task did not introduce a new warning category.

## Limits and risks

- No live PostgreSQL instance or production market connector was exercised. Repository behavior was verified with SQLite-backed ORM tests; PostgreSQL integration remains a later acceptance gate.
- The current trading calendar handles weekends plus an injected non-trading-day set. A production exchange holiday provider must populate that set; absent that provider, weekday public holidays are not inferred.
- Close snapshots are created only for the current local trading day after close. Past missing snapshots are intentionally not reconstructed from current live data.
- No browser UI change is claimed by this task. The API contract is ready for the separate legacy-page adapter stage.
