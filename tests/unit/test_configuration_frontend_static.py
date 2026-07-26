"""Static safety checks for the configuration workbench."""

import re
import subprocess
from pathlib import Path

CONFIGURATION_JS = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "js" / "configuration.js"
)
CONFIGURATION_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "index.html"
)
APP_WEB_DOC = Path(__file__).resolve().parents[2] / "docs" / "modules" / "app_web.md"
CONFIGURATION_LOCK_SPEC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-26-contextual-configuration-locks-design.md"
)


def _configuration_function(source: str, name: str) -> str:
    """Return one named function, with an actionable failure if it is absent."""
    declaration = re.compile(
        rf"^(?:export\s+)?(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = declaration.search(source)
    if not match:
        raise AssertionError(f"configuration.js must declare {name}()")
    following = re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(",
        re.MULTILINE,
    ).search(source, match.end())
    return source[match.start():following.start() if following else len(source)]


def _configuration_modal_markup(template: str) -> str:
    """Return configuration-modal markup without relying on a fixed line layout."""
    modal = re.search(r'<div\s+id="config-edit-modal"(?=[\s>])', template)
    if not modal:
        raise AssertionError('index.html must declare the config-edit-modal container')
    section_end = re.search(r"^\s*</section>", template[modal.start():], re.MULTILINE)
    if not section_end:
        raise AssertionError('config-edit-modal must remain inside the configuration section')
    return template[modal.start():modal.start() + section_end.start()]


def _config_refresh_markup(template: str) -> str:
    """Return the refresh button markup, or identify the missing UI control clearly."""
    refresh = re.search(
        r'<button\b(?=[^>]*\bid="config-refresh")[^>]*>.*?</button>',
        template,
        re.DOTALL,
    )
    if not refresh:
        raise AssertionError('index.html must declare a #config-refresh button')
    return refresh.group(0)


def test_configuration_workbench_never_refills_saved_secrets():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "api_key?.value" not in source
    assert "password?.value" not in source
    assert "account.key?.value" not in source
    assert "database_url?.value" not in source
    assert "environment_locked_fields" in source
    assert "applyEnvironmentLocks" in source
    assert "setSecretState" in source


def test_configuration_modal_event_binder_remains_declared():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "bindModalFormEvents(form, section);" in source
    assert "function bindModalFormEvents(form, section)" in source


def test_database_summary_uses_runtime_readiness_not_saved_url_state():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "databaseRuntimeReadiness" in source
    assert "/api/setup/readiness" in source
    assert "数据库已验证" in source
    assert "数据库待重启" in source
    assert "数据库未就绪" in source
    assert "已配置连接地址" not in source


def test_configuration_locks_are_contextual_not_global():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "data-config-environment-lock-notice" not in template
    assert "renderEnvironmentLockedFields" not in source
    assert "LOCKED_FIELD_MESSAGE" in source
    assert "data-config-lock-message" in source
    assert "aria-describedby" in source
    assert "由当前启动配置管理" in source


def test_configuration_locks_dynamic_configuration_in_context():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    app_web_doc = APP_WEB_DOC.read_text(encoding="utf-8")
    lock_spec = CONFIGURATION_LOCK_SPEC.read_text(encoding="utf-8")

    assert "applyProviderRowLocks" in source
    assert "applyTaskRouteLocks" in source
    assert "setDynamicRowLocked" in source
    assert "setModalLockNote(true)" in source
    assert "LLM_PROVIDER_${index}_" in source
    assert "TASK_${task.toUpperCase()}_PROVIDER" in source
    assert "该组由当前启动配置管理" in source
    assert "原子集合锁定" in app_web_doc
    assert "原子集合锁定" in lock_spec


def test_configuration_collection_lock_message_has_an_accessible_id():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "config-collection-lock-message-${++dynamicLockMessageSequence}" in source


def test_configuration_payload_filter_omits_static_environment_locks():
    script = f"""
import {{ filterEnvironmentLockedPayload }} from {CONFIGURATION_JS.as_uri()!r};

const accounts = [{{ name: 'primary' }}];
const webSearchPayload = {{
    accounts,
    provider: 'tavily',
    rotation_strategy: 'round_robin',
    quota_limit: 1000,
    max_results: 5,
    timeout: 15,
}};
const lockedFields = [
    'LOG_LEVEL', 'LOG_DIR', 'LLM_EXTRACT_MAX_WORKERS', 'LLM_EXTRACT_MAX_RETRIES',
    'LLM_EXTRACT_CHUNK_SIZE', 'LLM_EXTRACT_CHUNK_OVERLAP', 'LLM_EXTRACT_LONG_TEXT_THRESHOLD',
    'DATABASE_URL', 'WEB_SEARCH_PROVIDER', 'WEB_SEARCH_KEY_ROTATION',
    'WEB_SEARCH_KEY_QUOTA_LIMIT', 'WEB_SEARCH_MAX_RESULTS', 'WEB_SEARCH_TIMEOUT',
];
const advancedPayload = {{
    log_level: 'INFO', log_dir: '/tmp/logs', llm_max_workers: 4, llm_max_retries: 2,
    chunk_size: 1000, chunk_overlap: 100, long_text_threshold: 5000,
}};
const databasePayload = {{ database_url: 'postgres://secret' }};

const filtered = {{
    advanced: filterEnvironmentLockedPayload('advanced', advancedPayload, lockedFields),
    database: filterEnvironmentLockedPayload('database', databasePayload, lockedFields),
    web_search: filterEnvironmentLockedPayload('web_search', webSearchPayload, lockedFields),
}};

if (JSON.stringify(filtered) !== JSON.stringify({{
    advanced: {{}},
    database: {{}},
    web_search: {{ accounts }},
}})) {{
    throw new Error(`unexpected filtered payload: ${{JSON.stringify(filtered)}}`);
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_payload_filter_omits_locked_dynamic_collections_only():
    script = f"""
import {{ filterEnvironmentLockedPayload }} from {CONFIGURATION_JS.as_uri()!r};

const providers = [{{ name: 'environment-provider' }}];
const taskRoutes = [{{ task: 'chat', provider: 'environment-provider', model: 'gpt-test' }}];
const accounts = [{{ name: 'environment-account' }}];

const filtered = {{
    providerLocked: filterEnvironmentLockedPayload(
        'llm', {{ providers, task_routes: taskRoutes }}, ['LLM_PROVIDER_1_API_KEY'],
    ),
    routeLocked: filterEnvironmentLockedPayload(
        'llm', {{ providers, task_routes: taskRoutes }}, ['TASK_CHAT_PROVIDER'],
    ),
    zhiqiu: filterEnvironmentLockedPayload(
        'zhiqiu', {{ accounts, rotation_strategy: 'round_robin' }}, ['ZQ_ACCOUNTS_JSON'],
    ),
    ifind: filterEnvironmentLockedPayload(
        'ifind', {{ accounts, backend: 'http_api', http_base_url: 'https://example.test' }}, ['IFIND_PASSWORD'],
    ),
    webSearch: filterEnvironmentLockedPayload(
        'web_search', {{ accounts, provider: 'tavily', timeout: 15 }}, ['TAVILY_API_KEY'],
    ),
}};

const expected = {{
    providerLocked: {{ task_routes: taskRoutes }},
    routeLocked: {{ providers }},
    zhiqiu: {{ rotation_strategy: 'round_robin' }},
    ifind: {{ backend: 'http_api', http_base_url: 'https://example.test' }},
    webSearch: {{ provider: 'tavily', timeout: 15 }},
}};

if (JSON.stringify(filtered) !== JSON.stringify(expected)) {{
    throw new Error(`unexpected filtered payload: ${{JSON.stringify(filtered)}}`);
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_module_parses_with_node():
    result = subprocess.run(
        ["node", "--check", str(CONFIGURATION_JS)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_refinement_replaces_onboarding_with_compact_progress_overview():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    health_source = _configuration_function(source, "renderConfigurationHealth")

    assert 'data-config-progress-completed' in template
    assert 'data-config-progress-missing' in template
    assert 'data-config-connection-summary' in template
    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in template
    assert 'data-config-onboarding' not in health_source


def test_configuration_refinement_refresh_status_is_described_and_never_tests_connections():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    refresh_markup = _config_refresh_markup(template)
    refresh_source = _configuration_function(source, "refreshConfiguration")
    load_source = _configuration_function(source, "loadConfiguration")
    refresh_path = refresh_source + load_source

    assert '刷新状态' in refresh_markup
    described_by = re.search(r'\baria-describedby="([^"]+)"', refresh_markup)
    assert described_by, '#config-refresh must describe its non-testing refresh behavior'
    help_ids = described_by.group(1).split()
    help_text = ''
    for help_id in help_ids:
        help_node = re.search(
            rf'<(?P<tag>[A-Za-z][\w-]*)\b(?=[^>]*\bid="{re.escape(help_id)}")[^>]*>'
            rf'(?P<content>.*?)</(?P=tag)>',
            template,
            re.DOTALL,
        )
        if help_node:
            help_text += help_node.group('content')
    assert '不测试连接或保存配置' in help_text, (
        '#config-refresh aria-describedby must reference help text stating “不测试连接或保存配置”'
    )
    assert 'await loadConfiguration({ discardDirty: true });' in refresh_source
    assert 'connectionStateBySection.clear()' in refresh_path
    assert 'testSection' not in refresh_path
    assert '/test' not in refresh_path
    assert 'modalTestSection' not in refresh_path


def test_configuration_refinement_binds_status_filter_without_onboarding_events():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindConfigurationEvents")

    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in events_source
    assert 'openNextIncompleteConfiguration' not in events_source
    assert re.search(
        r'\[data-config-status-filter\][\s\S]{0,200}?addEventListener\(\s*[\'\"]change[\'\"]'
        r'[\s\S]{0,300}?renderConfigurationCardVisibility',
        events_source,
    ), 'bindConfigurationEvents must call renderConfigurationCardVisibility on filter changes'


def test_configuration_refinement_modal_test_help_tracks_testable_sections_without_saving():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    modal_template = _configuration_modal_markup(template)
    open_modal_source = _configuration_function(source, "openConfigModal")
    test_help = re.search(
        r'<(?P<tag>[A-Za-z][\w-]*)\b(?=[^>]*\bdata-config-test-help\b)[^>]*>'
        r'(?P<content>.*?)</(?P=tag)>',
        modal_template,
        re.DOTALL,
    )

    assert test_help, 'config edit modal must include a data-config-test-help element'
    assert '测试连接不会保存当前更改' in test_help.group('content')
    assert 'const testable = Boolean(meta.testable);' in open_modal_source
    assert re.search(r'testBtn\.hidden\s*=\s*!testable\s*;', open_modal_source)
    assert re.search(
        r'querySelector\(\s*[\'\"]\[data-config-test-help\][\'\"]\s*\)\.hidden\s*=\s*!testable\s*;',
        open_modal_source,
    ), 'openConfigModal must hide data-config-test-help with the test button for non-testable sections'


def test_configuration_refinement_modal_save_action_and_collection_layout_hooks():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    modal_template = _configuration_modal_markup(template)

    assert re.search(
        r'<button id="btn-config-edit-modal-save"[^>]*>.*?保存更改',
        modal_template,
        re.DOTALL,
    ), 'config edit modal must present its primary save action as “保存更改”'
    assert 'config-empty-collection' in source
    assert 'config-field-grid config-field-grid--compact' in source


def test_configuration_refinement_modal_locks_keep_accessible_descriptions():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    environment_lock_source = _configuration_function(source, "setEnvironmentLockState")
    apply_locks_source = _configuration_function(source, "applyEnvironmentLocks")

    assert 'aria-describedby' in environment_lock_source
    assert 'setEnvironmentLockState(control' in apply_locks_source
    assert 'setModalLockNote(hasStaticLock)' in apply_locks_source
