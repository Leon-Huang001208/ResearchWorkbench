# Host Capacity Resource Monitor Verification Report

**Date:** 2026-08-05
**Branch:** `codex/system-resource-monitor`
**Scope:** Delivery documentation, quality verification, and isolated desktop-preview evidence for host-capacity resource monitoring.

## Documented contracts

- The system-monitor page uses the in-process AlphaFoundry diagnostic path: a maximum five-minute / 150-point snapshot history of the API process tree and explicitly registered AlphaFoundry Workers. It does not enumerate other machine processes.
- `ResourceMonitorRuntime` is the distinct persistent path. When database readiness succeeds and `ALPHAFOUNDRY_PREVIEW != 1`, one stoppable thread samples host capacity each minute, persists a whitelisted aggregate, retains 24 hours, and evaluates resource events.
- `GET /api/system/resource-usage/host-history?hours=1..24` reads that persisted history. `memory_available_bytes` and `memory_available_percent` mean the operating system `available` value, not `total - used`.
- Alert metadata distinguishes controlled application events with `source_scope=alphafoundry` from host CPU/available-memory capacity events with `source_scope=host_capacity`.
- Resource events are presented by the API/system-monitor page; no native desktop notification is emitted.
- Branch previews deliberately set `ALPHAFOUNDRY_PREVIEW=1`; the persistent runtime does not start there, so previews cannot establish 24-hour background collection.

## Files updated

- `docs/ARCHITECTURE.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/modules/app_api.md`
- `docs/modules/app_web.md`
- `docs/modules/core_services.md` (new cross-service contract index)
- `docs/modules/data_layer_repositories.md`
- `docs/generated/py_file_index.md` was regenerated; it had no resulting diff.

## Actual verification evidence

| Command | Actual result |
| --- | --- |
| `python scripts/generate_py_file_index.py` | Passed: `Generated docs/generated/py_file_index.md`. |
| `python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/test_resource_host_history_service.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_monitoring.py -q` | Passed: `118 passed in 0.71s`. Expected mocked failure-path logs were emitted by the tests. |
| `ruff check $(git diff --name-only 22d9066..HEAD | rg '\\.py$')` | Passed: `All checks passed!` for 16 changed Python files. |
| `black --check $(git diff --name-only 22d9066..HEAD | rg '\\.py$')` | **Failed:** `would reformat tests/unit/test_resource_monitor_frontend_static.py`; the other 15 changed Python files were unchanged. No test or business code was changed in this delivery task. |
| `isort --check-only $(git diff --name-only 22d9066..HEAD | rg '\\.py$')` | Passed (no output; command exit status 0). |
| `node --check app/web/static/js/app.js` | Passed (no output; command exit status 0). |
| `node --check app/web/static/js/resource-monitor.js` | Passed (no output; command exit status 0). |
| `python scripts/check_doc_sync.py` | Passed: `No source files requiring doc sync were changed.` |
| `python scripts/check_task_completion.py` | Passed: `Task completion check passed.` |
| `git diff --check` | Passed (no output; command exit status 0). |

## Isolated desktop-preview evidence

1. Read-only port inspection found no listener on `127.0.0.1:8766`; the stable desktop listener on `8765` was not inspected, started, stopped, or changed.
2. Started the documented isolated command: `npm run desktop:preview -- --port 8766`. It created a temporary runtime-data directory and set `ALPHAFOUNDRY_PREVIEW=1`.
3. `GET http://127.0.0.1:8766/api/system/health/minimal` returned HTTP 200.
4. `GET http://127.0.0.1:8766/api/system/resource-usage` returned HTTP 200 with `status="degraded"`, a seven-field `host` aggregate, one API process, and public `field_unavailable` warnings for local I/O/connection fields. This verifies the endpoint response under the isolated preview.
5. `GET http://127.0.0.1:8766/api/system/resource-usage/host-history?hours=24` returned HTTP 503 with `{"detail":"Host resource history unavailable"}`. Preview logs show database setup-required mode and the database session failure; this is the documented unavailable-storage contract, not a successful 24-hour-history verification.
6. Preview startup logged that background workers were skipped, and the application startup path skips `ResourceMonitorRuntime` when `ALPHAFOUNDRY_PREVIEW=1`. The isolated preview was then stopped with its own process interrupt; no listener remained on 8766.

## Remaining risks and unverified boundaries

- The delivery gate is not fully clean because `black --check` fails for `tests/unit/test_resource_monitor_frontend_static.py`. This task deliberately did not reformat or modify that test.
- A normal, database-ready non-preview API lifecycle was not started. Therefore minute-by-minute persistence, 24-hour retention, and a successful live `host-history` response against PostgreSQL remain unverified in this environment.
- Windows is unverified. No native Windows CI runner, Windows sidecar/installer build, or real Windows installation smoke test was run; macOS preview evidence must not be treated as Windows support evidence.
- The preview resource snapshot was degraded because local process I/O and connection fields were unavailable. The API's public degradation contract was observed, but this does not validate all psutil/platform combinations.
