# AlphaFoundry Resource Monitor — Task 1–4 Evidence Report

## Scope

- Date: 2026-08-05
- Branch: `codex/system-resource-monitor`
- `services/resource_monitor_service.py` samples only the API root process and its recursive descendants.
- `app/api/routes/system.py` exposes the collector through `GET /api/system/resource-usage` and `GET /api/system/resource-usage/history`, with lazy construction, request validation, and response sanitization.
- `app/web/static/js/resource-monitor.js` provides the “系统监控” workbench page: bounded history, visible-page polling, chart fallback, a process table, and a detail drawer.

## Current Contract

- Resource collection is scoped to the API process root and recursive descendants; it does not enumerate machine-wide processes.
- `GET /api/system/resource-usage/history` defaults `window_seconds` to `300` and accepts `2` through `300` inclusive.
- API responses redact command arguments and replace internal collection failures with `field_unavailable`, `root_process_unavailable`, or `partial_data`; `unavailable_reason` is a stable public code.
- The frontend requests the 300-second history once per activation and current snapshots while the resource-monitor section is visible. It retains at most 150 points, aborts requests when hidden or navigated away, and shows the previous frame during request failure. Connection count is a count of process connections, not per-process network-byte throughput.

## Actual Commands and Results

| Command | Result | Evidence |
| --- | --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/app/api/routes/test_system_resource_usage.py tests/unit/test_resource_monitor_frontend_static.py -q` | passed | 31 passed in 0.52s, then again in 0.56s after the sorting/cache update. Expected collector downgrade logs appeared in field/error-path tests. |
| `node --check app/web/static/js/resource-monitor.js && node --check app/web/static/js/app.js` | passed | Both ES modules parsed successfully. |
| `git diff --check` | passed | No whitespace errors before the Task 4 documentation update; rerun after the update is recorded below. |
| `ALPHAFOUNDRY_RUN_MODE=desktop ALPHAFOUNDRY_DESKTOP_DATA_DIR=/tmp/alphafoundry-resource-monitor.nmAKUU python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000` | passed (setup-required mode) | The real application completed startup in desktop setup-required mode without a PostgreSQL connection. |
| Two `curl` snapshot calls, one history call, and `window_seconds=301` against that server | passed | Both snapshots returned only the API PID; history returned two points and the invalid window returned HTTP 422. On this macOS host `io_counters` and `net_connections` were unavailable for the API process, so the public snapshot was correctly `degraded` with `field_unavailable` warnings. |
| A temporary, source-unmodified Uvicorn launcher with persistence readiness stubbed to `ready` | passed for UI acceptance | It allowed the existing setup gate to release for a local browser check; no database schema or scheduler was started. |
| In-app browser at `http://127.0.0.1:8001/` | passed with limits | The resource-monitor section became active, sampled the API process and a temporary recursive child, rendered CPU and memory charts, showed the summary/table, opened the process-detail drawer, and used the `20260805b` module cache version. Default CPU order showed the child at 94.4% before the API at 0.6%; selecting memory reordered the API at 314.6 MiB before the child at 3.4 MiB. No screenshot artifact was saved. |

## Browser and API Observations

- The normal local server initially could not start in web-development mode because PostgreSQL was unavailable. Desktop setup-required mode did start, but its established setup gate correctly prevented navigation away from configuration; this is not a resource-monitor failure.
- The readiness-stubbed local launcher was used only to exercise the already-built frontend without changing source files. It started one temporary CPU-bound recursive child so that the browser check could verify default CPU order and memory-column reordering, in addition to the API row and detail drawer.
- The macOS sample did not expose per-process disk I/O counters or network connection counts through psutil. The UI displayed `--` for those metrics and the API retained the stable public `field_unavailable` code; no raw exception text was shown.
- No Windows runner, desktop installer, or licensed Wind/Excel session was involved. This feature is not a claim of Windows desktop verification.

## Remaining Risk and Follow-up

- `psutil` availability is platform- and permission-dependent; optional I/O and connection fields can remain unavailable even when CPU/RSS sampling succeeds.
- Browser acceptance verified two-row CPU and memory ordering after the `20260805b` resource-monitor cache update. Disk-I/O ordering could not be verified because macOS did not expose per-process I/O counters in this session.
- Full-repository quality gates and repository-wide mypy were not rerun as part of Task 4. Earlier scoped mypy evidence was blocked by existing structured-logger type errors in imported observability modules, not by the resource-monitor targets.

## Final Status

- Focused backend/frontend tests, JavaScript syntax checks, live API boundary checks, and a browser smoke check have passed with the limits above.
- Documentation now covers the frontend lifecycle and degradation contract. Platform/permission limitations remain explicitly open.
