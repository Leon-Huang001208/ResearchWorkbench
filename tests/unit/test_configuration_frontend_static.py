"""Static safety checks for the configuration workbench."""

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


def test_configuration_refinement_uses_compact_progress_and_explicit_refresh_semantics():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'data-config-progress-completed' in template
    assert 'data-config-progress-missing' in template
    assert 'data-config-connection-summary' in template
    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in template
    assert '刷新状态' in template
    assert '不测试连接' in template
    assert 'renderConfigurationCardVisibility' in source
    assert 'connectionStateBySection' in source
    assert 'connectionStateBySection.clear()' in source


def test_configuration_refinement_keeps_modal_actions_and_empty_collection_hooks():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'data-config-test-help' in template
    assert '保存更改' in template
    assert 'config-empty-collection' in source
    assert 'config-field-grid config-field-grid--compact' in source
    assert 'aria-describedby' in source
