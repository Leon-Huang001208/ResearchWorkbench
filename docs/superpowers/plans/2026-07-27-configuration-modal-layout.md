# Configuration Modal Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild configuration modal information hierarchy so account pools are compact tables, empty pools have a clear next action, and advanced settings are grouped parameter lists without changing any configuration behavior.

**Architecture:** Keep `configuration.js` as the sole renderer of section-specific modal forms and preserve every existing input `name`, data attribute, save/test handler, lock application, and secret-state path. Add presentational hooks only inside the form markup; use `configuration.css` for the desktop table, small-screen stacked rows, inline empty state, and advanced-settings navigation/list layout. Static frontend tests will protect the DOM hooks and existing safety contracts.

**Tech Stack:** Vanilla JavaScript ES modules, HTML template strings, CSS Grid/Flexbox, pytest static frontend contracts, Node syntax check.

---

## File structure

- `app/web/static/js/configuration.js` — owns modal form markup, dynamic account rows, empty-state lifecycle, locking, field serialization, and modal events. Add structural class/data hooks here; do not change payload code.
- `app/web/static/configuration.css` — owns the final configuration-modal overrides. Add all layout rules here, after the current modal-refinement rules, so legacy `style.css` decoration cannot win by source order.
- `tests/unit/test_configuration_frontend_static.py` — validates both the new visual structure hooks and the non-negotiable save/test/lock/secret contracts.
- `docs/modules/app_web.md` — documents the account-table, advanced-list, and empty-state behavior for future UI work.

### Task 1: Lock down the new modal layout contracts

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: Write the failing structural tests**

  Add this test after `test_configuration_refinement_modal_save_action_and_collection_layout_hooks`:

  ```python
  def test_configuration_modal_layout_uses_compact_collections_and_advanced_groups():
      source = CONFIGURATION_JS.read_text(encoding="utf-8")
      stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")
      render_source = _configuration_function(source, "renderModalForm")

      for section in ("zhiqiu", "ifind", "web_search"):
          assert f'config-collection config-collection--{section}' in render_source
      assert 'config-collection-table' in render_source
      assert 'config-empty-collection--inline' in source
      assert 'data-advanced-group="runtime"' in render_source
      assert 'data-advanced-group="llm"' in render_source
      assert 'data-advanced-group="chunking"' in render_source
  ```

- [ ] **Step 2: Run the new test to prove the current renderer lacks the hooks**

  Run:

  ```bash
  pytest tests/unit/test_configuration_frontend_static.py::test_configuration_modal_layout_uses_compact_collections_and_advanced_groups -q
  ```

  Expected: FAIL because `renderModalForm()` currently emits `config-dynamic-list` directly and advanced fields have no `data-advanced-group` grouping.

- [ ] **Step 3: Preserve safety assertions adjacent to the new contract**

  Extend the same test with these explicit assertions, so a visual rewrite cannot bypass current behavior:

  ```python
      assert 'applyEnvironmentLocks(form, section);' in render_source
      assert 'createSecretControl(password)' in source
      assert 'setAttribute(\'role\', \'status\')' in source
      assert 'filterEnvironmentLockedPayload' in source
  ```

- [ ] **Step 4: Commit the failing-spec tests**

  ```bash
  git add tests/unit/test_configuration_frontend_static.py
  git commit -m "test(config): specify compact modal layouts"
  ```

### Task 2: Add semantic collection and advanced-settings markup

**Files:**
- Modify: `app/web/static/js/configuration.js:439-582, 1659-1745`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: Render collections as one table-like region without changing row creation**

  In each `zhiqiu`, `ifind`, and `web_search` branch of `renderModalForm()`, wrap the existing labels and list with section-specific hooks. Keep the existing list IDs and row classes unchanged. The target shape is:

  ```js
  <section class="config-collection config-collection--ifind" aria-labelledby="config-ifind-accounts-heading">
      <div class="config-subsection-header">
          <h4 id="config-ifind-accounts-heading"><i class="codicon codicon-organization"></i>账号</h4>
          <button type="button" class="secondary-btn" data-add-ifind-account>新增账号</button>
      </div>
      <div class="config-collection-table" role="group" aria-label="iFinD 账号列表">
          <div class="config-row-labels config-ifind-labels" aria-hidden="true">...</div>
          <div id="config-ifind-account-list" class="config-dynamic-list"></div>
      </div>
  </section>
  ```

  Do not change `createZhiqiuAccountRow`, `createIfindAccountRow`, `createWebSearchKeyRow`, their `data-field` values, account list IDs, `rowOriginalNames`, or the calls to `applyEnvironmentLocks`.

- [ ] **Step 2: Give the existing empty-state node an inline presentation hook**

  Change only the class supplied to `element()` in `createEmptyCollectionState()`:

  ```js
  const state = element('p', 'config-empty-collection config-empty-collection--inline', message);
  state.setAttribute('role', 'status');
  ```

  Keep placement after the existing add button and keep `renderEmptyCollectionState`, `restoreEmptyCollectionState`, and `syncEmptyCollectionState` call paths intact.

- [ ] **Step 3: Replace advanced field flattening with named visual groups**

  In the `advanced` `renderModalForm()` branch, retain every current input name and option. Wrap them in these groups:

  ```js
  <div class="config-advanced-settings">
      <nav class="config-advanced-nav" aria-label="高级配置分类">
          <a href="#config-advanced-runtime">运行与日志</a>
          <a href="#config-advanced-llm">LLM 处理</a>
          <a href="#config-advanced-chunking">文本分块</a>
      </nav>
      <div class="config-advanced-groups">
          <section id="config-advanced-runtime" class="config-advanced-group" data-advanced-group="runtime">...</section>
          <section id="config-advanced-llm" class="config-advanced-group" data-advanced-group="llm">...</section>
          <section id="config-advanced-chunking" class="config-advanced-group" data-advanced-group="chunking">...</section>
      </div>
  </div>
  ```

  The runtime group contains `log_level` and `log_dir`; LLM contains `llm_max_workers` and `llm_max_retries`; chunking contains `chunk_size`, `chunk_overlap`, and `long_text_threshold`. Leave disabled controls disabled after `applyEnvironmentLocks(form, section)`; do not replace controls with text nodes.

- [ ] **Step 4: Run the focused layout test**

  Run:

  ```bash
  pytest tests/unit/test_configuration_frontend_static.py::test_configuration_modal_layout_uses_compact_collections_and_advanced_groups -q
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the semantic markup update**

  ```bash
  git add app/web/static/js/configuration.js tests/unit/test_configuration_frontend_static.py
  git commit -m "feat(config): structure modal collections and settings"
  ```

### Task 3: Implement the compact account, empty-state, and advanced-list styles

**Files:**
- Modify: `app/web/static/configuration.css:1504-1678`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: Write the failing CSS contract**

  Add this test:

  ```python
  def test_configuration_modal_layout_styles_compact_tables_and_responsive_advanced_groups():
      stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")

      assert re.search(r'\.config-collection-table\s*\{[^}]*border:', stylesheet, re.DOTALL)
      assert re.search(r'\.config-collection-table\s+\.config-dynamic-row\s*\{[^}]*border-radius:\s*0', stylesheet, re.DOTALL)
      assert re.search(r'\.config-empty-collection--inline\s*\{[^}]*display:\s*flex', stylesheet, re.DOTALL)
      assert re.search(r'\.config-advanced-settings\s*\{[^}]*grid-template-columns:', stylesheet, re.DOTALL)
      assert '@media (max-width: 720px)' in stylesheet
  ```

- [ ] **Step 2: Run the test to verify the style selectors are absent**

  Run:

  ```bash
  pytest tests/unit/test_configuration_frontend_static.py::test_configuration_modal_layout_styles_compact_tables_and_responsive_advanced_groups -q
  ```

  Expected: FAIL because the current rows retain card padding/radius and no advanced-settings layout exists.

- [ ] **Step 3: Add desktop compact-table rules at the end of the modal refinement block**

  Add rules equivalent to:

  ```css
  .config-collection-table { overflow: hidden; border: 1px solid var(--border-primary); border-radius: 10px; }
  .config-collection-table .config-row-labels { margin: 0; padding: 8px 12px; background: var(--bg-elevated); }
  .config-collection-table .config-dynamic-list { gap: 0; }
  .config-collection-table .config-dynamic-row { min-height: 48px; padding: 8px 12px; border: 0; border-top: 1px solid var(--border-soft); border-radius: 0; background: transparent; }
  .config-collection-table .config-dynamic-field > span:first-child { display: none; }
  .config-collection-table :is(input, .config-secret-control, .config-secret-action) { min-height: 34px; }
  .config-collection-table .config-remove-row { border: 0; background: transparent; color: var(--danger); }
  ```

  Keep focus styles visible by defining a `:focus-within` background/border treatment rather than reintroducing colored card shadows. Preserve `config-dynamic-row-locked` and the dynamic lock-message grid behavior.

- [ ] **Step 4: Add empty-state and advanced-list rules**

  Add these layout rules, using existing CSS variables rather than hard-coded page colors:

  ```css
  .config-empty-collection--inline { display: flex; margin: 10px 0 0; padding: 10px 12px; }
  .config-advanced-settings { display: grid; grid-template-columns: 164px minmax(0, 1fr); border: 1px solid var(--border-primary); border-radius: 10px; overflow: hidden; }
  .config-advanced-nav { padding: 8px; background: var(--bg-elevated); border-right: 1px solid var(--border-soft); }
  .config-advanced-nav a { display: block; padding: 8px 9px; color: var(--text-secondary); text-decoration: none; }
  .config-advanced-group { padding: 0 14px; scroll-margin-top: 12px; }
  .config-advanced-group > label { display: grid; grid-template-columns: minmax(0, 1fr) minmax(96px, 0.42fr); align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--border-soft); }
  ```

  Include a `@media (max-width: 720px)` override that makes collection rows one-column with field labels visible and changes `.config-advanced-settings` to one column with a horizontal, wrap-safe navigation. Do not hide save, test, cancel, status, lock note, or field labels at 200% zoom.

- [ ] **Step 5: Run the CSS contract**

  Run:

  ```bash
  pytest tests/unit/test_configuration_frontend_static.py::test_configuration_modal_layout_styles_compact_tables_and_responsive_advanced_groups -q
  ```

  Expected: PASS.

- [ ] **Step 6: Commit the CSS implementation**

  ```bash
  git add app/web/static/configuration.css tests/unit/test_configuration_frontend_static.py
  git commit -m "feat(config): compact modal information layout"
  ```

### Task 4: Document and verify the completed redesign

**Files:**
- Modify: `docs/modules/app_web.md:44-54, 100-108`
- Test: `tests/unit/test_configuration_service.py`
- Test: `tests/unit/test_configuration_frontend_static.py`

- [ ] **Step 1: Update the configuration UI documentation**

  Add a bullet stating that account and Key pools render as compact tables on desktop and labelled stacked rows on narrow screens; empty pools show an inline next-action state; advanced settings use a category navigation plus grouped parameter list. State explicitly that visual grouping does not change startup-environment locks or secret-value handling.

- [ ] **Step 2: Run all configuration regression tests and syntax check**

  Run:

  ```bash
  pytest tests/unit/test_configuration_service.py tests/unit/test_configuration_frontend_static.py -q
  node --check app/web/static/js/configuration.js
  git diff --check HEAD~3..HEAD
  ```

  Expected: all tests PASS, Node exits 0, and the diff check has no output. If the exact commit count differs, run `git diff --check` instead; do not use a broad unrelated test failure to modify this UI change.

- [ ] **Step 3: Perform visual checks in the local app**

  Verify these three states without entering or exposing a real secret:

  1. A populated 知丘账号池 has one table container, aligned rows, low-emphasis remove actions, and a visible fixed footer.
  2. An empty iFinD 账号池 has no empty table header and no reserved blank table height; the add button and inline guidance remain visible before connection settings.
  3. 高级配置 shows the three group anchors, preserves locked disabled controls and accessible explanations, and remains usable at the narrow-screen breakpoint.

- [ ] **Step 4: Commit documentation and final tests**

  ```bash
  git add docs/modules/app_web.md
  git commit -m "docs(config): describe compact modal layout"
  ```
