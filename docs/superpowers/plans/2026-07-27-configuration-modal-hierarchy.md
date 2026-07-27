# Configuration Modal Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace crowded configuration-modal cards with compact collections and clear safe database state.

**Architecture:** Preserve the existing configuration snapshot and save/test APIs. Add a presentation-only database-state helper, simplify modal markup generated in `renderModalForm`, and use scoped CSS overrides for a shared collection/table treatment.

**Tech Stack:** Vanilla JavaScript, HTML templates created by JavaScript, CSS, pytest static frontend checks.

---

### Task 1: Define safe modal-state contracts

**Files:**
- Modify: `tests/unit/test_configuration_frontend_static.py`

- [ ] Add assertions that database rendering retains a configured-state label without assigning a secret value to `database_url`, that collection markup uses `.config-collection-table`, and that legacy nested-row card styling is not used by modal rows.
- [ ] Run `pytest tests/unit/test_configuration_frontend_static.py -q` and verify failure before the new selectors and helper exist.
- [ ] Commit the failing contract with message `test(config): define modal hierarchy contract`.

### Task 2: Render compact modal hierarchy

**Files:**
- Modify: `app/web/static/js/configuration.js`

- [ ] Add `databaseSecretPresentation(secret)` that returns only `未配置`, `已配置`, or `由启动配置管理` based on the existing `SecretState`; it must not read or construct the secret value.
- [ ] Change LLM and account collection wrappers to use `.config-collection-table`, keeping one column-label row and one list of rows.
- [ ] Add a `config-modal-section-note` for collection lock state; keep field locks functional but move the explanatory copy out of each business row.
- [ ] Change database input placeholder to `输入新的连接地址` and place the safe configured state above it.
- [ ] Run `node --check app/web/static/js/configuration.js` and the focused static test.

### Task 3: Apply the shared visual system

**Files:**
- Modify: `app/web/static/configuration.css`

- [ ] Apply a single border and divider treatment to `.config-collection-table`, remove accent bars and card shadows from rows inside `.config-edit-modal-body`, and reduce labels/actions to a consistent compact scale.
- [ ] Give settings blocks a two-column grid without fixed height; collapse to one column under 720px.
- [ ] Style database state and restart guidance as quiet information, not a large green alert.
- [ ] Run `node --check app/web/static/js/configuration.js`, `pytest tests/unit/test_configuration_service.py tests/unit/test_configuration_frontend_static.py -q`, and `git diff --check`.
- [ ] Commit with message `feat(config): simplify modal hierarchy`.
