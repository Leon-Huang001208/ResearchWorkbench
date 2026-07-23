# tests/unit/app/api/routes/test_configuration_token.py
"""GET /api/config/token 端点的单元测试"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.routes.configuration import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


class TestGetConfigToken:
    """GET /api/config/token 端点"""

    def test_returns_token_without_csrf_header(self, client):
        """不带 X-AlphaFoundry-Config-Token 也能拿到 token"""
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
