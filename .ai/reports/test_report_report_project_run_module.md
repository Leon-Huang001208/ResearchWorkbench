Task ID: report_project_run_module

Changed source files:
- `reporting/projects/run.py`
- `app/api/routes/report_projects.py`

Changed test files:
- `tests/unit/test_report_projects_api.py`

Changed docs:
- `docs/superpowers/plans/2026-07-07-report-project-run-module.md`
- `docs/modules/reporting.md`
- `docs/modules/app_api.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

Commands run:
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_report_project_run_service_renders_word_project -q`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_report_project_run_service_renders_word_project tests/unit/test_report_projects_api.py::test_render_report_project_writes_to_project_generated_dir tests/unit/test_report_projects_api.py::test_render_ppt_report_project_writes_pptx_to_generated_dir tests/unit/test_report_projects_api.py::test_render_report_project_generates_from_config_and_writes_generation_log -q`
- `/Users/leon/opt/anaconda3/bin/python scripts/generate_py_file_index.py`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py tests/unit/test_report_project_manager.py tests/unit/test_report_project_chart_generation.py tests/unit/test_report_project_table_generation.py tests/unit/test_ppt_template_projection.py tests/unit/test_word_projection.py -q`
- `isort app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py`
- `black app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py`
- `ruff check app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py`
- `black --check app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py`
- `isort --check-only app/api/routes/report_projects.py reporting/projects/run.py tests/unit/test_report_projects_api.py`
- `mypy app/api/routes/report_projects.py reporting/projects/run.py`
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py::test_get_report_project_returns_ppt_template_placeholders tests/unit/test_report_projects_api.py::test_report_project_run_service_renders_word_project tests/unit/test_report_projects_api.py::test_render_report_project_writes_to_project_generated_dir tests/unit/test_report_projects_api.py::test_render_ppt_report_project_writes_pptx_to_generated_dir tests/unit/test_report_projects_api.py::test_render_report_project_generates_from_config_and_writes_generation_log -q`

Command results:
- Initial RED test failed with `ModuleNotFoundError: No module named 'reporting.projects.run'`.
- New service test passed after implementation.
- Focused render/API tests passed: 4 passed, then 5 passed after type fixes.
- `ruff check` passed.
- `black --check` passed after formatting.
- `isort --check-only` passed after sorting imports.
- Targeted `mypy` passed: no issues in `app/api/routes/report_projects.py` and `reporting/projects/run.py`.
- Python file index regenerated successfully.
- Broader focused report suite result: 78 passed, 1 failed. The failed test was `test_huaan_prompt_placeholders_use_report_level_retrieval_defaults`; it asserts the checked-in `report_projects/华安ETF周报/config/section_config.yaml` contains `type: prompt` placeholders, but the current file has none. This appears unrelated to the run seam refactor and was not changed here.

Skipped tests:
- Full repository gate (`ruff check .`, full `black --check .`, full `isort --check-only`, full `mypy ...`, full `pytest tests/ -v`, `scripts/check_task_completion.py`, `scripts/check_doc_sync.py`) was not run.

Reason for skipped tests:
- The worktree contains many unrelated pre-existing modified files. Running and fixing the full gate would risk mixing this focused report-run refactor with unrelated in-flight work. Focused checks were run on touched files and adjacent reporting tests.

Remaining risk:
- The current checked-in Huaan ETF section config does not satisfy one existing test expectation; this should be resolved separately by either restoring prompt placeholders or updating that test to match the current schema.
- Full repository gates remain unverified in this turn.

Final test decision:
- Focused implementation verified. Repository-wide completion is not claimed.
