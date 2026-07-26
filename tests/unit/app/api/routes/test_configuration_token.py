# tests/unit/app/api/routes/test_configuration_token.py
"""GET /api/config/token 端点的单元测试"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.routes.configuration import get_configuration_service, router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


def _safe_snapshot() -> dict:
    """Return the complete snapshot returned by the dependency-overridden service."""
    return {
        "sections": {
            "llm": {
                "providers": [
                    {
                        "original_name": "primary",
                        "name": "primary",
                        "protocol": "openai_compatible",
                        "base_url": "https://api.example.invalid",
                        "api_key": {"configured": True, "masked_value": "********"},
                    }
                ],
                "task_routes": [],
            },
            "zhiqiu": {
                "accounts": [],
                "enabled": False,
                "rotation_strategy": "round_robin",
                "max_retries": 0,
                "retry_delay": 0,
                "lease_timeout": 1,
                "max_consecutive_failures": 1,
            },
            "ifind": {
                "accounts": [],
                "username": "",
                "password": {"configured": False, "masked_value": None},
                "backend": "auto",
                "http_base_url": "",
            },
            "database": {
                "database_url": {"configured": True, "masked_value": "********"},
                "restart_required": True,
            },
            "advanced": {
                "log_level": "INFO",
                "log_dir": "logs",
                "llm_max_workers": 1,
                "llm_max_retries": 0,
                "chunk_size": 256,
                "chunk_overlap": 0,
                "long_text_threshold": 1,
            },
            "web_search": {
                "accounts": [],
                "provider": "tavily",
                "rotation_strategy": "round_robin",
                "quota_limit": 1,
                "max_results": 1,
                "timeout": 1,
            },
        },
        "readiness": {
            "llm": False,
            "zhiqiu": False,
            "ifind": False,
            "database": False,
            "advanced": True,
            "web_search": False,
        },
        "ready_count": 1,
        "total_count": 6,
        "environment_locked_fields": [],
        "catalog": {
            "sections": [
                {
                    "key": "database",
                    "label": "数据库",
                    "scope": "storage",
                    "platforms": ["desktop"],
                    "restart_required": True,
                    "testable": True,
                    "fields": [
                        {
                            "key": "database_url",
                            "label": "数据库连接地址",
                            "kind": "secret",
                            "environment_keys": ["DATABASE_URL"],
                        }
                    ],
                }
            ]
        },
        "environment": {
            "platform": "linux",
            "architecture": "x64",
            "runtime_mode": "desktop",
            "paths": {"config": None, "data": None, "logs": None},
            "capabilities": [
                {
                    "key": "postgresql_client",
                    "label": "PostgreSQL 客户端",
                    "status": "not_detected",
                    "detail": "未检测到 psql 客户端。",
                    "remediation": ["安装 PostgreSQL 客户端。"],
                }
            ],
        },
    }


class _SnapshotService:
    """Dependency override that avoids any real configuration database or environment."""

    def get_snapshot(self) -> dict:
        return _safe_snapshot()


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

    def test_config_get_serializes_capability_snapshot_without_secrets(self, client):
        """GET /api/config serializes catalog and environment through the real route."""
        client.app.dependency_overrides[get_configuration_service] = _SnapshotService

        response = client.get(
            "/api/config",
            headers={"X-AlphaFoundry-Config-Token": CONFIGURATION_CSRF_TOKEN},
        )

        assert response.status_code == 200
        serialized = response.text
        assert response.json()["catalog"]["sections"][0]["key"] == "database"
        assert response.json()["environment"]["capabilities"][0]["status"] == "not_detected"
        assert set(response.json()["sections"]["database"]["database_url"]) == {
            "configured",
            "masked_value",
        }
        assert set(response.json()["sections"]["llm"]["providers"][0]["api_key"]) == {
            "configured",
            "masked_value",
        }
        assert "postgresql://user:database-password@localhost/configuration" not in serialized
        assert "sk-live-api-key" not in serialized
