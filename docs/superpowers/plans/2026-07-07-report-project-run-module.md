# Report Project Run Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Word/PPT report project render orchestration out of the FastAPI route and into a focused reporting module without changing the public API response.

**Architecture:** Add `reporting.projects.run` as the deep module for one project render. `app.api.routes.report_projects` keeps request/response models and path validation, then delegates to `ReportProjectRunService.execute()`. Existing generation, chart, table, Word, PPT, and run-log behavior remains unchanged behind the new seam.

**Tech Stack:** Python, FastAPI, Pydantic, python-docx, project-local reporting modules, pytest.

---

### Task 1: Add the report project run seam

**Files:**
- Create: `reporting/projects/run.py`
- Modify: `app/api/routes/report_projects.py`
- Test: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Write the failing test**

Add a unit test that imports `ReportProjectRunService` from `reporting.projects.run`, builds a minimal fake project, patches generation/projection/chart/table collaborators, executes a Word render, and asserts that the returned object includes the generated file name, run-log path, placeholder count, evidence count, and warnings.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_report_project_run_service_renders_word_project -q
```

Expected: fail with `ModuleNotFoundError: No module named 'reporting.projects.run'`.

- [ ] **Step 3: Write minimal implementation**

Create `ReportProjectRunService`, `ReportProjectRunRequest`, and `ReportProjectRunResult` in `reporting/projects/run.py`. Move the existing Word render orchestration into this service and preserve the same run-record fields currently built in the route.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_report_project_run_service_renders_word_project -q
```

Expected: pass.

### Task 2: Delegate API render to the new module

**Files:**
- Modify: `app/api/routes/report_projects.py`
- Test: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Write/adjust API test**

Keep existing API render tests as behavior coverage. Add an assertion or patch point showing the route delegates render execution to `ReportProjectRunService.execute()`.

- [ ] **Step 2: Run focused API tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q
```

Expected: pass after delegation is wired.

- [ ] **Step 3: Thin the route**

Replace inline Word/PPT render assembly in `render_report_project()` and `_render_ppt_report_project()` with calls to the new service, while keeping response model conversion in the route.

### Task 3: Update docs and verification artifacts

**Files:**
- Modify: `docs/modules/reporting.md`
- Modify: `docs/modules/app_api.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/generated/py_file_index.md`
- Create/modify: `.ai/reports/test_report_report_project_run_module.md`
- Create/modify: `.ai/progress/progress_report_project_run_module.md`
- Modify: `.ai/progress/progress.md`

- [ ] **Step 1: Update docs**

Document `reporting/projects/run.py` as the orchestration seam for a single report project render and describe that API routes delegate to it.

- [ ] **Step 2: Generate Python file index**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python scripts/generate_py_file_index.py
```

Expected: generated index includes `reporting.projects.run`.

- [ ] **Step 3: Run focused verification**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py tests/unit/test_report_project_manager.py tests/unit/test_report_project_chart_generation.py tests/unit/test_report_project_table_generation.py tests/unit/test_ppt_template_projection.py tests/unit/test_word_projection.py -q
ruff check app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py
black --check app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py
isort --check-only app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py
```

Expected: pass, or record any pre-existing/full-suite blocker in the test report.
