"""运行时配置路径和知秋账号兼容性测试。"""

import json

from core.settings.config import resolve_runtime_env_path
from data_layer.crawlers.zq.zhiqiu.account_manager import AccountManager


def test_resolve_runtime_env_path_prefers_explicit_path(monkeypatch, tmp_path):
    explicit_path = tmp_path / "custom.env"
    monkeypatch.setenv("ALPHAFOUNDRY_CONFIG_PATH", str(explicit_path))
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    assert resolve_runtime_env_path(project_root=tmp_path / "project") == explicit_path


def test_resolve_runtime_env_path_uses_desktop_data_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPHAFOUNDRY_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    assert (
        resolve_runtime_env_path(project_root=tmp_path / "project") == tmp_path / "desktop" / ".env"
    )


def test_resolve_runtime_env_path_defaults_to_project_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPHAFOUNDRY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", raising=False)

    assert resolve_runtime_env_path(project_root=tmp_path) == tmp_path / ".env"


def test_account_manager_prefers_json_accounts_with_special_characters(monkeypatch, tmp_path):
    config_path = tmp_path / "zq.yaml"
    config_path.write_text("accounts: {}\n", encoding="utf-8")
    expected = [
        {"name": "primary", "username": "user@example.com", "password": "p:a,s#word"},
        {"name": "backup", "username": "备用用户", "password": "密,码:值"},
    ]
    monkeypatch.setenv("ZQ_ACCOUNTS_JSON", json.dumps(expected, ensure_ascii=False))
    monkeypatch.setenv("ZQ_ACCOUNTS", "legacy:secret")

    manager = AccountManager(str(config_path))

    assert manager.config["accounts"] == {
        "primary": {"username": "user@example.com", "password": "p:a,s#word"},
        "backup": {"username": "备用用户", "password": "密,码:值"},
    }


def test_account_manager_falls_back_when_json_is_invalid(monkeypatch, tmp_path, caplog):
    config_path = tmp_path / "zq.yaml"
    config_path.write_text("accounts: {}\n", encoding="utf-8")
    monkeypatch.setenv("ZQ_ACCOUNTS_JSON", '{"password":"must-not-appear"')
    monkeypatch.setenv("ZQ_ACCOUNTS", "legacy:legacy-secret")

    manager = AccountManager(str(config_path))

    assert manager.config["accounts"]["legacy"]["password"] == "legacy-secret"
    assert "must-not-appear" not in caplog.text


def test_account_manager_uses_yaml_when_account_environment_is_absent(monkeypatch, tmp_path):
    config_path = tmp_path / "zq.yaml"
    config_path.write_text(
        "accounts:\n  yaml-account:\n    username: yaml-user\n    password: yaml-secret\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)

    manager = AccountManager(str(config_path))

    assert manager.config["accounts"]["yaml-account"]["username"] == "yaml-user"


def test_account_manager_prefers_runtime_rotation_environment(monkeypatch, tmp_path):
    config_path = tmp_path / "zq.yaml"
    config_path.write_text(
        "accounts: {}\naccount_rotation:\n  max_retries: 2\n  rotation_strategy: random\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ZQ_MAX_RETRIES", "7")
    monkeypatch.setenv("ZQ_ROTATION_STRATEGY", "least_used")

    manager = AccountManager(str(config_path))

    assert manager.rotation_config.max_retries == 7
    assert manager.rotation_config.rotation_strategy == "least_used"
