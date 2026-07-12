"""系统配置 API 契约与错误处理测试。"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.main import app, parse_cors_origins
from app.api.routes.configuration import get_configuration_service
from services.configuration_service import ConfigurationService

CONFIGURATION_SECURITY_SOURCE = (
    Path(__file__).resolve().parents[2] / "app" / "api" / "configuration_security.py"
)


def _client_for(path: Path, connection_probes=None, authorized=True) -> TestClient:
    service = ConfigurationService(env_path=path, connection_probes=connection_probes)
    app.dependency_overrides[get_configuration_service] = lambda: service
    client = TestClient(app)
    if authorized:
        client.headers["X-AlphaFoundry-Config-Token"] = CONFIGURATION_CSRF_TOKEN
    return client


def test_configuration_api_requires_exact_csrf_token(tmp_path):
    missing = _client_for(tmp_path / ".env", authorized=False)
    missing_responses = [
        missing.get("/api/config"),
        missing.put("/api/config/advanced", json={"log_level": "DEBUG"}),
        missing.post("/api/config/database/test", json={"database_url": "sqlite:////tmp/a.db"}),
    ]
    wrong_response = missing.get(
        "/api/config", headers={"X-AlphaFoundry-Config-Token": "wrong-token"}
    )
    valid = missing.get(
        "/api/config",
        headers={"X-AlphaFoundry-Config-Token": CONFIGURATION_CSRF_TOKEN},
    )

    assert all(response.status_code == 403 for response in missing_responses)
    assert wrong_response.status_code == 403
    assert all(response.json() == {"detail": "Forbidden"} for response in missing_responses)
    assert wrong_response.json() == {"detail": "Forbidden"}
    assert CONFIGURATION_CSRF_TOKEN not in wrong_response.text
    assert valid.status_code == 200
    app.dependency_overrides.clear()


def test_default_cors_is_disabled_and_index_injects_token_without_api_echo(tmp_path):
    client = _client_for(tmp_path / ".env")

    index_response = client.get("/", headers={"Origin": "https://attacker.example"})
    second_index_response = client.get("/")
    preflight_response = client.options(
        "/api/config",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    api_response = client.get("/api/config")

    assert index_response.status_code == 200
    assert index_response.headers.get("access-control-allow-origin") is None
    assert preflight_response.headers.get("access-control-allow-origin") is None
    assert f'content="{CONFIGURATION_CSRF_TOKEN}"' in index_response.text
    assert f'content="{CONFIGURATION_CSRF_TOKEN}"' in second_index_response.text
    assert CONFIGURATION_CSRF_TOKEN not in api_response.text
    security_source = CONFIGURATION_SECURITY_SOURCE.read_text(encoding="utf-8")
    assert "logger" not in security_source
    assert "logging" not in security_source
    app.dependency_overrides.clear()


def test_cors_origins_require_explicit_strict_http_origins():
    assert parse_cors_origins(None) == []
    assert parse_cors_origins("https://one.example,http://127.0.0.1:3000") == [
        "https://one.example",
        "http://127.0.0.1:3000",
    ]
    for invalid in (
        "*",
        "javascript:alert(1)",
        "https://user:password@example.test",
        "https://example.test/path",
        "https://example.test?token=secret",
    ):
        try:
            parse_cors_origins(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid CORS origin accepted: {invalid}")


def test_get_configuration_never_returns_plaintext_secrets(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "IFIND_USERNAME=tester\nIFIND_PASSWORD=api-hidden-secret\n"
        "DATABASE_URL=postgresql://user:db-hidden-secret@localhost:5432/alpha\n",
        encoding="utf-8",
    )
    client = _client_for(env_path)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert "api-hidden-secret" not in response.text
    assert "db-hidden-secret" not in response.text
    assert response.json()["sections"]["ifind"]["password"]["configured"] is True
    app.dependency_overrides.clear()


def test_put_configuration_rejects_unknown_fields_and_numeric_strings(tmp_path):
    client = _client_for(tmp_path / ".env")

    unknown = client.put("/api/config/advanced", json={"arbitrary_env": "secret"})
    coerced = client.put("/api/config/advanced", json={"llm_max_workers": "8"})

    assert unknown.status_code == 422
    assert coerced.status_code == 422
    app.dependency_overrides.clear()


def test_ifind_explicit_null_fields_are_rejected_without_persisting(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("IFIND_USERNAME=existing\n", encoding="utf-8")
    client = _client_for(env_path)

    username_response = client.put("/api/config/ifind", json={"username": None})
    url_response = client.put("/api/config/ifind", json={"http_base_url": None})

    assert username_response.status_code == 422
    assert url_response.status_code == 422
    assert env_path.read_text(encoding="utf-8") == "IFIND_USERNAME=existing\n"
    assert "None" not in env_path.read_text(encoding="utf-8")
    app.dependency_overrides.clear()


def test_validation_error_response_never_echoes_rejected_secret(tmp_path):
    client = _client_for(tmp_path / ".env")
    rejected_secret = "TOPSECRET" + ("x" * 9000) + "LEAKME"

    response = client.put(
        "/api/config/ifind",
        json={"username": "tester", "password": rejected_secret},
    )

    assert response.status_code == 422
    assert "TOPSECRET" not in response.text
    assert "LEAKME" not in response.text
    assert "input" not in response.text
    assert "ctx" not in response.text
    assert "url" not in response.text
    app.dependency_overrides.clear()


def test_put_database_returns_restart_required(tmp_path):
    client = _client_for(tmp_path / ".env")

    response = client.put("/api/config/database", json={"database_url": "sqlite:////tmp/next.db"})

    assert response.status_code == 200
    assert response.json()["applied"] is False
    assert response.json()["restart_required"] is True
    assert "sqlite:////tmp/next.db" not in response.text
    app.dependency_overrides.clear()


def test_configuration_test_does_not_persist_candidate_secret(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# existing\n", encoding="utf-8")
    client = _client_for(env_path, connection_probes={"ifind": lambda candidate, timeout: True})

    response = client.post(
        "/api/config/ifind/test",
        json={"username": "tester", "password": "temporary-secret", "backend": "python_sdk"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "temporary-secret" not in env_path.read_text(encoding="utf-8")
    app.dependency_overrides.clear()


def test_configuration_test_failure_is_generic_and_does_not_leak_probe_error(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# existing\n", encoding="utf-8")

    def failed_probe(candidate, timeout):
        raise RuntimeError("https://example.test/check?token=LEAKME&password=TOPSECRET")

    client = _client_for(env_path, connection_probes={"ifind": failed_probe})

    response = client.post(
        "/api/config/ifind/test",
        json={"username": "tester", "password": "temporary-secret", "backend": "python_sdk"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": False, "message": "连接验证失败"}
    assert "TOPSECRET" not in response.text
    assert "LEAKME" not in response.text
    assert env_path.read_text(encoding="utf-8") == "# existing\n"
    app.dependency_overrides.clear()


def test_configuration_rejects_unknown_section(tmp_path):
    client = _client_for(tmp_path / ".env")

    response = client.put("/api/config/secrets", json={})

    assert response.status_code == 422
    app.dependency_overrides.clear()
