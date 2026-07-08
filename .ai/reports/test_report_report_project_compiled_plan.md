# Test Report: report_project_compiled_plan

## Scope

- `reporting/projects/plan.py`
- `app/api/routes/report_projects.py`
- `app/web/static/js/templates.js`
- report project API / frontend static tests

## Changes Verified

- Added `CompiledReportPlan` as a backend pre-render readiness plan for report projects.
- Verified composite placeholders inherit `llm_writing` component retrieval before readiness is computed.
- Verified missing prompt templates surface as preflight warnings before generation starts.
- Verified report project API responses expose `compiled_plan`.
- Verified template workbench preflight prefers backend compiled plans when present.
- Verified template workbench preflight renders Prompt coverage, Evidence coverage, and output asset groups.
- Verified template workbench preflight surfaces a prioritized user task queue and Evidence samples.
- Verified current issue settings bar and post-generation delivery check card.

## Commands

- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_project_plan.py -q`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_get_report_project_returns_real_template_asset_summary -q`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py::test_generation_preflight_prefers_backend_compiled_plan -q`
- `/Users/leon/opt/anaconda3/bin/python scripts/generate_py_file_index.py`
- `/Users/leon/opt/anaconda3/bin/python -m isort app/api/routes/report_projects.py reporting/projects/plan.py tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py`
- `/Users/leon/opt/anaconda3/bin/python -m black app/api/routes/report_projects.py reporting/projects/plan.py tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py`
- `/Users/leon/opt/anaconda3/bin/python -m ruff check app/api/routes/report_projects.py reporting/projects/plan.py tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py`
- `/Users/leon/opt/anaconda3/bin/python -m black --check app/api/routes/report_projects.py reporting/projects/plan.py tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py`
- `/Users/leon/opt/anaconda3/bin/python -m isort --check-only app/api/routes/report_projects.py reporting/projects/plan.py tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py`
- `/Users/leon/opt/anaconda3/bin/python -m mypy app/api/routes/report_projects.py reporting/projects/plan.py`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_project_plan.py tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py tests/unit/test_report_project_chart_generation.py tests/unit/test_report_project_table_generation.py tests/unit/test_ppt_template_projection.py tests/unit/test_word_projection.py -q`
- `node --check app/web/static/js/templates.js`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py -q`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py::test_generation_preflight_surfaces_prioritized_task_queue_and_evidence_samples -q`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py::test_report_generation_surfaces_current_issue_settings_bar tests/unit/test_report_template_workbench_frontend.py::test_report_generation_delivery_check_card_and_repair_return_path -q`

## Current Result

- Formatting, lint, targeted mypy, and broader focused report-project regression checks passed.
- Broader focused pytest result: 132 passed, 22 warnings.
- Frontend JS syntax check passed.
- Template workbench frontend static regression result: 59 passed.
