# Report Configuration Detail Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore readable selected-placeholder details at the top of the unified report configuration editor.

**Architecture:** Preserve the current single YAML/Markdown data contract. Replace the editor shell's incorrect two-row grid allocation with a column layout. Express the A-share review as `paragraph` plus the explicit `data_template_plus_evidence_ai` mode, and dispatch that mode directly in generation.

**Tech Stack:** Vanilla CSS, vanilla JavaScript, pytest static frontend tests.

---

### Task 1: Specify the visual layout regression

**Files:**
- Modify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] Add a static test that extracts the final editor-shell CSS rule and asserts it uses `display: flex`, `flex-direction: column`, and does not use `grid-template-rows: auto minmax(0, 1fr);`. It also asserts `buildPlaceholderConfigSummaryHtml` remains the selected-detail renderer.
- [ ] Run `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q` and confirm failure before the CSS fix.

### Task 2: Restore ordered detail layout

**Files:**
- Modify: `app/web/static/style.css`
- Modify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] In the final editor-shell CSS override, use `display: flex; flex-direction: column;`; set the selected detail form to `height: auto`, `min-height: 0`, and `align-content: start`.
- [ ] Run `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q && /Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check app/web/static/js/templates.js && git diff --check` and confirm success.
- [ ] Commit only the CSS, static test, and these two planning documents.

### Task 3: Remove the obsolete composite type from the live project

**Files:**
- Modify: `tests/unit/test_report_projects_api.py`
- Modify: `report_projects/华安ETF周报/config/report_config.yaml`
- Modify: `reporting/projects/generation.py`
- Modify: `reporting/projects/plan.py`

- [ ] Change the A-share generation fixture to `type: paragraph` and `mode: data_template_plus_evidence_ai`; assert the built-in project uses the same explicit shape. Run the focused test and confirm it fails because generation still dispatches only the obsolete type.
- [ ] Dispatch the specialised A-share Excel-plus-evidence generator when `type` is `paragraph` and `mode` is `data_template_plus_evidence_ai`; update plan/default handling to use the same explicit mode.
- [ ] Run the focused generation and plan tests, then the report-project frontend/API suite. Commit the implementation and tests with the layout repair.
