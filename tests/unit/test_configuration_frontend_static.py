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
