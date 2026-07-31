# Test Report: Cross-platform configuration unification

Task ID: ad-hoc-cross-platform-configuration

## Changed source files

- `core/settings/runtime.py`, `core/settings/config.py`, and `core/settings/registry.py` — resolve desktop/Web runtime mode, configuration locations, storage defaults, locked process-environment fields, and safe database defaults.
- `scripts/desktop/backend_launcher.py`, `build_sidecar.py`, and `sidecar_launcher.py` — package a self-contained sidecar, resolve PyInstaller bundle roots correctly, enforce loopback-only IPv4 startup, require PostgreSQL, migrate the legacy Windows config, and refuse to kill unknown port owners.
- `services/configuration_service.py`, `app/api/configuration_models.py`, `app/api/configuration_security.py`, `app/api/main.py`, and `app/web/static/js/configuration.js` — hide persisted secrets, restrict configuration to loopback, disable it in production, expose/disable environment-locked fields, require restart for database and logging changes, and sanitize health errors.
- `data_layer/repositories/base.py` — emit dialect-specific, sanitized startup connection diagnostics and avoid raw database exception strings in session logs.
- `cron_jobs/auto_ingest_service.py` — uses `ALPHAFOUNDRY_BACKEND_URL` for internal API endpoints.
- `data_layer/web_search/factory.py` and `key_pool.py` — build a temporary web-search provider from submitted candidate configuration rather than global runtime settings during validation.

## Changed test files

- `tests/unit/test_runtime_settings.py`
- `tests/unit/test_settings_registry.py`
- `tests/unit/test_auto_ingest_service.py`
- `tests/unit/test_configuration_service.py`
- `tests/unit/test_configuration_frontend_static.py`
- `tests/unit/data_layer/repositories/test_base_connection.py`
- `tests/unit/app/api/test_configuration_security.py`
- `tests/unit/app/api/test_health_security.py`
- `tests/unit/test_desktop_shell_scaffold.py`

## Changed docs

- `.env.example`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/REFERENCE.md`
- `docs/DATA_STORAGE.md`
- `docs/desktop_packaging.md`
- `docs/FILE_GUIDE.md`
- `docs/modules/app_api.md`
- `docs/modules/cron_jobs.md`
- `docs/modules/data_layer_repositories.md`
- `docs/modules/scripts.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

## Commands run

- Focused cross-platform configuration suite: runtime, registry, auto-ingest, configuration service/frontend, API security/health, repository diagnostics, and desktop launcher tests.
- Additional web-search factory/key-pool regression suite.
- `node --check app/web/static/js/configuration.js`
- Scoped `ruff`, `black --check`, `isort --check-only`, and `mypy` for all changed Python modules/tests.
- `ruff check .`
- `black . --check`
- `isort . --check-only`
- Project-wide `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`
- `python -m pytest tests/ -v`
- `python scripts/generate_py_file_index.py`
- `python scripts/check_task_completion.py`
- `python scripts/check_doc_sync.py`
- Playwright MCP browser-tab access.

## Command results

- Focused cross-platform suite: **56 passed, 4 deselected**; FastAPI lifecycle deprecation warnings only.
- Additional final configuration, web-search, key-pool, and launcher regressions: **42 passed**; security review confirmed no remaining HIGH or CRITICAL finding after key-pool failure-accounting and fallback remediation.
- Final JavaScript syntax check: passed.
- Scoped Ruff/Black/isort/mypy for the changed modules/tests: passed; mypy reported no issues in 14 changed source files.
- Completion check: passed.
- Documentation sync check: passed.
- Full `ruff check .`: failed with **31 errors** in lazy-import annotations, one import-order issue, and unused imports outside this task's changed scope.
- Full `black . --check`: failed; **110 files would be reformatted**.
- Full `isort . --check-only`: passed.
- Project-wide `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`: failed with **51 errors in 13 files**.
- Full `python -m pytest tests/ -v`: failed with **36 failure markers** outside this task's changed scope. Failures include missing report-project binary assets, stale workbench static expectations, source-registry expectation drift, chart contract failures, Wind display normalization, and a pytest-managed Chromium headless-shell dependency failure; no focused cross-platform configuration test failed.
- Playwright MCP: passed. It opened the desktop configuration page, opened the database configuration modal, confirmed the configured secret stayed masked with a restart-required notice, and captured `cross-platform-configuration-browser-proof.png` as verification evidence.

## Skipped tests

- Full project suite includes expected live E2E skips; its remaining failures are outside this task's changed scope and described above.
- No browser verification was skipped: Playwright MCP successfully verified the desktop configuration page and database configuration modal and captured a screenshot.

## Remaining risk

- PostgreSQL + pgvector installation remains user-managed for desktop builds.
- Windows ACL hardening equivalent to POSIX `0600` is not implemented; normal `%LOCALAPPDATA%` user isolation is relied upon.
- Full desktop-bundle smoke tests on physical macOS and Windows remain outstanding.
- Repository-wide Ruff, Black formatting, mypy, and full pytest failures block final completion status. Playwright MCP browser verification has passed.

## Final test decision

Blocked. Focused configuration regressions, scoped checks, documentation checks, and Playwright MCP browser verification pass. Mandatory repository-wide `ruff check .`, `black . --check`, project-wide mypy, and `python -m pytest tests/ -v` remain nonzero because of baseline failures outside this task's changed scope.

## 2026-07-23 Workbench interaction incident follow-up

### Root cause

- `app/web/static/js/configuration.js` is statically imported by `app.js`.
- An unwrapped configuration-modal event-listener block left its closing brace unmatched after `applyEnvironmentLocks()` was added, producing `SyntaxError: Unexpected token '}'` in the browser.
- Because the entry module could not evaluate, Workbench navigation and other document event listeners were never registered, so rendered controls appeared but did not respond.

### Repair and focused verification

- Restored `function bindModalFormEvents(form, section)` around the existing modal event-binding body.
- Added `test_configuration_modal_event_binder_remains_declared` and `test_configuration_module_parses_with_node` in `tests/unit/test_configuration_frontend_static.py`.
- `node --check app/web/static/js/configuration.js`: passed.
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_configuration_frontend_static.py -v`: **3 passed**.
- `ruff check tests/unit/test_configuration_frontend_static.py`, `black --check tests/unit/test_configuration_frontend_static.py`, and `isort --check-only tests/unit/test_configuration_frontend_static.py`: passed.
- Playwright MCP loaded `http://127.0.0.1:8765/`, clicked `.activity-btn[data-section="config"]`, found no `pageerror`, and confirmed `#section-config.active`.

### Follow-up risk

- The previously recorded repository-wide Ruff and full-pytest baseline failures remain outside this focused repair; the task remains blocked until that baseline debt is separately remediated.
- Re-ran the mandatory repository gate sequence on 2026-07-23. `ruff check .` reports 31 errors, `black . --check` reports 110 files requiring formatting, and project-wide mypy reports 51 errors in 13 files; the full pytest command also exits nonzero because report-project binary assets are missing and unrelated expectations have drifted. The focused configuration module checks and Playwright MCP verification remain green.
