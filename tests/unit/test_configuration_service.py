"""Configuration service safety tests."""

import json

from core.settings.config import Settings
from core.settings.runtime import RuntimeContext
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


def test_database_validation_accepts_psycopg_v3_url(tmp_path):
    service = ConfigurationService(env_path=tmp_path / ".env", runtime_settings=Settings())

    result = service.test_section(
        "database",
        {"database_url": "postgresql+psycopg://user:password@localhost:5432/alphafoundry"},
    )

    assert result == {"success": True, "message": "数据库地址格式验证通过"}


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

    try:
        service.update_section("advanced", {"log_level": "ERROR"})
    except RuntimeError as exc:
        assert "系统环境变量锁定" in str(exc)
    else:
        raise AssertionError("Expected environment-locked field rejection")

    assert env_path.read_text(encoding="utf-8") == "LOG_LEVEL=INFO\n"
