# Test Report: report-template-load-diagnostics

## Task Info

- Task ID: ad-hoc-report-template-load-diagnostics
- Date: 2026-07-24
- Affected subsystem: `reporting/projects`, `app/api/routes/report_projects.py`, report template workbench
- User request: stop the report template page from silently rendering “暂无模板” when a template source or report-project assets fail.

## Changed Source Files

- `reporting/projects/project_manager.py`
- `app/api/routes/report_projects.py`
- `app/web/static/js/templates.js`
- `app/web/templates/index.html`
- `app/web/static/style.css`

## Changed Test Files

- `tests/unit/test_report_project_manager.py`
- `tests/unit/test_report_projects_api.py`
- `tests/unit/test_report_template_workbench_frontend.py`

## Changed Documentation

- `docs/modules/reporting.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`

## Behavior Verified

- `ReportProjectManager.scan_projects()` returns usable projects plus stable diagnostics for malformed `project.yaml` and missing active templates.
- `GET /api/report-projects/` keeps usable projects in `projects` and returns non-fatal diagnostics in `issues`.
- The template workbench makes one parallel request per source with `Promise.allSettled()`.
- One failed source keeps cards from the available source visible and displays an explicit warning.
- Two failed sources show an error and retry action; they do not render the normal “暂无模板” empty state.
- A restored `华安ETF周报` is visible alongside the other report templates in the real local application.

## Commands Run

- `python3 -m pytest tests/unit/test_report_project_manager.py -k scan_projects -v` (RED before implementation: expected missing `scan_projects()` failure)
- `python3 -m pytest tests/unit/test_report_projects_api.py -k scan_issues -v` (RED before implementation: expected missing `issues` response field)
- `python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -k exposes_source_failures -v` (RED before implementation: expected missing load-state wiring)
- `python3 -m pytest tests/unit/test_report_project_manager.py -k 'scan_projects or list_projects' -v`
- `python3 -m pytest tests/unit/test_report_projects_api.py -k 'list_report_projects' -v`
- `python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -k 'templates_list' -v`
- `node --check app/web/static/js/templates.js`
- `curl http://127.0.0.1:8765/api/report-projects/`
- Playwright CLI real-app verification at `http://127.0.0.1:8765`

## Command Results

- Targeted manager tests: 3 passed, 2 deselected.
- Targeted API tests: 2 passed, 58 deselected; FastAPI deprecation warnings only.
- Targeted frontend static tests: 2 passed, 58 deselected.
- JavaScript syntax check: passed.
- Runtime API: 3 visible projects (`创业板50周报`, `华安ETF周报`, `华安ETF投资风向标`) and no actionable project scan issues.
- Browser normal state: all three cards visible; screenshot `template-diagnostics-20260724.png`.
- Browser single-source failure: report-project API intercepted with 503; legacy cards stayed visible and warning text displayed; screenshot `template-single-source-failure-20260724.png`.
- Browser dual-source failure: both APIs intercepted with 503; error text and retry action displayed, grid said “模板来源暂时不可用，请重试。” rather than “暂无模板”; screenshot `template-double-source-failure-20260724.png`.

## Skipped Tests

- None for targeted diagnostics coverage.

## Required Gate Results

- `ruff check .` — failed before this task's scoped checks because of 31 pre-existing repository-wide violations in unrelated API routes and legacy tests; scoped changed-file Ruff check passed.
- `black . --check` — not reached in the combined full command after repository-wide Ruff failure; scoped changed-file Black check passed.
- `isort . --check-only` — not reached in the combined full command after repository-wide Ruff failure; scoped changed-file isort check passed.
- `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/` — failed with 51 pre-existing repository-wide errors in 13 files; the changed `project_manager.py` and `report_projects.py` pass scoped mypy.
- `python -m pytest tests/ -v` — failed on pre-existing/environment-dependent tests: restored chart workbook content no longer matches hardcoded chart-zero assertions, historical generated DOCX fixtures are absent, several stale static frontend expectations fail, and unrelated CNStock/Wind expectations fail. Targeted diagnostics tests passed.
- `python scripts/generate_py_file_index.py` — passed.
- `python scripts/check_doc_sync.py` — passed.
- `python scripts/check_task_completion.py` — passed.

## Remaining Risk

- The default report assets remain ignored local binaries; this task exposes asset failures but does not establish cross-machine asset delivery or recover the separate `创业板50周报` source assets.
- Repository-wide quality gates remain blocked by unrelated existing failures, so this task cannot be marked complete under project policy.

## Final Test Decision

- Targeted behavior and browser scenarios are verified, but required full-project gates fail. Status: blocked.
