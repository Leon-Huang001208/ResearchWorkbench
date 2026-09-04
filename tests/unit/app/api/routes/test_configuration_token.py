# tests/unit/app/api/routes/test_configuration_token.py
"""GET /api/config/token 端点的单元测试"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.routes.configuration import get_configuration_service, router
from core.settings.config import Settings
from core.settings.runtime import RuntimeContext
from services.configuration_service import ConfigurationService


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


class TestGetConfigToken:
    """GET /api/config/token 端点"""

    def test_returns_token_without_csrf_header(self, client):
        """不带 X-Research Workbench-Config-Token 也能拿到 token"""
        resp = client.get("/api/config/token")
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token"] == CONFIGURATION_CSRF_TOKEN

    def test_token_is_string(self, client):
        """token 字段是字符串"""
        resp = client.get("/api/config/token")
        assert isinstance(resp.json()["token"], str)
        assert len(resp.json()["token"]) > 16

    def test_external_origin_blocked(self, client):
        """外部 Origin 应被 403 拦截"""
        resp = client.get(
            "/api/config/token",
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_localhost_origin_allowed(self, client):
        """localhost origin 可以拿到 token"""
        resp = client.get(
            "/api/config/token",
            headers={"Origin": "http://localhost:8765"},
        )
        assert resp.status_code == 200

    def test_existing_config_get_still_requires_csrf(self, client):
        """原有 GET /api/config 没有 token 还是 403"""
        resp = client.get("/api/config")
        assert resp.status_code == 403

    def test_config_get_serializes_real_snapshot_without_secrets(
        self, client, monkeypatch, tmp_path
    ):
        """GET /api/config does not leak real file-backed configuration secrets."""
        database_url = (
            "postgresql+psycopg://route-user:route-database-password@"
            "route-db.internal:5432/configuration"
        )
        api_key = "sk-route-real-api-key"
        for key in (
            "DATABASE_URL",
            "LLM_PROVIDER_1_NAME",
            "LLM_PROVIDER_1_PROTOCOL",
            "LLM_PROVIDER_1_BASE_URL",
            "LLM_PROVIDER_1_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    f"DATABASE_URL={database_url}",
                    "LLM_PROVIDER_1_NAME=route-provider",
                    "LLM_PROVIDER_1_PROTOCOL=openai_compatible",
                    "LLM_PROVIDER_1_BASE_URL=https://api.example.invalid/v1",
                    f"LLM_PROVIDER_1_API_KEY={api_key}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        runtime_context = RuntimeContext(
            mode="desktop",
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            env_path=env_path,
            backend_url="http://127.0.0.1:8765",
            can_write_config=True,
        )
        service = ConfigurationService(
            env_path=env_path,
            runtime_settings=Settings(LOG_DIR=tmp_path / "logs"),
            runtime_context=runtime_context,
        )
        client.app.dependency_overrides[get_configuration_service] = lambda: service

        response = client.get(
            "/api/config",
            headers={
                "Origin": "http://localhost:8765",
                "X-Research Workbench-Config-Token": CONFIGURATION_CSRF_TOKEN,
            },
        )

        assert response.status_code == 200
        serialized = response.text
        response_data = response.json()
        assert response_data["catalog"]["sections"][0]["key"] == "llm"
        assert response_data["environment"]["runtime_mode"] == "desktop"
        database_secret = response_data["sections"]["database"]["database_url"]
        api_key_secret = response_data["sections"]["llm"]["providers"][0]["api_key"]
        assert set(database_secret) == {
            "configured",
            "masked_value",
        }
        assert set(api_key_secret) == {
            "configured",
            "masked_value",
        }
        assert database_secret["configured"] is True
        assert api_key_secret["configured"] is True
        assert "route-database-password" not in serialized
        assert database_url not in serialized
        assert api_key not in serialized
