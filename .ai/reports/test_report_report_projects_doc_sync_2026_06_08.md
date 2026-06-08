# Test Report: report_projects 文档同步

## Task Info

- Task ID: report-projects-doc-sync-2026-06-08
- Date: 2026-06-08
- Affected subsystem: app/api, app/web, reporting, report_projects, cognitive_agents, data_layer, signal_lab, docs
- User request: 阅读 Markdown 并按 `CLAUDE.md` 规范更新长期未同步的 Markdown 文档。

## Documentation Reads

- `CLAUDE.md`
- `.claude/rules/00-core-rules.md`
- `.claude/rules/01-task-workflow.md`
- `.claude/rules/03-doc-sync-policy.md`
- `.claude/rules/06-final-response.md`
- `.claude/rules/project-practices/007-auto-update-docs.md`
- `docs/DEVELOPMENT_MAP.md`
- `docs/ARCHITECTURE.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/modules/app_api.md`
- `docs/modules/app_web.md`
- `docs/modules/reporting.md`
- `docs/modules/cognitive_agents.md`
- `docs/modules/data_layer_crawlers.md`
- `docs/modules/data_layer_repositories.md`
- `docs/modules/signal_lab.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_STORAGE.md`
- Scanned all Markdown files for headings and report/template-related references.

## Changed Docs

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_MAP.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/modules/app_api.md`
- `docs/modules/app_web.md`
- `docs/modules/reporting.md`
- `docs/modules/cognitive_agents.md`
- `docs/modules/data_layer_crawlers.md`
- `docs/modules/data_layer_repositories.md`
- `docs/modules/signal_lab.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_STORAGE.md`
- `.ai/progress/progress.md`
- `.ai/progress/progress_report_projects_doc_sync.md`
- `.ai/reports/test_report_report_projects_doc_sync_2026_06_08.md`

## Sync Summary

- Documented `report_projects` source persistence, config-driven render, generated DOCX preview, run-log metadata, and chart embedding API behavior.
- Documented `reporting/projects/generation.py` and `reporting/projects/chart_generation.py` responsibilities.
- Documented template workbench behavior for YAML/Markdown Prompt source switching, read-only edit flow, project-backed source saves, preview loading, and upload toolbar placement.
- Documented current `华安ETF周报` config model: `placeholders`, embedded retrieval Query prompt templates, and chart replacement rules.
- Documented the follow-up full-gate cleanup: protocol-based workflow runner factory, agent view metadata JSONB unpacking, CNINFO attachment metadata, event label classification type handling, and config/worksheet type narrowing in report generation.

## Commands Run

- `rg --files -g '*.md' -g 'CLAUDE.md'`
- `git status --short`
- `sed` reads for required CLAUDE rules and related docs
- `rg` scans across Markdown files for report/template references

## Verification Status

- `python scripts/generate_py_file_index.py` — passed, regenerated `docs/generated/py_file_index.md`.
- `python scripts/check_doc_sync.py` — passed.
- `python scripts/check_task_completion.py` — passed.
- `python -m pytest tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py tests/unit/test_report_project_chart_generation.py -q` — 30 passed, 22 warnings.
- `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/` — passed across 369 source files.
- `python -m pytest tests/unit/test_asset_kline_interaction.py::test_kline_static_module_versions_are_bumped -q` — passed.
- `python -m pytest tests/unit/test_asset_kline_interaction.py tests/unit/test_report_projects_api.py tests/unit/test_report_project_chart_generation.py tests/unit/test_asset_agent_committee_service.py tests/unit/test_agent_view_repository.py -q` — 26 passed, 22 warnings.
- `ruff check .` — passed.
- `black . --check` — passed.
- `isort . --check-only` — passed.
- `python -m pytest tests/ -v` — 1680 passed, 4 skipped, 33 warnings.

## Not Run

- None.

## Remaining Risks

- None identified for the requested remaining-risk cleanup.

## Worktree Note

- The repository still contains unstaged task changes plus pre-existing/user changes. They were preserved and not reverted.
