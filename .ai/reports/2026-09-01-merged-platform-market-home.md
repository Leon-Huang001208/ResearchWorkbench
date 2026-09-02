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
- Hardened the facts-only boundary after independent review: important events now expose only original-document title/source/hash/time anchors and never `DocumentEvent` model enrichment; explicit unavailable sections carry no fabricated source.
- Added a same-watermark mainline quality gate covering freshness, blocking quality flags, units, future `available_at`, missing facts, and watermark conflicts. Rejected facts are returned as `partial.missing_components` instead of disappearing silently.
- Changed A-share status and asset moves to select each symbol's latest quote at or before the request time, including universe coverage and min/max watermarks.
- Added idempotent fact-update outbox writes and persistent single-flight `market_home.close_snapshot` jobs. Concurrent snapshot unique conflicts now reread complete existing rows without poisoning the request transaction.
- Wired authoritative quote and `DocumentEvent` writers to the reusable market-home invalidation helper. Facts and their idempotent `market_home.section_invalidated` outbox rows now flush before the writer's single transaction commit; an outbox failure rolls back the fact write.
- Added the initial production `MarketHomeSchedulerRuntime`. This wiring was subsequently superseded by `.ai/reports/2026-09-01-merged-platform-unified-scheduler.md`: market close now registers on the single process-wide `DurableSchedulerRuntime`, while this class remains compatibility-only.
- Added per-section `age_seconds` to every market-home fact response, including degraded responses, so clients can display actual data age without reconstructing it.

## TDD evidence

The first service test run failed during collection with the expected missing implementation:

```text
ModuleNotFoundError: No module named 'services.market_home_service'
```

After the service implementation, 17 service tests passed. Repository tests were then written first and failed with the expected missing repository module. After implementation, service and repository tests passed. API tests were written before the route and failed with the expected missing `app.api.routes.market_home`; after route registration, the API suite passed. Drill-down, the strict three-field SSE payload, latest-100 ordered replay, and original document provenance each had explicit failing tests before their implementations.

The independent-review remediation also followed RED→GREEN. The first updated test collection failed because `MainlineCandidateBatch` did not exist. After adding only that contract, the review suite produced `12 failed, 16 passed`; failures covered `as_of` propagation, quality-gated mainlines, event enrichment leakage, per-symbol quote watermarks, snapshot uniqueness recovery, durable outbox/scheduling, and finite HTTP replay. The completed implementation passes all of those cases.

The second review was also test-first. New writer/runtime tests initially failed during collection with `ModuleNotFoundError: No module named 'services.market_home_invalidation'`. The GREEN implementation adds the reusable transaction-bound helper, production writer integration, the scheduler runtime, actual-age responses, and an actual writer-to-HTTP cursor recovery path. A first targeted pass completed with `18 passed`; the writer/runtime and adjacent repository regression completed with `63 passed`; the final combined market-home, dashboard, event bus, scheduler, startup, and writer suite completed with `130 passed`.

## Verification

| Command | Actual result |
| --- | --- |
| `/Users/leon/opt/anaconda3/bin/pytest` on market-home service/repository/API/writer/runtime, dashboard, event bus/SSE, generic scheduler, API startup, market-data writers/ingestion, documents, and index-structure ingestion | `130 passed, 4 warnings in 5.36s` |
| `/Users/leon/opt/anaconda3/bin/ruff check --ignore B008` on the fourteen changed market-home/writer/startup Python and test files | passed |
| `/Users/leon/opt/anaconda3/bin/black --check` on the fourteen changed market-home/writer/startup Python and test files | passed |
| `/Users/leon/opt/anaconda3/bin/isort --check-only` on the fourteen changed market-home/writer/startup Python and test files | passed after mechanically correcting one test import order |
| `python scripts/generate_py_file_index.py` | passed |
| `git diff --check` | passed |
| `/Users/leon/opt/anaconda3/bin/python scripts/check_doc_sync.py` | expected repository-wide failure: concurrent research-runtime source files and this hardening diff require shared top-level/module docs; the market-home decision details are synchronized in `docs/architecture/merged-platform/03-market-home.md` |
| `/Users/leon/opt/anaconda3/bin/python scripts/check_task_completion.py` | expected repository-wide failure because the shared `docs/CHANGELOG.md` is intentionally not edited in this scoped concurrent follow-up |

Warnings are existing FastAPI `on_event` and legacy dashboard naive-UTC deprecations; this task did not introduce a new warning category.

## Limits and risks

- No live PostgreSQL instance or production market connector was exercised. Repository behavior was verified with SQLite-backed ORM tests; PostgreSQL integration remains a later acceptance gate.
- The outbox API deliberately uses the caller's SQLAlchemy session. The authoritative quote and `DocumentEvent` repositories invoke it before their existing commit boundary; future fact writers must do the same. There is no separate auto-commit in the market-home repository.
- The production scheduler now uses the process-wide shared durable runtime documented in `.ai/reports/2026-09-01-merged-platform-unified-scheduler.md`. Multi-process duplicate execution is prevented by the coordinator's lease/fencing contract, but PostgreSQL-backed multi-worker behavior remains an integration acceptance gate.
- The repository-wide documentation gates remain for the parent integration pass. This follow-up does not claim they passed and does not take ownership of concurrent research-runtime files or shared changelog/index edits.
- The current trading calendar handles weekends plus an injected non-trading-day set. A production exchange holiday provider must populate that set; absent that provider, weekday public holidays are not inferred.
- Close snapshots are created only for the current local trading day after close. Past missing snapshots are intentionally not reconstructed from current live data.
- No browser UI change is claimed by this task. The API contract is ready for the separate legacy-page adapter stage.
