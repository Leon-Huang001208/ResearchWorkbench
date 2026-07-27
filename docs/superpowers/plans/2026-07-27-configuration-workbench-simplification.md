# Configuration Workbench Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the system-configuration landing page to progress, configuration entry points, and an optional running-environment diagnostic disclosure.

**Architecture:** Keep backend snapshot and card/modal APIs unchanged. Simplify static markup and its JavaScript event surface, then scope the existing diagnostics renderer inside a native disclosure. CSS replaces large summary/card surfaces with a compact responsive workbench layout.

**Tech Stack:** HTML, vanilla JavaScript modules, CSS, pytest static frontend checks.

---

### Task 1: Specify the simplified workbench contract

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py:367-435`

- [ ] Write failing static assertions that `#config-refresh` and `[data-config-status-filter]` are absent, the environment diagnostics are inside `.config-environment-disclosure`, and `bindConfigurationEvents` contains no obsolete bindings.
- [ ] Run `pytest tests/unit/test_configuration_frontend_static.py -q` and expect a failure before implementation.
- [ ] Commit: `test(config): specify simplified workbench`.

### Task 2: Simplify markup and behavior

**Files:**
- Modify: `app/web/templates/index.html:1231-1288`
- Modify: `app/web/static/js/configuration.js:1000-1038, 1355-1525`

- [ ] Remove the refresh button, its help text, connection-status control, and status filter; retain only the progress summary.
- [ ] Wrap existing diagnostics markup in `<details class="config-environment-disclosure"><summary>运行环境</summary>…</details>`.
- [ ] Remove `setRefreshDisabled`, `refreshConfiguration`, filtering, and their event bindings; leave save/test card updates intact.
- [ ] Run `pytest tests/unit/test_configuration_frontend_static.py -q` and commit: `feat(config): simplify workbench controls`.

### Task 3: Apply compact visual hierarchy

**Files:**
- Modify: `app/web/static/configuration.css:1200-1510`

- [ ] Style the health summary as a low-height row and the disclosure as a quiet, collapsed control.
- [ ] Make cards compact (about 142px minimum height) while preserving the 3/2/1 column breakpoints.
- [ ] Verify with `node --check app/web/static/js/configuration.js`, `pytest tests/unit/test_configuration_frontend_static.py -q`, and `git diff --check`.
- [ ] Commit: `style(config): focus workbench layout`.
