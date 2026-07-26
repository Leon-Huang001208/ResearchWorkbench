"""Static safety checks for the configuration workbench."""

import subprocess
from pathlib import Path

CONFIGURATION_JS = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "js" / "configuration.js"
)
CONFIGURATION_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "index.html"
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

    assert "applyProviderRowLocks" in source
    assert "applyTaskRouteLocks" in source
    assert "setDynamicRowLocked" in source
    assert "LLM_PROVIDER_${index}_" in source
    assert "TASK_${task.toUpperCase()}_PROVIDER" in source


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


def test_configuration_module_parses_with_node():
    result = subprocess.run(
        ["node", "--check", str(CONFIGURATION_JS)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_console_keeps_health_overview_and_session_test_state():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'data-config-health-summary' in template
    assert 'data-config-onboarding' in template
    assert 'data-config-card-action' in template
    assert 'connectionStateBySection' in source
    assert '已验证' in source
    assert '连接异常' in source
