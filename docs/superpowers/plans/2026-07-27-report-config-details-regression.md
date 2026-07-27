# Report Configuration Detail Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore readable selected-placeholder details at the top of the unified report configuration editor.

**Architecture:** Preserve the current single YAML/Markdown data contract. Replace the editor shell's incorrect two-row grid allocation with a column layout, then retain the detail-card renderer and collapsible low-frequency sections.

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
