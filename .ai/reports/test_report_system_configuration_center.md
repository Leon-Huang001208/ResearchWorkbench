# 系统配置中心测试报告

Task ID: `system-configuration-center`

Status: `done`（功能、浏览器验证和全仓门禁均已完成）

Changed source files:

- `core/settings/config.py`
- `data_layer/crawlers/zq/zhiqiu/account_manager.py`
- `data_layer/crawlers/zq/zhiqiu/client.py`
- `services/configuration_service.py`
- `app/api/configuration_models.py`
- `app/api/configuration_security.py`
- `app/api/routes/configuration.py`
- `app/api/main.py`
- `app/web/templates/index.html`
- `app/web/static/js/configuration.js`
- `app/web/static/js/app.js`
- `app/web/static/js/core.js`
- `app/web/static/style.css`
- `scripts/desktop/backend_launcher.py`

Changed test files:

- `tests/unit/test_runtime_configuration_compatibility.py`
- `tests/unit/test_configuration_service.py`
- `tests/unit/test_configuration_api.py`
- `tests/unit/test_configuration_frontend.py`

Commands/results recorded by implementation and integration stages:

- Fresh combined configuration/iFinD/ZQ suite: `78 passed, 22 warnings`.
- Configuration frontend focused suite: `14 passed`, including three Node-backed behavior tests and a WCAG contrast matrix.
- Final CSRF/CORS, endpoint-secret binding, runtime, frontend Node, and desktop launcher focused suite: `64 passed, 22 warnings`.
- Host/Origin and implicit provider-identity security regression suite: `92 passed, 22 warnings`.
- Combined frontend regression before final style-only changes: 2 failures, matching the pre-implementation baseline (`if (!wordFile)` legacy assertion and old `app.js?v=20260703theme1` cache-version assertion).
- Focused ruff: passed.
- Focused black check: passed.
- Focused isort check: passed after normalizing `tests/unit/test_configuration_frontend.py`.
- Targeted mypy (`--follow-imports=skip`): passed, 5 source files checked.
- Playwright CLI browser verification: passed at 1440×1000 and 820×1000.
- Runtime `.env` persistence: passed with mode `0600`.

Behavior covered:

- Runtime config path precedence and current-process environment override.
- Five-section masking/readiness, strict schemas, safe 422 responses, and unsupported sections.
- Secret retain/replace/explicit-clear semantics and `original_name` behavior across renames.
- LLM endpoint-secret binding also resolves an existing provider by current `name` when `original_name` is omitted; endpoint changes with an empty token fail before any probe.
- Trusted Host defaults restrict the local server to `localhost`, `127.0.0.1`, and `testserver`; explicit host extensions reject wildcards, URLs, credentials, paths, and ports. Configuration API origins are limited to loopback, supported Tauri origins, or explicit CORS origins whose host is also trusted.
- Strict dotenv rejection, unrelated line/comment preservation, same-path thread/process serialization, `0600` temporary permissions, fsync, atomic replace, and failure cleanup.
- Runtime-safe refresh, ZhiQiu new-client environment compatibility, and database restart-only behavior.
- Real short-timeout LLM/ZhiQiu/iFinD probes with no candidate persistence; database URL-only validation.
- Frontend initial-load gate, stale-load cancellation, save/test serialization, dirty-form protection, safe DOM rendering, and blank secret controls.

Browser verification:

- Loaded the configuration page from the real FastAPI application using an isolated SQLite database and `/tmp` configuration path.
- Added and saved an LLM Provider and task route; the readiness summary changed from `2 / 5` to `3 / 5`.
- Reloaded the page and confirmed the Token field remained blank while displaying `已配置`.
- Renamed the Provider with an empty Token field and verified the persisted API key remained present.
- Verified entering a replacement Token then selecting explicit clear emptied and disabled the secret input.
- Saved a database URL and confirmed the UI returned `重启后生效`.
- Verified the 1440px single-column layout no longer overlaps the help cards and the 820px layout remains usable.
- Browser console contained no JavaScript errors; Chromium emitted only password/autocomplete accessibility suggestions.

Full repository gates:

- `ruff check .`: passed.
- `black . --check`: passed.
- `isort . --check-only`: passed.
- `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`: passed (`383 source files`).
- `python -m pytest tests/ -q`: passed (`2085 passed, 5 skipped`).
- `python scripts/check_task_completion.py`: passed.
- `python scripts/check_doc_sync.py`: passed.
- `python scripts/generate_py_file_index.py`: passed.

Skipped checks:

- Real production credentials were not used by automated tests; connection-probe unit tests inject controlled probes, while production defaults use the existing real clients.

Documentation checks:

- `/Users/leon/opt/anaconda3/bin/python scripts/generate_py_file_index.py`: passed; generated `docs/generated/py_file_index.md`.
- `git diff --check`: passed with no whitespace errors.
- `/Users/leon/opt/anaconda3/bin/python scripts/check_doc_sync.py`: passed; reported `No source files requiring doc sync were changed.` because this audit commit changes documentation/metadata only.

Gate remediation:

- pytest 的同名 PDF 测试已通过包标记获得唯一模块路径；默认数据库测试改为每进程临时 SQLite，真实 PostgreSQL 冒烟受 `ALPHAFOUNDRY_RUN_POSTGRES_TESTS=1` 控制。
- 内置华安报告的必需二进制资产纳入版本控制；模型配置改为可迁移的 `BAAI/...` 标识。
- 全仓 ruff、black、isort 和 mypy 历史债均已清理，产业链基础图数据已随仓库提供。

Remaining risk:

- Real LLM、知秋和 iFinD connectivity still depends on valid user credentials and reachable vendor services.
- IPv6 loopback is not enabled by the default Host allowlist; deployments that need non-default network binding require an explicitly reviewed host configuration and compatible server binding.

Final test decision: feature-focused and browser verification are green; all mandatory repository gates pass and the task is `done`.
