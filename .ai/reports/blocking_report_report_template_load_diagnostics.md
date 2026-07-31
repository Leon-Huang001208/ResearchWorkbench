# Blocking Report: report-template-load-diagnostics

## Current Task

- Task ID: ad-hoc-report-template-load-diagnostics
- Task name: 报告生产模板页加载诊断
- Date: 2026-07-24

## Completed Work

- 恢复后的 `华安ETF周报` 已在报告生产页显示。
- 报告项目扫描现在会保留有效项目，并返回不安全路径、缺少活动模板和损坏 `project.yaml` 的稳定诊断。
- 模板工作台会区分单源失败、双源失败和真实空库；双源失败不再显示“暂无模板”。
- 浏览器已验证正常状态、单源 503 和双源 503 降级状态。
- 代码审查发现的详情页和上传刷新回归、项目资产路径泄露均已修复并复审通过。

## Blocking Reason

项目规定的全量质量门禁未通过，但失败均在本次范围之外：

- `ruff check .`：31 个既有错误，涉及 `app/api/routes/assets.py`、`event_ingestion.py`、`ingest.py`、`pipeline.py`、旧测试等。
- `mypy ...`：51 个既有类型错误，涉及 observability、PPT renderer、builder、非本次 API 路由等。
- `python -m pytest tests/ -v`：恢复的华安图表工作簿与历史测试固定预期不符，历史生成 DOCX fixture 缺失，另有静态前端、CNStock 和 Wind 测试的既有失败。

## Evidence

- Targeted manager diagnostics: 6 passed.
- Targeted list API diagnostics: 2 passed, 58 deselected.
- Targeted frontend diagnostics: 3 passed, 58 deselected.
- Scoped Ruff/Black/isort: passed.
- `node --check app/web/static/js/templates.js`: passed.
- `python scripts/generate_py_file_index.py`: passed.
- `python scripts/check_doc_sync.py`: passed.
- `python scripts/check_task_completion.py`: passed.

## Required Human Action

1. Decide whether the unrelated repository-wide Ruff, mypy and test failures should be assigned to their owning tasks.
2. Decide whether the restored `华安ETF周报/data/周报图表.xlsx` should be accepted as the current test fixture or whether chart tests must be updated for its real contents.
3. Supply or approve recovery of the historical generated DOCX fixtures if the preview-normalization tests must remain fixture-based.

## Safe Next Step After Unblocking

- Resolve the owning repository-wide failures, rerun all required gates, then update the appropriate task status.

## Files Changed Before Blocking

- `reporting/projects/project_manager.py`
- `app/api/routes/report_projects.py`
- `app/web/static/js/templates.js`
- `app/web/templates/index.html`
- `app/web/static/style.css`
- `tests/unit/test_report_project_manager.py`
- `tests/unit/test_report_projects_api.py`
- `tests/unit/test_report_template_workbench_frontend.py`
- `docs/modules/reporting.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `.ai/reports/test_report_report_template_load_diagnostics.md`
