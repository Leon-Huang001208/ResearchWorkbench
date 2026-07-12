"""ConfigurationService 的安全持久化和热更新测试。"""

import json
import os
import stat
import threading
import time
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


@pytest.mark.parametrize("include_original_name", [False, True])
def test_provider_endpoint_change_never_reuses_saved_secret(
    monkeypatch, tmp_path, include_original_name
):
    path = tmp_path / ".env"
    original = (
        "LLM_PROVIDER_1_NAME=primary\n"
        "LLM_PROVIDER_1_PROTOCOL=openai_compatible\n"
        "LLM_PROVIDER_1_BASE_URL=https://old.example.test\n"
        "LLM_PROVIDER_1_API_KEY=TOPSECRET\n"
    )
    path.write_text(original, encoding="utf-8")
    for key in list(os.environ):
        if key.startswith("LLM_PROVIDER_"):
            monkeypatch.delenv(key, raising=False)
    probe_calls = []
    service = ConfigurationService(
        env_path=path,
        connection_probes={"llm": lambda candidate, timeout: probe_calls.append(candidate) or True},
    )
    provider = {
        "name": "primary",
        "protocol": "openai_compatible",
        "base_url": "https://new.example.test",
        "api_key": "",
    }
    if include_original_name:
        provider["original_name"] = "primary"
    payload = {"providers": [provider]}

    with pytest.raises(ConfigurationError, match="重新输入"):
        service.test_section("llm", payload)
    with pytest.raises(ConfigurationError, match="重新输入"):
        service.update_section("llm", payload)

    assert probe_calls == []
    assert path.read_text(encoding="utf-8") == original

    payload["providers"][0]["api_key"] = "NEWSECRET"
    result = service.test_section("llm", payload)

    assert result["success"] is True
    assert probe_calls[0]["LLM_PROVIDER_1_BASE_URL"] == "https://new.example.test"
    assert probe_calls[0]["LLM_PROVIDER_1_API_KEY"] == "NEWSECRET"
    assert "TOPSECRET" not in probe_calls[0].values()


@pytest.mark.parametrize(
    "endpoint_change",
    [
        {"http_base_url": "https://new-ifind.example.test"},
        {"backend": "python_sdk"},
    ],
)
def test_ifind_endpoint_change_never_reuses_saved_password(monkeypatch, tmp_path, endpoint_change):
    path = tmp_path / ".env"
    original = (
        "IFIND_USERNAME=user\n"
        "IFIND_PASSWORD=TOPSECRET\n"
        "IFIND_BACKEND=http_api\n"
        "IFIND_HTTP_BASE_URL=https://old-ifind.example.test\n"
    )
    path.write_text(original, encoding="utf-8")
    for key in ("IFIND_USERNAME", "IFIND_PASSWORD", "IFIND_BACKEND", "IFIND_HTTP_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    probe_calls = []
    service = ConfigurationService(
        env_path=path,
        connection_probes={
            "ifind": lambda candidate, timeout: probe_calls.append(candidate) or True
        },
    )

    with pytest.raises(ConfigurationError, match="重新输入"):
        service.test_section("ifind", endpoint_change)
    with pytest.raises(ConfigurationError, match="重新输入"):
        service.update_section("ifind", endpoint_change)

    assert probe_calls == []
    assert path.read_text(encoding="utf-8") == original


def test_changed_endpoint_probe_uses_only_new_submitted_secret(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "IFIND_USERNAME=user\nIFIND_PASSWORD=OLDSECRET\n"
        "IFIND_BACKEND=http_api\nIFIND_HTTP_BASE_URL=https://old.example.test\n",
        encoding="utf-8",
    )
    for key in ("IFIND_USERNAME", "IFIND_PASSWORD", "IFIND_BACKEND", "IFIND_HTTP_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    captured = []
    service = ConfigurationService(
        env_path=path,
        connection_probes={
            "ifind": lambda candidate, timeout: captured.append(dict(candidate)) or True
        },
    )

    result = service.test_section(
        "ifind",
        {"http_base_url": "https://new.example.test", "password": "NEWSECRET"},
    )

    assert result["success"] is True
    assert captured[0]["IFIND_HTTP_BASE_URL"] == "https://new.example.test"
    assert captured[0]["IFIND_PASSWORD"] == "NEWSECRET"
    assert "OLDSECRET" not in captured[0].values()


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


@pytest.mark.parametrize(
    "broken_content",
    ["IFIND_PASSWORD='unterminated\n", "this is not a valid dotenv line\n"],
)
def test_update_rejects_malformed_existing_env_without_overwrite(tmp_path, broken_content):
    path = tmp_path / ".env"
    path.write_text(broken_content, encoding="utf-8")
    service = ConfigurationService(env_path=path)

    with pytest.raises(ConfigurationError, match="配置文件格式无效"):
        service.update_section("advanced", {"log_level": "DEBUG"})

    assert path.read_text(encoding="utf-8") == broken_content


def test_concurrent_section_updates_are_serialized_per_env_path(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("# base\n", encoding="utf-8")
    service_a = ConfigurationService(env_path=path)
    service_b = ConfigurationService(env_path=path)
    original_write = ConfigurationService._write_env_atomic
    active_writers = 0
    max_active_writers = 0
    counter_lock = threading.Lock()

    def observed_write(self, updates, removals):
        nonlocal active_writers, max_active_writers
        with counter_lock:
            active_writers += 1
            max_active_writers = max(max_active_writers, active_writers)
        time.sleep(0.03)
        try:
            return original_write(self, updates, removals)
        finally:
            with counter_lock:
                active_writers -= 1

    monkeypatch.setattr(ConfigurationService, "_write_env_atomic", observed_write)
    errors = []

    def update_advanced():
        try:
            service_a.update_section("advanced", {"log_level": "DEBUG"})
        except Exception as exc:
            errors.append(exc)

    def update_ifind():
        try:
            service_b.update_section("ifind", {"username": "concurrent-user"})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=update_advanced), threading.Thread(target=update_ifind)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    effective = service_a.get_effective_values()
    assert errors == []
    assert max_active_writers == 1
    assert effective["LOG_LEVEL"] == "DEBUG"
    assert effective["IFIND_USERNAME"] == "concurrent-user"
    lock_path = path.parent / f".{path.name}.lock"
    assert lock_path.stat().st_size >= 1
    assert lock_path.stat().st_mode & 0o077 == 0


def test_atomic_replace_has_no_post_replace_chmod_failure(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
    service = ConfigurationService(env_path=path)

    def fail_chmod(*args, **kwargs):
        raise AssertionError("os.chmod must not run")

    monkeypatch.setattr("services.configuration_service.os.chmod", fail_chmod)

    service.update_section("advanced", {"log_level": "DEBUG"})

    assert service.get_effective_values()["LOG_LEVEL"] == "DEBUG"


def test_atomic_write_succeeds_when_os_fchmod_is_unavailable(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("IFIND_PASSWORD=TOPSECRET\nLOG_LEVEL=INFO\n", encoding="utf-8")
    service = ConfigurationService(env_path=path)
    monkeypatch.delattr("services.configuration_service.os.fchmod")

    result = service.update_section("advanced", {"log_level": "DEBUG"})

    assert result["applied"] is True
    assert service.get_effective_values()["LOG_LEVEL"] == "DEBUG"
    assert "TOPSECRET" not in str(result)
    assert path.stat().st_mode & 0o777 == 0o600


def test_fchmod_failure_before_replace_cleans_temp_and_preserves_original(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    original = "IFIND_PASSWORD=TOPSECRET\nLOG_LEVEL=INFO\n"
    path.write_text(original, encoding="utf-8")
    service = ConfigurationService(env_path=path)

    def fail_fchmod(descriptor, mode):
        raise OSError("simulated permission failure TOPSECRET")

    monkeypatch.setattr("services.configuration_service.os.fchmod", fail_fchmod)

    with pytest.raises(ConfigurationError, match="配置持久化失败") as captured:
        service.update_section("advanced", {"log_level": "DEBUG"})

    temporary_files = [item for item in tmp_path.glob("..env.*") if item != service.lock_path]
    assert path.read_text(encoding="utf-8") == original
    assert temporary_files == []
    assert "TOPSECRET" not in str(captured.value)


def test_directory_fsync_is_attempted_without_post_replace_business_failure(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
    service = ConfigurationService(env_path=path)
    original_fsync = os.fsync
    directory_sync_attempted = False

    def observed_fsync(descriptor):
        nonlocal directory_sync_attempted
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directory_sync_attempted = True
            raise OSError("simulated unsupported directory fsync")
        return original_fsync(descriptor)

    monkeypatch.setattr("services.configuration_service.os.fsync", observed_fsync)

    service.update_section("advanced", {"log_level": "DEBUG"})

    assert directory_sync_attempted is True
    assert service.get_effective_values()["LOG_LEVEL"] == "DEBUG"


@pytest.mark.parametrize("login_result", [True, False])
def test_zhiqiu_probe_always_closes_client_and_disables_failure_dump(
    monkeypatch, tmp_path, login_result
):
    monkeypatch.chdir(tmp_path)
    created = []

    class FakeClient:
        def __init__(self, username, password, request_timeout, failure_dump_path):
            self.failure_dump_path = failure_dump_path
            self.closed = False
            created.append(self)

        def login(self):
            if not login_result and self.failure_dump_path is not None:
                Path(self.failure_dump_path).write_text("LEAKME", encoding="utf-8")
            return login_result

        def close(self):
            self.closed = True

    monkeypatch.setattr("data_layer.crawlers.zq.zhiqiu.client.ZhiQiuClient", FakeClient)
    candidate = {
        "ZQ_ACCOUNTS_JSON": json.dumps(
            [{"name": "main", "username": "user", "password": "TOPSECRET"}]
        )
    }

    result = ConfigurationService._probe_zhiqiu(candidate, 1.0)

    assert result is login_result
    assert created[0].failure_dump_path is None
    assert created[0].closed is True
    assert not (tmp_path / "login_failed.html").exists()
