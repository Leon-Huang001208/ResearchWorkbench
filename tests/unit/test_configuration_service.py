"""Configuration service safety tests."""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.settings.config import Settings
from core.settings.runtime import RuntimeContext
from services import configuration_service
from services.database_readiness import DatabaseReadiness, DatabaseReadinessCode
from services.configuration_service import ConfigurationService

SECRET_VALUES = {
    "DATABASE_URL": "postgresql+psycopg://user:db-secret@localhost:5432/alphafoundry",
    "IFIND_USERNAME": "ifind-user",
    "IFIND_PASSWORD": "ifind-secret",
    "TAVILY_API_KEY": "tavily-secret",
}


def _service(tmp_path) -> ConfigurationService:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in SECRET_VALUES.items()) + "\n",
        encoding="utf-8",
    )
    return ConfigurationService(env_path=env_path, runtime_settings=Settings())


def test_snapshot_masks_secrets_without_returning_raw_values(monkeypatch, tmp_path):
    for key in SECRET_VALUES:
        monkeypatch.delenv(key, raising=False)
    service = _service(tmp_path)

    serialized = json.dumps(service.get_snapshot(), ensure_ascii=False)

    for secret in ("db-secret", "ifind-secret", "tavily-secret"):
        assert secret not in serialized
    assert '"value"' not in serialized
    assert "********" in serialized


def test_database_url_persists_with_restart_required(monkeypatch, tmp_path):
    for key in SECRET_VALUES:
        monkeypatch.delenv(key, raising=False)
    runtime_settings = Settings(
        DATABASE_URL="postgresql+psycopg://active:old@localhost:5432/alphafoundry"
    )
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=runtime_settings)
    new_url = "postgresql+psycopg://next:next-secret@localhost:5432/alphafoundry"

    result = service.update_section("database", {"database_url": new_url})

    assert result["applied"] is False
    assert result["restart_required"] is True
    assert (
        runtime_settings.DATABASE_URL
        == "postgresql+psycopg://active:old@localhost:5432/alphafoundry"
    )
    assert new_url in (tmp_path / ".env").read_text(encoding="utf-8")
    assert "next-secret" not in json.dumps(result)


def test_configuration_service_rejects_web_production_control_plane(tmp_path):
    runtime_context = RuntimeContext(
        mode="web-prod",
        project_root=tmp_path,
        data_dir=None,
        env_path=tmp_path / "controlled.env",
        backend_url="https://api.example.invalid",
        can_write_config=False,
    )
    service = ConfigurationService(
        env_path=tmp_path / "controlled.env",
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )

    try:
        service.get_snapshot()
    except RuntimeError as exc:
        assert "禁用" in str(exc)
    else:
        raise AssertionError("Expected production control-plane rejection")


def test_database_probe_reports_missing_pgvector_without_persistence(monkeypatch, tmp_path):
    database_url = "postgresql+psycopg://user:db-secret@localhost:5432/alphafoundry"
    env_path = tmp_path / ".env"
    env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
    service = ConfigurationService(env_path=env_path, runtime_settings=Settings())
    probe = Mock(
        return_value=DatabaseReadiness(
            ready=False,
            code=DatabaseReadinessCode.PGVECTOR_MISSING,
            message="数据库未启用 pgvector 扩展。",
            remediation=("请在目标数据库中启用 vector 扩展后重试。",),
        )
    )
    monkeypatch.setattr(configuration_service, "probe_postgresql", probe, raising=False)
    original_content = env_path.read_text(encoding="utf-8")
    original_environment = dict(os.environ)

    result = service.test_section("database", {"database_url": database_url})

    probe.assert_called_once_with(database_url, service.connection_timeout)
    assert result == {
        "success": False,
        "message": "数据库未启用 pgvector 扩展。",
        "code": "pgvector_missing",
        "remediation": ["请在目标数据库中启用 vector 扩展后重试。"],
    }
    assert env_path.read_text(encoding="utf-8") == original_content
    assert dict(os.environ) == original_environment
    assert "db-secret" not in json.dumps(result, ensure_ascii=False)


def test_database_probe_returns_ready_result_from_readiness_stub(monkeypatch, tmp_path):
    database_url = "postgresql+psycopg://user:password@localhost:5432/alphafoundry"
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=Settings())
    probe = Mock(
        return_value=DatabaseReadiness(
            ready=True,
            code=DatabaseReadinessCode.READY,
            message="数据库连接正常，pgvector 已就绪。",
            remediation=("无需处理。",),
        )
    )
    monkeypatch.setattr(configuration_service, "probe_postgresql", probe, raising=False)

    result = service.test_section("database", {"database_url": database_url})

    probe.assert_called_once_with(database_url, service.connection_timeout)
    assert result == {
        "success": True,
        "message": "数据库连接正常，pgvector 已就绪。",
        "code": "ready",
        "remediation": ["无需处理。"],
    }


def test_database_probe_exception_returns_safe_fallback(monkeypatch, tmp_path):
    database_url = "postgresql+psycopg://alice:top-secret@db.internal:5432/private_db"
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=Settings())

    def raise_sensitive_error(*_args, **_kwargs):
        raise RuntimeError("alice top-secret db.internal:5432/private_db")

    monkeypatch.setattr(
        configuration_service, "probe_postgresql", raise_sensitive_error, raising=False
    )

    result = service.test_section("database", {"database_url": database_url})

    assert result == {
        "success": False,
        "message": "数据库预检发生未知错误。",
        "code": "unexpected_error",
        "remediation": ["请检查本地数据库配置后重试。"],
    }
    rendered = json.dumps(result, ensure_ascii=False)
    for sensitive_text in ("alice", "top-secret", "db.internal", "5432", "private_db"):
        assert sensitive_text not in rendered


def test_web_search_probe_uses_submitted_candidate_values(monkeypatch, tmp_path):
    from data_layer.web_search import factory

    captured: dict[str, object] = {}

    class Provider:
        def search(self, query, max_results):
            assert query == "ping"
            assert max_results == 1
            return [object()]

    def build_provider(**kwargs):
        captured.update(kwargs)
        return Provider()

    monkeypatch.setattr(factory, "build_web_search_provider_from_values", build_provider)
    candidate = {
        "WEB_SEARCH_PROVIDER": "bing",
        "WEB_SEARCH_API_KEYS": '[{"name":"next","key":"submitted-key"}]',
        "WEB_SEARCH_KEY_ROTATION": "random",
        "WEB_SEARCH_KEY_QUOTA_LIMIT": "2000",
    }

    assert ConfigurationService._probe_web_search(candidate, timeout=5.0) is True
    assert captured["provider_name"] == "bing"
    assert captured["key_pool_json"] == candidate["WEB_SEARCH_API_KEYS"]
    assert captured["rotation_strategy"] == "random"
    assert captured["quota_limit"] == 2000


def test_advanced_configuration_persists_for_restart_without_mutating_runtime(tmp_path):
    runtime_settings = Settings(LOG_LEVEL="INFO")
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=runtime_settings)

    result = service.update_section("advanced", {"log_level": "ERROR"})

    assert result["applied"] is False
    assert result["restart_required"] is True
    assert runtime_settings.LOG_LEVEL == "INFO"
    assert "LOG_LEVEL='ERROR'" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_environment_values_lock_configuration_fields(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=tmp_path,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
        environment_override_keys=frozenset({"LOG_LEVEL"}),
    )
    service = ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )

    snapshot = service.get_snapshot()

    assert snapshot["sections"]["advanced"]["log_level"] == "WARNING"
    assert snapshot["environment_locked_fields"] == ["LOG_LEVEL"]

    with pytest.raises(RuntimeError, match="系统环境变量锁定") as exc_info:
        service.update_section("advanced", {"log_level": "ERROR"})

    assert "WARNING" not in str(exc_info.value)
    assert env_path.read_text(encoding="utf-8") == "LOG_LEVEL=INFO\n"


def test_llm_partial_updates_preserve_environment_locked_provider_and_route_keys(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_PROVIDER_1_NAME=locked-provider\n"
        "LLM_PROVIDER_1_PROTOCOL=openai_compatible\n"
        "LLM_PROVIDER_1_BASE_URL=https://locked.example.test\n"
        "LLM_PROVIDER_1_API_KEY=file-locked-secret\n"
        "LLM_PROVIDER_2_NAME=editable-provider\n"
        "LLM_PROVIDER_2_PROTOCOL=openai_compatible\n"
        "LLM_PROVIDER_2_BASE_URL=https://editable.example.test\n"
        "LLM_PROVIDER_2_API_KEY=file-editable-secret\n"
        "TASK_CHAT_PROVIDER=file-chat-provider\n"
        "TASK_CHAT_MODEL=old-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_PROVIDER_1_API_KEY", "environment-locked-secret")
    monkeypatch.setenv("TASK_CHAT_PROVIDER", "environment-chat-provider")
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=tmp_path,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
        environment_override_keys=frozenset({"LLM_PROVIDER_1_API_KEY", "TASK_CHAT_PROVIDER"}),
    )
    service = ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )

    result = service.update_section(
        "llm",
        {
            "providers": [
                {
                    "original_name": "locked-provider",
                    "name": "locked-provider",
                    "protocol": "openai_compatible",
                    "base_url": "https://locked.example.test",
                    "api_key": None,
                    "clear_api_key": False,
                },
                {
                    "original_name": "editable-provider",
                    "name": "editable-provider",
                    "protocol": "anthropic",
                    "base_url": "https://editable.example.test",
                    "api_key": None,
                    "clear_api_key": False,
                },
            ],
            "task_routes": [
                {
                    "task": "chat",
                    "provider": "environment-chat-provider",
                    "model": "next-model",
                },
            ],
        },
    )

    saved = env_path.read_text(encoding="utf-8")
    assert result["section"]["providers"][1]["protocol"] == "anthropic"
    assert result["section"]["task_routes"] == [
        {"task": "chat", "provider": "environment-chat-provider", "model": "next-model"}
    ]
    assert "LLM_PROVIDER_1_API_KEY=file-locked-secret" in saved
    assert "TASK_CHAT_PROVIDER=file-chat-provider" in saved
    assert "LLM_PROVIDER_2_PROTOCOL='anthropic'" in saved
    assert "TASK_CHAT_MODEL='next-model'" in saved


def test_ifind_connection_updates_preserve_environment_managed_credentials(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "IFIND_USERNAME=file-user\n"
        "IFIND_PASSWORD=file-secret\n"
        "IFIND_BACKEND=auto\n"
        "IFIND_HTTP_BASE_URL=https://old.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("IFIND_USERNAME", "environment-user")
    monkeypatch.setenv("IFIND_PASSWORD", "environment-secret")
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=tmp_path,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
        environment_override_keys=frozenset({"IFIND_USERNAME", "IFIND_PASSWORD"}),
    )
    service = ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )

    result = service.update_section(
        "ifind",
        {"backend": "http_api", "http_base_url": "https://next.example.test"},
    )

    saved = env_path.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["restart_required"] is False
    assert result["section"]["backend"] == "http_api"
    assert result["section"]["http_base_url"] == "https://next.example.test"
    assert "IFIND_BACKEND='http_api'" in saved
    assert "IFIND_HTTP_BASE_URL='https://next.example.test'" in saved
    assert "IFIND_USERNAME=file-user" in saved
    assert "IFIND_PASSWORD=file-secret" in saved

    with pytest.raises(RuntimeError, match="IFIND_USERNAME"):
        service.update_section("ifind", {"username": "attempted-override"})


def test_ifind_connection_updates_preserve_environment_managed_account_pool(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "IFIND_USERNAME=file-user\n"
        "IFIND_PASSWORD=file-secret\n"
        "IFIND_BACKEND=auto\n"
        "IFIND_HTTP_BASE_URL=https://old.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "IFIND_ACCOUNTS_JSON",
        '[{"name":"environment","username":"environment-user","password":"environment-secret"}]',
    )
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=tmp_path,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
        environment_override_keys=frozenset({"IFIND_ACCOUNTS_JSON"}),
    )
    service = ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )

    result = service.update_section(
        "ifind",
        {"backend": "http_api", "http_base_url": "https://next.example.test"},
    )

    saved = env_path.read_text(encoding="utf-8")
    assert result["section"]["backend"] == "http_api"
    assert result["section"]["http_base_url"] == "https://next.example.test"
    assert "IFIND_USERNAME=file-user" in saved
    assert "IFIND_PASSWORD=file-secret" in saved
    assert "IFIND_ACCOUNTS_JSON" not in saved

    with pytest.raises(RuntimeError, match="IFIND_ACCOUNTS_JSON"):
        service.update_section(
            "ifind",
            {"accounts": [{"name": "attempted", "username": "attempted-user", "password": "new-secret"}]},
        )

    assert env_path.read_text(encoding="utf-8") == saved


@pytest.mark.parametrize(
    "locked_key, environment_value",
    [
        ("WEB_SEARCH_API_KEYS", '[{"name":"environment","key":"secret"}]'),
        ("TAVILY_API_KEY", "tavily-secret"),
        ("BING_API_KEY", "bing-secret"),
    ],
)
def test_web_search_account_pool_rejects_any_environment_managed_pool_key(
    monkeypatch, tmp_path, locked_key, environment_value
):
    env_path = tmp_path / ".env"
    env_path.write_text(f"{locked_key}=file-value\nWEB_SEARCH_TIMEOUT=15\n", encoding="utf-8")
    monkeypatch.setenv(locked_key, environment_value)
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=tmp_path,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
        environment_override_keys=frozenset({locked_key}),
    )
    service = ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(),
        runtime_context=runtime_context,
    )
    original = env_path.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match=locked_key):
        service.update_section(
            "web_search",
            {"accounts": [{"name": "attempted-override", "key": "replacement-secret"}]},
        )

    assert env_path.read_text(encoding="utf-8") == original
    result = service.update_section("web_search", {"timeout": 20})
    assert result["section"]["timeout"] == 20


def _environment_service(tmp_path, *, data_dir=Path("data")) -> ConfigurationService:
    env_path = tmp_path / "config" / ".env"
    runtime_context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path,
        data_dir=data_dir,
        env_path=env_path,
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
    )
    return ConfigurationService(
        env_path=env_path,
        runtime_settings=Settings(LOG_DIR=tmp_path / "logs"),
        runtime_context=runtime_context,
    )


def test_snapshot_reports_windows_x64_psql_without_exposing_its_path(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(configuration_service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(configuration_service.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(shutil, "which", lambda command: r"C:\\Program Files\\PostgreSQL\\bin\\psql.exe")
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)

    snapshot = service.get_snapshot()
    environment = snapshot["environment"]
    capabilities = environment["capabilities"]

    assert environment["platform"] == "windows"
    assert environment["architecture"] == "x64"
    assert environment["runtime_mode"] == "desktop"
    assert environment["paths"] == {
        "config": str((tmp_path / "config" / ".env").resolve()),
        "data": str((tmp_path / "data").resolve()),
        "logs": str((tmp_path / "logs").resolve()),
    }
    assert [item["key"] for item in capabilities] == [
        "postgresql_client",
        "ifind_python_sdk",
        "wind_excel",
    ]
    assert capabilities[0]["status"] == "available"
    assert "psql.exe" not in json.dumps(snapshot, ensure_ascii=False)


def test_snapshot_reports_missing_psql_client(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)

    capability = service.get_snapshot()["environment"]["capabilities"][0]

    assert capability["key"] == "postgresql_client"
    assert capability["status"] == "not_detected"


def test_snapshot_reports_not_detected_for_an_absent_ifind_sdk_without_mocking_finder(
    monkeypatch, tmp_path
):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(
        configuration_service,
        "IFIND_SDK_MODULE",
        "alphafoundry_missing_ifind_sdk_for_contract_test",
    )

    capability = service.get_snapshot()["environment"]["capabilities"][1]

    assert capability["key"] == "ifind_python_sdk"
    assert capability["status"] == "not_detected"


def test_snapshot_marks_wind_excel_not_applicable_on_macos(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(configuration_service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)

    capability = service.get_snapshot()["environment"]["capabilities"][2]

    assert capability["key"] == "wind_excel"
    assert capability["status"] == "not_applicable"


def test_snapshot_reports_unknown_when_ifind_sdk_discovery_raises(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(shutil, "which", lambda command: None)

    def raise_discovery_error(_name):
        raise RuntimeError("unexpected discovery failure")

    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", raise_discovery_error)

    capability = service.get_snapshot()["environment"]["capabilities"][1]

    assert capability["key"] == "ifind_python_sdk"
    assert capability["status"] == "unknown"


def test_snapshot_reports_none_data_path_when_runtime_context_has_no_data_dir(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=None)
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)

    assert service.get_snapshot()["environment"]["paths"]["data"] is None


def test_snapshot_degrades_one_unresolvable_path_without_leaking_it(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)
    original_resolve = Path.resolve
    config_path = str(service.env_path)

    def fail_only_config_path(path, *args, **kwargs):
        if path == service.env_path:
            raise OSError("sensitive configuration path cannot be resolved")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_only_config_path)

    snapshot = service.get_snapshot()

    assert snapshot["environment"]["paths"]["config"] is None
    assert snapshot["environment"]["paths"]["data"] == str((tmp_path / "data").resolve())
    assert snapshot["environment"]["paths"]["logs"] == str((tmp_path / "logs").resolve())
    assert config_path not in json.dumps(snapshot, ensure_ascii=False)


def test_snapshot_includes_static_configuration_catalog(monkeypatch, tmp_path):
    service = _environment_service(tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr(shutil, "which", lambda command: None)
    monkeypatch.setattr(configuration_service.importlib.util, "find_spec", lambda name: None)

    snapshot = service.get_snapshot()

    assert snapshot["catalog"]["sections"][0]["key"] == "llm"
