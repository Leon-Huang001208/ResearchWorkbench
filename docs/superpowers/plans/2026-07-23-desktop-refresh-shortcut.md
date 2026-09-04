# Desktop Workbench Refresh Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let developers reload the Research Workbench desktop Web Workbench with `F5`, `Cmd+R`, or `Ctrl+R` without closing the Tauri window or restarting the Python sidecar.

**Architecture:** Add one document-level `keydown` handler inside the existing Workbench `DOMContentLoaded` initializer in `app/web/static/js/app.js`. The handler intercepts only `F5` and `Ctrl`/`Cmd` + `R`, suppresses the WebView default action, then performs a normal `window.location.reload()`. Update the cache-busted module URL, static regression coverage, and user-facing desktop documentation; do not add Tauri Rust, native-menu, or sidecar changes.

**Tech Stack:** Vanilla ES modules, FastAPI/Jinja templates, pytest static regression tests, Playwright MCP verification, Tauri WebView.

---

## File structure

| File | Change responsibility |
|---|---|
| `app/web/static/js/app.js` | Register the workbench-wide refresh keyboard handler during initialization. |
| `app/web/templates/index.html` | Bump the `app.js` cache query string so live WebViews fetch the new handler after a page reload. |
| `tests/unit/test_desktop_shell_scaffold.py` | Assert the shortcut wiring is present in the Workbench entry point and uses the new module version. |
| `tests/unit/test_live_monitor_ui_static.py` | Update the pre-existing `app.js` cache-version expectation. |
| `tests/unit/test_asset_kline_interaction.py` | Update the pre-existing `app.js` cache-version expectation. |
| `docs/desktop_packaging.md` | Explain the supported refresh shortcuts and their sidecar/window boundaries. |
| `docs/modules/app_web.md` | Record the new Workbench-wide keyboard behavior. |
| `docs/FILE_GUIDE.md` | Describe `app.js` as owning the Workbench refresh shortcut. |
| `docs/CHANGELOG.md` | Add a user-visible Unreleased entry. |
| `.ai/reports/test_report_rwb-auto-011-00.md` | Record changed files, commands, outcomes, skips, and residual risk. |
| `.ai/progress/progress_rwb-auto-011-00.md` | Record task progress and gate outcomes. |
| `.ai/progress/progress.md` | Append the current task’s progress summary. |
| `.ai/tasks/task_rwb_auto_011.json` | Track this task from `doing` to `done` only after every mandatory gate passes. |

### Task 1: Establish a failing static regression test

**Files:**
- Modify: `tests/unit/test_desktop_shell_scaffold.py:264-367`
- Modify: `tests/unit/test_live_monitor_ui_static.py:103-108`
- Modify: `tests/unit/test_asset_kline_interaction.py:35-40`

- [ ] **Step 1: Add a focused desktop refresh-shortcut assertion**

Append the following test after `test_desktop_workbench_uses_phase_one_visual_baseline` in `tests/unit/test_desktop_shell_scaffold.py`:

```python
def test_desktop_workbench_refresh_shortcuts_reload_the_page():
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "document.addEventListener('keydown'" in js
    assert "event.key === 'F5'" in js
    assert "event.ctrlKey || event.metaKey" in js
    assert "event.key.toLowerCase() === 'r'" in js
    assert "event.preventDefault()" in js
    assert "window.location.reload()" in js
    assert "app.js?v=20260723refresh1" in html
```

Update the three existing stale cache-version assertions to use the same version:

```python
assert "app.js?v=20260723refresh1" in html
assert "/static/js/app.js?v=20260723refresh1" in template
assert "/static/js/app.js?v=20260723refresh1" in index_source
```

- [ ] **Step 2: Run the focused tests and verify the intended red state**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest \
  tests/unit/test_desktop_shell_scaffold.py::test_desktop_workbench_refresh_shortcuts_reload_the_page \
  tests/unit/test_live_monitor_ui_static.py::test_live_monitor_cache_versions_are_bumped \
  tests/unit/test_asset_kline_interaction.py::test_kline_static_module_versions_are_bumped \
  -v
```

Expected: FAIL because `app.js` does not yet register the refresh handler and `index.html` still references the prior `app.js` query-string version.

- [ ] **Step 3: Commit the red test only if the repository workflow permits intermediate commits**

```bash
git add tests/unit/test_desktop_shell_scaffold.py tests/unit/test_live_monitor_ui_static.py tests/unit/test_asset_kline_interaction.py
git commit -m "test: cover desktop refresh shortcuts"
```

Expected: a commit containing only the intentionally failing regression test and consistent cache-version expectations. If the project requires only green commits, do not commit at this point; carry the test into Task 2.

### Task 2: Implement the minimum workbench refresh handler

**Files:**
- Modify: `app/web/static/js/app.js:312-367`
- Modify: `app/web/templates/index.html:2241`
- Test: `tests/unit/test_desktop_shell_scaffold.py:264-367`
- Test: `tests/unit/test_live_monitor_ui_static.py:103-108`
- Test: `tests/unit/test_asset_kline_interaction.py:35-40`

- [ ] **Step 1: Add a document-level refresh handler within the existing initializer**

Immediately after `initNavigationCuration();` in the existing `DOMContentLoaded` callback in `app/web/static/js/app.js`, add:

```javascript
    document.addEventListener('keydown', (event) => {
        const isFunctionRefresh = event.key === 'F5';
        const isModifierRefresh =
            (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'r';

        if (!isFunctionRefresh && !isModifierRefresh) {
            return;
        }

        event.preventDefault();
        window.location.reload();
    });
```

Do not add input-focus exclusions: the intended behavior is browser-style refresh even when an input has focus. Do not modify existing Escape, Enter, arrow-key, click, or scroll listeners.

- [ ] **Step 2: Bump only the `app.js` cache version**

In `app/web/templates/index.html`, replace:

```html
<script type="module" src="/static/js/app.js?v=20260722flowfix"></script>
```

with:

```html
<script type="module" src="/static/js/app.js?v=20260723refresh1"></script>
```

Do not change the stylesheet cache version or any other static module URL.

- [ ] **Step 3: Run the focused regression tests and verify the green state**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest \
  tests/unit/test_desktop_shell_scaffold.py::test_desktop_workbench_refresh_shortcuts_reload_the_page \
  tests/unit/test_live_monitor_ui_static.py::test_live_monitor_cache_versions_are_bumped \
  tests/unit/test_asset_kline_interaction.py::test_kline_static_module_versions_are_bumped \
  -v
```

Expected: PASS. The static tests now prove both supported shortcut branches, default-action suppression, page reload, and the synchronized module cache version.

- [ ] **Step 4: Use Playwright MCP to verify page-level behavior**

1. Start the local FastAPI development server with reload enabled if it is not already running:

   ```bash
   scripts/desktop/run_backend.sh --host 127.0.0.1 --port 8765 --reload
   ```

2. Navigate Playwright MCP to `http://127.0.0.1:8765`.
3. Confirm the Workbench root page loads.
4. Trigger `F5`, then verify the root Workbench page is available again after navigation.
5. Trigger `Meta+R` on macOS or `Control+R` on another platform, then verify the root Workbench page is available again after navigation.
6. Capture a screenshot or browser-verification note for the task report.

Expected: both shortcut paths reload the page; the desktop shell/window and backend process remain running.

- [ ] **Step 5: Commit the implementation and tests**

```bash
git add \
  app/web/static/js/app.js \
  app/web/templates/index.html \
  tests/unit/test_desktop_shell_scaffold.py \
  tests/unit/test_live_monitor_ui_static.py \
  tests/unit/test_asset_kline_interaction.py
git commit -m "feat: add desktop workbench refresh shortcuts"
```

Expected: one focused green commit for the UI behavior and its regression coverage.

### Task 3: Synchronize user and module documentation

**Files:**
- Modify: `docs/desktop_packaging.md:4-12`
- Modify: `docs/modules/app_web.md:33-49`
- Modify: `docs/FILE_GUIDE.md:110`
- Modify: `docs/CHANGELOG.md:8-16`

- [ ] **Step 1: Document the desktop shortcut boundary in packaging guidance**

Add the following bullet below the existing `Current Shape` list in `docs/desktop_packaging.md`:

```markdown
- The Workbench supports `F5` on every platform, `Cmd+R` on macOS, and `Ctrl+R` on Windows/Linux to reload the current WebView page without closing the Tauri window or restarting the Python sidecar.
```

- [ ] **Step 2: Document the interaction in the app/web module guide**

Add this bullet to the `app/web/static/*.js` purpose list in `docs/modules/app_web.md`:

```markdown
- The Workbench entry module handles `F5`, macOS `Cmd+R`, and Windows/Linux `Ctrl+R` as full-page refresh shortcuts; this reloads the WebView page only and does not restart the Tauri shell or backend sidecar.
```

- [ ] **Step 3: Refine the file-guide entry without changing unrelated rows**

Replace the existing `app.js` description row in `docs/FILE_GUIDE.md`:

```markdown
| `app/web/static/js/app.js` | 主入口模块：导航路由、SSE 连接、全局状态管理 |
```

with:

```markdown
| `app/web/static/js/app.js` | 主入口模块：导航路由、SSE 连接、全局状态管理与 Workbench 刷新快捷键 |
```

- [ ] **Step 4: Add one Unreleased changelog entry**

Under the first `### Added` heading in `docs/CHANGELOG.md`, add:

```markdown
- **桌面工作台刷新快捷键**：支持所有平台 `F5`、macOS `Cmd+R` 与 Windows/Linux `Ctrl+R` 刷新当前 Workbench 页面，无需退出 Tauri 窗口或重启 Python sidecar。
```

- [ ] **Step 5: Check the documentation diff**

Run:

```bash
git diff --check -- docs/desktop_packaging.md docs/modules/app_web.md docs/FILE_GUIDE.md docs/CHANGELOG.md
```

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 6: Commit documentation synchronization**

```bash
git add docs/desktop_packaging.md docs/modules/app_web.md docs/FILE_GUIDE.md docs/CHANGELOG.md
git commit -m "docs: document desktop refresh shortcuts"
```

Expected: one documentation-only commit with no source or test changes.

### Task 4: Record task evidence and run all mandatory completion gates

**Files:**
- Create: `.ai/tasks/task_rwb_auto_011.json`
- Create: `.ai/reports/test_report_rwb-auto-011-00.md`
- Create: `.ai/progress/progress_rwb-auto-011-00.md`
- Modify: `.ai/progress/progress.md`
- Modify: `.ai/tasks/task_rwb_auto_011.json`

- [ ] **Step 1: Create the task record with status `doing` before completion gates**

Create `.ai/tasks/task_rwb_auto_011.json` with:

```json
{
  "tasks": [
    {
      "id": "rwb-auto-011-00",
      "title": "Add desktop Workbench refresh shortcuts",
      "description": "Add F5, Cmd+R, and Ctrl+R page refresh handling to the Tauri-hosted Web Workbench without restarting the desktop window or Python sidecar.",
      "priority": "medium",
      "dependencies": [],
      "success_criteria": [
        "F5 refreshes the Workbench on every platform",
        "Cmd+R refreshes the Workbench on macOS",
        "Ctrl+R refreshes the Workbench on Windows/Linux",
        "Refresh does not restart the Tauri window or Python sidecar",
        "Static regression coverage and browser verification pass",
        "Documentation and completion evidence are synchronized"
      ],
      "verification_commands": [
        "ruff check .",
        "black . --check",
        "isort . --check-only",
        "mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/",
        "python -m pytest tests/ -v",
        "python scripts/generate_py_file_index.py",
        "python scripts/check_task_completion.py",
        "python scripts/check_doc_sync.py"
      ],
      "status": "doing",
      "started_at": "2026-07-23"
    }
  ],
  "metadata": {
    "project_name": "Research Workbench",
    "task_set_id": "rwb-auto-011",
    "task_set_description": "RWB-AUTO-011: desktop Workbench refresh shortcuts",
    "status": "doing",
    "started_at": "2026-07-23",
    "total_tasks": 1
  }
}
```

- [ ] **Step 2: Run required source-quality and test commands**

Run each command and capture its exit code and significant output for the report:

```bash
ruff check .
black . --check
isort . --check-only
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
/Users/leon/opt/anaconda3/bin/python -m pytest tests/ -v
python scripts/generate_py_file_index.py
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
```

Expected: every command exits with code 0. If any command fails due to a pre-existing repository issue, do not mark the task done; create the required blocking report and leave the task status `blocked` or `doing` according to the blocking policy.

- [ ] **Step 3: Create the audit report after commands finish**

Create `.ai/reports/test_report_rwb-auto-011-00.md` with these completed sections and factual command outcomes:

```markdown
# Test Report: rwb-auto-011-00

## Task ID

- rwb-auto-011-00

## Changed Source Files

- `app/web/static/js/app.js`
- `app/web/templates/index.html`

## Changed Test Files

- `tests/unit/test_desktop_shell_scaffold.py`
- `tests/unit/test_live_monitor_ui_static.py`
- `tests/unit/test_asset_kline_interaction.py`

## Changed Documentation

- `docs/desktop_packaging.md`
- `docs/modules/app_web.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`

## Commands Run

- List every required command with its actual exit status and summary.

## Browser Verification

- Record the actual Playwright MCP URL, shortcut events tested, observed reload behavior, and screenshot artifact or explicit reason no screenshot was captured.

## Skipped Tests

- `None` if none were skipped; otherwise list each skipped command/test and its actual reason.

## Remaining Risk

- Page-level browser verification covers the shared WebView JavaScript path. It does not verify a native Tauri menu because this feature intentionally does not add one.

## Final Test Decision

- `Passed` only when every mandatory completion gate exited with code 0; otherwise `Blocked` with the failing command and reason.
```

- [ ] **Step 4: Update both progress records with factual evidence**

Create `.ai/progress/progress_rwb-auto-011-00.md` and append a matching entry to `.ai/progress/progress.md` that list:

```markdown
## rwb-auto-011-00 — Desktop Workbench refresh shortcuts

- Added F5, Cmd+R, and Ctrl+R page refresh handling in `app/web/static/js/app.js`.
- Bumped the `app.js` cache version in `app/web/templates/index.html`.
- Added static shortcut regression coverage and synchronized existing cache-version assertions.
- Updated desktop, module, file-guide, and changelog documentation.
- Browser verification: record only the observed Playwright result.
- Completion gates: record only actual command outcomes.
- Remaining risk: record the actual remaining risk, or `None known` only if supported by the verification evidence.
```

- [ ] **Step 5: Mark the task `done` only after all gates have passed**

In `.ai/tasks/task_rwb_auto_011.json`, change only:

```json
"status": "doing"
```

to:

```json
"status": "done"
```

and update the metadata status to `done`. Do not edit the task title, description, success criteria, or verification command list. If any required gate failed, set the task status to `blocked` instead and create `.ai/reports/blocking_report_rwb-auto-011-00.md` with the command, full error, required human action, and safe next step.

- [ ] **Step 6: Commit task evidence only when completion gates passed**

```bash
git add \
  .ai/tasks/task_rwb_auto_011.json \
  .ai/reports/test_report_rwb-auto-011-00.md \
  .ai/progress/progress_rwb-auto-011-00.md \
  .ai/progress/progress.md \
  docs/generated/py_file_index.md
git commit -m "chore: record desktop refresh shortcut verification"
```

Expected: evidence and task status accurately represent actual gate outcomes. Do not include `docs/generated/py_file_index.md` if `generate_py_file_index.py` did not modify it.

## Plan self-review

- **Spec coverage:** Task 2 implements `F5`, `Cmd+R`, `Ctrl+R`, prevents default actions, reloads only the page, and updates the module cache URL. Task 3 documents desktop window and sidecar boundaries. Task 1/2 supply static regression coverage and browser verification. Task 4 supplies mandatory task, report, progress, and verification evidence.
- **Scope:** The plan does not add native Tauri menus, global shortcuts, HMR, worker reload, or sidecar/process changes.
- **Consistency:** All cache-version assertions and the template URL use `20260723refresh1`. The JavaScript implementation and static test agree on exact event properties and `window.location.reload()`.
- **Placeholder scan:** No incomplete requirements, unspecified commands, or undefined implementation interfaces remain.
