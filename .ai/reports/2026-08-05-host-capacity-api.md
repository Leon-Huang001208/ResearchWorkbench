# Host Capacity API Delivery Report

**Date:** 2026-08-05
**Branch:** `codex/system-resource-monitor`

## Scope

- Extended `GET /api/system/resource-usage` with a strictly sanitized seven-field `host` capacity object.
- Added `GET /api/system/resource-usage/host-history?hours=24` for sorted, persisted minute-level host capacity points.
- Removed request-time resource-event evaluation; `ResourceMonitorRuntime` remains the continuous evaluator.
- Extended resource-event metadata with only the safe host source and threshold fields.

## Security and error contract

- Host payloads return only CPU, CPU-idle, logical CPU count, and total/used/available memory fields. Invalid values, booleans, non-finite floats, and unknown keys become absent or `null` under the stable field protocol.
- Host history points contain only `sampled_at`, safe `host` fields, and safe AlphaFoundry CPU/memory/proportion fields. They are sorted ascending before returning.
- Each history request uses a fresh database session and `ResourceHostHistoryService`; storage failures log only `error_type` and return `503 {"detail":"Host resource history unavailable"}`.
- Event metadata never returns `dedupe_key` or other internal fields.

## TDD evidence

The new API route tests were written before route implementation. Initial run:

```text
python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py -q
6 failed, 3 passed
```

The failures were the expected missing host sanitizer/history helper and existing request-time event evaluation. After implementation, the same test file passed (`9 passed`).

## Verification

| Command | Actual result |
| --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/test_resource_host_history_service.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_system_resource_usage.py tests/unit/app/api/routes/test_resource_monitoring.py -q` | `80 passed in 1.03s` |
| `ruff check app/api/routes/system.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/app/api/routes/test_system_resource_usage.py` | passed |
| `black --check app/api/routes/system.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/app/api/routes/test_system_resource_usage.py` | passed |
| `isort --check-only app/api/routes/system.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/app/api/routes/test_system_resource_usage.py` | passed after import-order correction |
| `python scripts/check_doc_sync.py` | passed |
| `git diff --check` | passed |

## Limits and risks

- Verification uses route/service fakes for persistence failure and history ordering; no live PostgreSQL endpoint call was made.
- The long-term service owns 24-hour retention. The API validates the requested range and returns its value, while relying on the service's bounded retained history.
