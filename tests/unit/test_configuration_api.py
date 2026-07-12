"""系统配置 API 契约与错误处理测试。"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.configuration import get_configuration_service
from services.configuration_service import ConfigurationService


def _client_for(path: Path) -> TestClient:
    service = ConfigurationService(env_path=path)
    app.dependency_overrides[get_configuration_service] = lambda: service
    return TestClient(app)


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
    client = _client_for(env_path)

    response = client.post(
        "/api/config/ifind/test",
        json={"username": "tester", "password": "temporary-secret", "backend": "python_sdk"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "temporary-secret" not in env_path.read_text(encoding="utf-8")
    app.dependency_overrides.clear()


def test_configuration_rejects_unknown_section(tmp_path):
    client = _client_for(tmp_path / ".env")

    response = client.put("/api/config/secrets", json={})

    assert response.status_code == 422
    app.dependency_overrides.clear()
