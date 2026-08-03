# Test Report: wind-excel-load-20260803

## Task

- Task ID: wind-excel-load-20260803
- Task name: Prevent Wind Excel retries from causing sustained CPU load
- Date: 2026-08-03
- Branch: `codex/wind-excel-load-20260803`

## Root Cause and Scope

An Excel timeout or read error previously triggered `WindWorkbookManager` recovery. An
existing workbook with no readable snapshot then re-primed its `=wss()` formulas, increasing
Excel/Wind plugin load while Excel was already busy. The dashboard cache also expired at the
same five-second cadence as the market UI refresh, allowing repeated xlwings reads.

This change keeps existing workbooks read-only during automatic recovery, suppresses recovery
after busy/read-error states, and aligns both the market UI refresh interval and in-memory Wind
sector cache to 30 seconds.
Initial workbook creation, catalog rebuilds, and explicit `force_prime=True` repair retain
formula activation behavior.

## Changed Source Files

- `services/dashboard_service.py`
- `services/wind_workbook_manager.py`
- `app/web/static/js/dashboard.js`

## Changed Test Files

- `tests/unit/test_dashboard.py`
- `tests/unit/test_wind_workbook_manager.py`
- `tests/unit/test_desktop_shell_scaffold.py`

## Changed Documentation Files

- `docs/modules/services.md`
- `docs/modules/app_web.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`

## Commands Run

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_workbook_manager.py tests/unit/test_dashboard.py -q
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_desktop_shell_scaffold.py -q
node --check app/web/static/js/dashboard.js
/Users/leon/opt/anaconda3/bin/python scripts/generate_py_file_index.py
/Users/leon/opt/anaconda3/bin/python -m ruff check .
/Users/leon/opt/anaconda3/bin/python -m ruff check services/dashboard_service.py services/wind_workbook_manager.py tests/unit/test_dashboard.py tests/unit/test_wind_workbook_manager.py
/Users/leon/opt/anaconda3/bin/python -m black services/dashboard_service.py services/wind_workbook_manager.py tests/unit/test_dashboard.py tests/unit/test_wind_workbook_manager.py --check
/Users/leon/opt/anaconda3/bin/python -m isort services/dashboard_service.py services/wind_workbook_manager.py tests/unit/test_dashboard.py tests/unit/test_wind_workbook_manager.py --check-only
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py tests/unit/test_wind_workbook_manager.py tests/unit/test_dashboard.py -q
/Users/leon/opt/anaconda3/bin/python -m mypy services/dashboard_service.py services/wind_workbook_manager.py
/Users/leon/opt/anaconda3/bin/python scripts/check_doc_sync.py
/Users/leon/opt/anaconda3/bin/python scripts/check_task_completion.py
git diff --check
```

## Results

| Check | Result | Notes |
| --- | --- | --- |
| Baseline focused tests | pass | 30 passed before the regression tests were added. |
| RED regression run | expected failures observed | Existing empty workbook re-primed and a timeout scheduled recovery, proving the primary retry loop. |
| Wind/dashboard/desktop focused tests | pass | 80 passed, including workbook builder/parser and desktop static-dashboard coverage. |
| Frontend cadence regression | pass | The static dashboard contract requires `MARKET_REFRESH_INTERVAL_MS = 30000`; it failed while the source still used 5 seconds. |
| Dashboard JavaScript syntax | pass | `node --check app/web/static/js/dashboard.js` completed successfully. |
| Targeted ruff / black / isort | pass | All four changed Python files passed. |
| Targeted mypy | pass | `services/dashboard_service.py` and `services/wind_workbook_manager.py` passed. |
| Documentation / task integrity checks | pass | `check_doc_sync.py`, `check_task_completion.py`, and `git diff --check` passed. |
| Full-repository ruff | fail (pre-existing) | 35 unrelated errors in legacy lazy-import annotations, duplicate routes, and unused imports; none are in this change. |

## UI Verification

- Browser tested: no
- Reason: this worktree is not the currently running desktop application. Static regression coverage verifies the interval and the existing visibility/tab/trading-session guards remain unchanged.

## Platform Verification

- Local macOS Wind/Excel behavior: not run against a licensed Wind session in this worktree.
- Native Windows CI / installer smoke test: not run. This Excel/Wind integration change requires native Windows CI before Windows compatibility can be claimed.

## Final Decision

- [ ] This task is safe to mark as done.
- [x] This task is blocked from release completion until native Windows CI and a licensed Wind/Excel smoke test are recorded.
