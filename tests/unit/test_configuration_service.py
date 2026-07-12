"""ConfigurationService 的安全持久化和热更新测试。"""

import json
import os
from pathlib import Path

import pytest

from services.configuration_service import ConfigurationError, ConfigurationService


@pytest.fixture
def env_path(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        "# keep this comment\n"
        "UNRELATED_FLAG=leave-me\n"
        "IFIND_USERNAME=existing-user\n"
        "IFIND_PASSWORD=super-secret-value\n"
        "DATABASE_URL=postgresql://user:db-secret@localhost:5432/alpha\n",
        encoding="utf-8",
    )
    return path


def test_snapshot_masks_secrets_without_returning_original_values(monkeypatch, env_path):
    monkeypatch.delenv("IFIND_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = ConfigurationService(env_path=env_path)

    snapshot = service.get_snapshot()
    serialized = json.dumps(snapshot, ensure_ascii=False)

    assert snapshot["sections"]["ifind"]["password"] == {
        "configured": True,
        "masked_value": "********alue",
    }
    assert "super-secret-value" not in serialized
    assert "db-secret" not in serialized


def test_update_ifind_keeps_blank_secret_and_preserves_unrelated_lines(monkeypatch, env_path):
    monkeypatch.delenv("IFIND_PASSWORD", raising=False)
    service = ConfigurationService(env_path=env_path)

    result = service.update_section(
        "ifind",
        {
            "username": "new-user",
            "password": "",
            "backend": "http_api",
            "http_base_url": "https://example.test/api",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "# keep this comment" in content
    assert "UNRELATED_FLAG=leave-me" in content
    assert "IFIND_PASSWORD=super-secret-value" in content
    assert os.stat(env_path).st_mode & 0o777 == 0o600
    assert result["applied"] is True
    assert result["restart_required"] is False


def test_update_ifind_replaces_and_explicitly_clears_password(monkeypatch, env_path):
    monkeypatch.delenv("IFIND_PASSWORD", raising=False)
    service = ConfigurationService(env_path=env_path)

    replaced = service.update_section("ifind", {"password": "new-secret"})
    cleared = service.update_section("ifind", {"clear_password": True})

    assert replaced["section"]["password"]["configured"] is True
    assert cleared["section"]["password"]["configured"] is False
    assert "IFIND_PASSWORD" not in env_path.read_text(encoding="utf-8")


def test_update_zhiqiu_serializes_special_characters_as_json(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
    service = ConfigurationService(env_path=path)
    accounts = [{"name": "main", "username": "user@example.com", "password": "p:a,s#word"}]

    result = service.update_section("zhiqiu", {"accounts": accounts, "max_retries": 4})

    assert result["section"]["accounts"][0]["password"]["configured"] is True
    assert service.get_effective_values()["ZQ_ACCOUNTS_JSON"] == json.dumps(
        accounts, ensure_ascii=False, separators=(",", ":")
    )


def test_database_update_is_persisted_but_requires_restart(monkeypatch, env_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = ConfigurationService(env_path=env_path)
    previous_runtime_url = service.runtime_settings.DATABASE_URL

    result = service.update_section(
        "database", {"database_url": "sqlite:////tmp/next-alphafoundry.db"}
    )

    assert result["applied"] is False
    assert result["restart_required"] is True
    assert service.runtime_settings.DATABASE_URL == previous_runtime_url
    assert service.get_effective_values()["DATABASE_URL"] == "sqlite:////tmp/next-alphafoundry.db"


def test_llm_partial_route_update_preserves_provider_credentials(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "LLM_PROVIDER_1_NAME=primary\n"
        "LLM_PROVIDER_1_PROTOCOL=openai_compatible\n"
        "LLM_PROVIDER_1_BASE_URL=https://llm.example.test\n"
        "LLM_PROVIDER_1_API_KEY=provider-secret\n",
        encoding="utf-8",
    )
    for key in list(os.environ):
        if key.startswith("LLM_PROVIDER_") or key.startswith("TASK_TEST_"):
            monkeypatch.delenv(key, raising=False)
    service = ConfigurationService(env_path=path)

    service.update_section(
        "llm", {"task_routes": [{"task": "test", "provider": "primary", "model": "m1"}]}
    )

    effective = service.get_effective_values()
    assert effective["LLM_PROVIDER_1_API_KEY"] == "provider-secret"
    assert effective["TASK_TEST_MODEL"] == "m1"


def test_provider_rename_with_blank_secret_preserves_original_secret(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "LLM_PROVIDER_1_NAME=old-provider\n"
        "LLM_PROVIDER_1_PROTOCOL=openai_compatible\n"
        "LLM_PROVIDER_1_BASE_URL=https://llm.example.test\n"
        "LLM_PROVIDER_1_API_KEY=provider-secret\n",
        encoding="utf-8",
    )
    for key in list(os.environ):
        if key.startswith("LLM_PROVIDER_"):
            monkeypatch.delenv(key, raising=False)
    service = ConfigurationService(env_path=path)

    service.update_section(
        "llm",
        {
            "providers": [
                {
                    "original_name": "old-provider",
                    "name": "new-provider",
                    "protocol": "openai_compatible",
                    "base_url": "https://llm.example.test",
                    "api_key": "",
                }
            ]
        },
    )

    effective = service.get_effective_values()
    assert effective["LLM_PROVIDER_1_NAME"] == "new-provider"
    assert effective["LLM_PROVIDER_1_API_KEY"] == "provider-secret"

    service.update_section(
        "llm",
        {
            "providers": [
                {
                    "original_name": "new-provider",
                    "name": "new-provider",
                    "protocol": "openai_compatible",
                    "base_url": "https://llm.example.test",
                    "clear_api_key": True,
                }
            ]
        },
    )

    assert "LLM_PROVIDER_1_API_KEY" not in service.get_effective_values()


def test_zhiqiu_account_rename_preserves_secret_until_explicit_clear(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        'ZQ_ACCOUNTS_JSON=\'[{"name":"old","username":"user","password":"saved-secret"}]\'\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
    service = ConfigurationService(env_path=path)

    service.update_section(
        "zhiqiu",
        {
            "accounts": [
                {
                    "original_name": "old",
                    "name": "new",
                    "username": "user",
                    "password": "",
                }
            ]
        },
    )
    renamed = json.loads(service.get_effective_values()["ZQ_ACCOUNTS_JSON"])
    service.update_section(
        "zhiqiu",
        {
            "accounts": [
                {
                    "original_name": "new",
                    "name": "new",
                    "username": "user",
                    "clear_password": True,
                }
            ]
        },
    )
    cleared = json.loads(service.get_effective_values()["ZQ_ACCOUNTS_JSON"])

    assert renamed[0]["password"] == "saved-secret"
    assert cleared[0]["password"] == ""


def test_zhiqiu_snapshot_preserves_unusable_json_account_status(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        'ZQ_ACCOUNTS_JSON=\'[{"name":"pending","username":"pending-user"}]\'\n'
        "ZQ_ACCOUNTS=legacy:legacy-secret\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ZQ_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("ZQ_ACCOUNTS", raising=False)
    service = ConfigurationService(env_path=path)

    account = service.get_snapshot()["sections"]["zhiqiu"]["accounts"][0]

    assert account["name"] == "pending"
    assert account["password"]["configured"] is False


def test_connection_probe_success_and_failure_are_non_persistent(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# keep\n", encoding="utf-8")
    calls = []

    def success_probe(candidate, timeout):
        calls.append((dict(candidate), timeout))
        return True

    service = ConfigurationService(
        env_path=path,
        connection_probes={
            "ifind": success_probe,
            "llm": lambda candidate, timeout: False,
            "zhiqiu": lambda candidate, timeout: True,
        },
        connection_timeout=1.5,
    )

    success = service.test_section(
        "ifind", {"username": "tester", "password": "temporary", "backend": "http_api"}
    )
    failure = service.test_section(
        "llm",
        {
            "providers": [
                {
                    "name": "probe",
                    "protocol": "openai_compatible",
                    "base_url": "https://example.test",
                    "api_key": "temporary",
                }
            ]
        },
    )

    assert success == {"success": True, "message": "连接验证成功"}
    assert failure == {"success": False, "message": "连接验证失败"}
    assert calls[0][1] == 1.5
    assert path.read_text(encoding="utf-8") == "# keep\n"


def test_invalid_section_is_rejected_without_persisting(env_path):
    before = env_path.read_text(encoding="utf-8")
    service = ConfigurationService(env_path=env_path)

    with pytest.raises(ConfigurationError):
        service.update_section("unsupported", {"value": "secret"})

    assert env_path.read_text(encoding="utf-8") == before


def test_atomic_write_failure_preserves_original_file(monkeypatch, env_path):
    service = ConfigurationService(env_path=env_path)
    before = env_path.read_text(encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("services.configuration_service.os.replace", fail_replace)

    with pytest.raises(ConfigurationError, match="配置持久化失败"):
        service.update_section("advanced", {"log_level": "DEBUG"})

    assert env_path.read_text(encoding="utf-8") == before
