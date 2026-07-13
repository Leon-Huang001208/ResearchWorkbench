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
CONFIGURATION_CSS = ROOT / "app" / "web" / "static" / "configuration.css"


def test_configuration_navigation_and_five_sections_are_present():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "app.js?v=20260713config13" in html
    assert 'data-section="config"' in html
    assert 'id="section-config"' in html
    assert 'id="config-readiness-overview"' not in html
    assert 'id="config-refresh"' not in html
    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'id="config-{section}-form"' in html
        assert f'data-config-save="{section}"' in html


def test_configuration_page_keeps_only_configuration_actions():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'data-config-save="{section}" disabled' in html
    assert "data-add-zhiqiu-account" in html
    assert "data-add-ifind-account" in html
    assert "data-config-test" not in html
    assert "整体就绪" not in html


def test_configuration_uses_a_dedicated_aligned_workspace_style_sheet():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'href="/static/configuration.css?v=20260713config12"' in html
    css = CONFIGURATION_CSS.read_text(encoding="utf-8")
    assert ".config-provider-labels" in css
    assert ".config-secret-control" in css
    assert ".config-ifind-row" in css
    assert "--config-provider-columns" in css
    assert "--config-account-columns" in css
    assert "justify-content: center;" in css


def test_configuration_module_uses_expected_api_contract_and_is_initialized_by_navigation():
    app_source = APP_JS.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert (
        "import { initConfigurationPage } from './configuration.js?v=20260713config13'" in app_source
    )
    assert "import { apiCall } from './core.js?v=20260712config2'" in source
    assert "if (section === 'config') initConfigurationPage();" in app_source
    assert "export async function initConfigurationPage()" in source
    assert (
        "configurationApiCall('GET', '/api/config', null, { signal: controller.signal })" in source
    )
    assert "configurationApiCall('PUT', `/api/config/${section}`" in source
    assert "configurationApiCall('POST', `/api/config/${section}/test`" in source
    assert "initialLoadRetryCount" in source


def test_configuration_csrf_meta_and_request_header_contract_execute_in_node():
    html = INDEX_HTML.read_text(encoding="utf-8")
    core_source = CORE_JS.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'name="alphafoundry-config-token"' in html
    assert 'content="__ALPHAFOUNDRY_CONFIG_TOKEN__"' in html
    assert "...(options.headers || {})" in core_source
    assert "X-AlphaFoundry-Config-Token" in source
    assert "localStorage" not in source

    script = f"""
        import {{ configurationRequestOptions }} from {json.dumps(CONFIGURATION_JS.as_uri())};
        globalThis.document = {{
            querySelector: () => ({{ content: 'NODE_CSRF_TOKEN' }}),
        }};
        const options = configurationRequestOptions({{signal: 'signal-value'}});
        console.log(JSON.stringify(options));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        "signal": "signal-value",
        "headers": {"X-AlphaFoundry-Config-Token": "NODE_CSRF_TOKEN"},
    }


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


def test_configuration_secrets_can_be_revealed_without_a_clear_control():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'type="password"' in html
    assert "config-clear-secret" not in source
    assert "显式清除" not in source
    assert "document.createTextNode('清除')" not in source
    assert "configured" in source
    assert "secret.value" in source
    assert "toggleSecretVisibility" in source
    assert "复制" in source
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
    assert "color: var(--accent-foreground);" in css
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


def test_configuration_primary_tokens_meet_wcag_contrast_in_final_cascade():
    css = STYLE_CSS.read_text(encoding="utf-8")
    final_schemes = css.split(
        "/* Re-apply color schemes after late desktop theme blocks so accents stay user-controlled. */",
        1,
    )[1]

    def contrast(foreground: str, background: str) -> float:
        def luminance(color: str) -> float:
            channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
        return (lighter + 0.05) / (darker + 0.05)

    cases = {
        "light-default": ("#0066cc", "#005bb5", "#ffffff"),
        "light-vscode": ("#007acc", "#006bb3", "#ffffff"),
        "light-github": ("#1a7f37", "#116329", "#ffffff"),
        "light-openclaw": ("#cf222e", "#a40e26", "#ffffff"),
        "light-claude": ("#d97706", "#f59e0b", "#111827"),
        "light-obsidian": ("#7c3aed", "#6d28d9", "#ffffff"),
        "dark-default": ("#0a84ff", "#409cff", "#0d0f14"),
        "dark-vscode": ("#007acc", "#006bb3", "#ffffff"),
        "dark-github": ("#3fb950", "#2ea043", "#0d0f14"),
        "dark-openclaw": ("#f85149", "#ff6b6b", "#0d0f14"),
        "dark-claude": ("#f59e0b", "#fbbf24", "#0d0f14"),
        "dark-obsidian": ("#a78bfa", "#c4b5fd", "#0d0f14"),
    }

    def last_block(source: str, selector: str) -> str:
        start = source.rindex(f"\n{selector} {{") + 1
        return source[start:].split("}", 1)[0].lower()

    before_schemes = css[: css.index("/* Re-apply color schemes after late desktop theme blocks")]
    selectors = {
        "light-default": (before_schemes, '[data-theme="light"]'),
        "dark-default": (before_schemes, '[data-theme="dark"]'),
    }
    for scheme in ("vscode", "github", "openclaw", "claude", "obsidian"):
        selectors[f"light-{scheme}"] = (final_schemes, f'[data-color-scheme="{scheme}"]')
        selectors[f"dark-{scheme}"] = (
            final_schemes,
            f'[data-theme="dark"][data-color-scheme="{scheme}"]',
        )

    for name, (accent, hover, foreground) in cases.items():
        assert contrast(foreground, accent) >= 4.5, name
        assert contrast(foreground, hover) >= 4.5, name
        source, selector = selectors[name]
        block = last_block(source, selector)
        assert f"--accent: {accent};" in block, name
        assert f"--accent-hover: {hover};" in block, name
        assert f"--accent-foreground: {foreground};" in block, name

    assert "--accent-foreground: #ffffff;" in final_schemes
    assert "--accent-foreground: #111827;" in final_schemes
    assert "--accent-foreground: #0D0F14;" in final_schemes
    assert "--accent-hover: #006bb3;" in final_schemes
    assert "--accent-hover: #116329;" in final_schemes
    assert "--accent-hover: #f59e0b;" in final_schemes
