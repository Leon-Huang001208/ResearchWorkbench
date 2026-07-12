"""系统配置中心前端静态回归测试。"""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
CORE_JS = ROOT / "app" / "web" / "static" / "js" / "core.js"
CONFIGURATION_JS = ROOT / "app" / "web" / "static" / "js" / "configuration.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"


def test_configuration_navigation_and_five_sections_are_present():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "app.js?v=20260712config5" in html
    assert 'data-section="config"' in html
    assert 'id="section-config"' in html
    assert 'id="config-readiness-overview"' in html
    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'id="config-{section}-form"' in html
        assert f'data-config-save="{section}"' in html


def test_configuration_page_exposes_readiness_and_connection_test_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for category in ("overall", "llm", "zhiqiu", "ifind", "database"):
        assert f'data-readiness="{category}"' in html
    for section in ("llm", "zhiqiu", "ifind"):
        assert f'data-config-test="{section}"' in html
        assert f'data-config-test="{section}" disabled' in html
    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'data-config-save="{section}" disabled' in html
    assert "重启后生效" in html


def test_configuration_module_uses_expected_api_contract_and_is_initialized_by_navigation():
    app_source = APP_JS.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert (
        "import { initConfigurationPage } from './configuration.js?v=20260712config5'" in app_source
    )
    assert "import { apiCall } from './core.js?v=20260712config2'" in source
    assert "if (section === 'config') initConfigurationPage();" in app_source
    assert "export async function initConfigurationPage()" in source
    assert "apiCall('GET', '/api/config', null, { signal: controller.signal })" in source
    assert "apiCall('PUT', `/api/config/${section}`" in source
    assert "apiCall('POST', `/api/config/${section}/test`" in source


def test_dynamic_configuration_rows_support_add_remove_and_original_names():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "renderProviders" in source
    assert "renderTaskRoutes" in source
    assert "renderZhiqiuAccounts" in source
    assert "original_name" in source
    assert "data-add-provider" in source
    assert "data-add-task-route" in source
    assert "data-add-zhiqiu-account" in source
    assert "aria-label" in source


def test_configuration_secrets_are_blank_and_require_explicit_clear():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'type="password"' in html
    assert "clear_api_key" in source
    assert "clear_password" in source
    assert "configured" in source
    assert "masked_value" not in source
    assert "localStorage" not in source
    assert "dataset.secret" not in source


def test_api_strings_are_rendered_without_inner_html():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "createElement" in source
    assert "textContent" in source
    assert "replaceChildren" in source
    assert "innerHTML" not in source


def test_api_call_exposes_only_safe_structured_validation_details():
    source = CORE_JS.read_text(encoding="utf-8")

    assert "apiError.details = safeDetails" in source
    assert "detail.loc" in source
    assert "detail.type" in source
    assert "detail.msg" in source
    assert "detail.input" not in source
    assert "请求未通过字段校验" in source


def test_configuration_errors_render_field_paths_without_api_values_in_dataset():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "const rowOriginalNames = new WeakMap()" in source
    assert "rowOriginalNames.set(row" in source
    assert "rowOriginalNames.get(row)" in source
    assert "updateOriginalNameMappings(section, values)" in source
    assert "rowOriginalNames.set(row, provider.original_name || provider.name || '')" in source
    assert "rowOriginalNames.set(row, account.original_name || account.name || '')" in source
    assert "dataset.originalName" not in source
    assert "formatValidationPath" in source
    assert "error.details" in source
    assert "replaceChildren" in source
    assert "字段校验失败" in source
    assert "result.message" not in source
    assert "error.message" not in source


def test_configuration_request_state_and_secret_rules_execute_in_node():
    script = f"""
        import {{
            createGenerationTracker,
            createRequestCoordinator,
            normalizeSecretState,
            safeConfigurationError,
        }} from {json.dumps(CONFIGURATION_JS.as_uri())};

        const tracker = createGenerationTracker();
        const loadOne = tracker.next();
        const loadTwo = tracker.next();
        const coordinator = createRequestCoordinator();
        const first = coordinator.begin('llm');
        const duplicate = coordinator.begin('llm');
        coordinator.finish('llm', first);
        const next = coordinator.begin('llm');
        const typed = normalizeSecretState('new-secret', true, 'input');
        const cleared = normalizeSecretState('new-secret', true, 'clear');
        const serverError = new Error('TOP_SECRET');
        serverError.status = 500;
        serverError.details = [{{loc: ['providers', 0, 'name'], msg: '安全消息', input: 'TOP_SECRET'}}];
        const safe = safeConfigurationError(serverError);
        const validationError = new Error('TOP_SECRET');
        validationError.status = 422;
        validationError.details = [{{loc: ['providers', 0, 'name'], msg: '输入值未通过校验'}}];
        const validation = safeConfigurationError(validationError);
        console.log(JSON.stringify({{
            latest: tracker.isLatest(loadTwo) && !tracker.isLatest(loadOne),
            duplicateBlocked: duplicate === null,
            newerToken: next > first,
            typed,
            cleared,
            safe,
            validation,
        }}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["latest"] is True
    assert payload["duplicateBlocked"] is True
    assert payload["newerToken"] is True
    assert payload["typed"] == {"value": "new-secret", "clear": False, "disabled": False}
    assert payload["cleared"] == {"value": "", "clear": True, "disabled": True}
    assert payload["safe"] == {"message": "配置保存失败", "details": []}
    assert payload["validation"]["message"] == "字段校验失败"
    assert payload["validation"]["details"][0]["path"] == "providers.0.name"
    assert "TOP_SECRET" not in result.stdout


def test_mutation_aborts_delayed_load_and_denies_refresh_in_node():
    script = f"""
        import {{ createGenerationTracker, createRequestCoordinator }}
            from {json.dumps(CONFIGURATION_JS.as_uri())};

        const applied = [];
        const tracker = createGenerationTracker();
        const controller = new AbortController();
        let aborted = false;
        let refreshRestored = false;
        const coordinator = createRequestCoordinator({{
            onFirstBegin: () => {{
                controller.abort();
                tracker.invalidate();
            }},
            onLastFinish: () => {{ refreshRestored = true; }},
        }});
        const loadToken = tracker.next();
        const delayedGet = new Promise((resolve, reject) => {{
            const timer = setTimeout(() => resolve({{source: 'GET'}}), 30);
            controller.signal.addEventListener('abort', () => {{
                clearTimeout(timer);
                aborted = true;
                const error = new Error('aborted');
                error.name = 'AbortError';
                reject(error);
            }}, {{once: true}});
        }}).then(value => {{
            if (tracker.isLatest(loadToken)) applied.push(value.source);
        }}).catch(error => {{
            if (error.name !== 'AbortError') throw error;
        }});

        const putToken = coordinator.begin('llm');
        const refreshDenied = coordinator.hasActive();
        applied.push('PUT');
        coordinator.finish('llm', putToken);
        await delayedGet;
        console.log(JSON.stringify({{
            aborted,
            refreshDenied,
            refreshRestored,
            oldLoadLatest: tracker.isLatest(loadToken),
            applied,
        }}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "aborted": True,
        "refreshDenied": True,
        "refreshRestored": True,
        "oldLoadLatest": False,
        "applied": ["PUT"],
    }


def test_readiness_gate_denies_mutation_until_successful_load_in_node():
    script = f"""
        import {{ createReadinessGate }} from {json.dumps(CONFIGURATION_JS.as_uri())};

        const gate = createReadinessGate();
        let collected = 0;
        let networked = 0;
        const mutation = () => {{ collected += 1; networked += 1; }};
        const beforeReady = gate.run(mutation);
        gate.markLoadFailed();
        const afterFailedInitialLoad = gate.run(mutation);
        gate.markReady();
        const afterReady = gate.run(mutation);
        console.log(JSON.stringify({{
            beforeReady,
            afterFailedInitialLoad,
            afterReady,
            collected,
            networked,
            ready: gate.isReady(),
        }}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "beforeReady": False,
        "afterFailedInitialLoad": False,
        "afterReady": True,
        "collected": 1,
        "networked": 1,
        "ready": True,
    }


def test_configuration_initializes_once_and_save_does_not_reload_snapshot():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    save_start = source.index("async function saveSection(section)")
    save_end = source.index("async function testSection(section)", save_start)
    save_source = source[save_start:save_end]
    test_end = source.index("function markSectionDirty", save_end)
    test_source = source[save_end:test_end]

    assert "let configurationInitialized = false" in source
    assert "if (configurationInitialized) return;" in source
    assert "configurationInitialized = true;" in source
    assert "AbortController" in source
    assert "createGenerationTracker" in source
    assert "loadConfiguration" not in save_source
    assert "setSectionBusy" in save_source
    assert "requestCoordinator.begin(section)" in save_source
    assert "requestCoordinator.finish(section, token)" in save_source
    assert "finally" in save_source
    assert "editedWhileSaving" in save_source
    assert "applySectionResponse(section, result.section, !editedWhileSaving)" in save_source
    assert "loadAbortController?.abort()" in source
    assert "loadGeneration.invalidate()" in source
    assert "requestCoordinator.hasActive()" in source
    assert "setRefreshDisabled(true)" in source
    assert "setRefreshDisabled(false)" in source
    assert "let configurationReady = false" in source
    assert "if (!configurationReady)" in save_source
    assert "if (!configurationReady)" in test_source
    assert "loadConfiguration({ discardDirty: true })" in source


def test_configuration_styles_cover_layout_states_and_accessible_focus():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".configuration-layout" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(280px, 0.38fr);" in css
    assert ".config-status.ready" in css
    assert ".config-status.missing" in css
    assert ".config-status.error" in css
    assert ".config-status.restart" in css
    assert ".config-field-errors" in css
    assert ".configuration-page .primary-btn" in css
    assert ".configuration-page .secondary-btn" in css
    assert "color: #111827;" in css
    assert ".configuration-page .primary-btn:not(:disabled):hover" in css
    assert ".configuration-page .secondary-btn:not(:disabled):hover" in css
    assert ".configuration-page .primary-btn:active" in css
    assert ".configuration-page .secondary-btn:active" in css
    assert ".configuration-page button:disabled" in css
    assert ".configuration-page .config-remove-row" in css
    assert ".configuration-page .config-remove-row:not(:disabled):hover" in css
    assert ".configuration-page :focus-visible" in css
    focus_block = css.split(".configuration-page :focus-visible {", 1)[1].split("}", 1)[0]
    assert "outline: 2px solid var(--border-focus);" in focus_block
    assert "@media (max-width: 1500px)" in css
    wide_breakpoint = css.split("@media (max-width: 1500px)", 1)[1].split(
        "@media (max-width: 1180px)", 1
    )[0]
    assert ".configuration-layout" in wide_breakpoint
    assert "grid-template-columns: 1fr;" in wide_breakpoint
    assert ".configuration-help" in wide_breakpoint
    assert "position: static;" in wide_breakpoint
    assert "@media (max-width: 900px)" in css
