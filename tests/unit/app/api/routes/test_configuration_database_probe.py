"""Database configuration probe API tests."""

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.configuration_models import ConfigurationTestResponse
from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
from app.api.routes.configuration import get_configuration_service, router
from core.settings.config import Settings
from services import configuration_service
from services.configuration_service import ConfigurationService
from services.database_readiness import DatabaseReadiness, DatabaseReadinessCode


def test_database_probe_api_accepts_valid_csrf_and_returns_readiness_contract(
    monkeypatch, tmp_path
):
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
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_configuration_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=True)

    response = client.post(
        "/api/config/database/test",
        json={"database_url": database_url},
        headers={
            "Origin": "http://localhost:8765",
            "X-AlphaFoundry-Config-Token": CONFIGURATION_CSRF_TOKEN,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "数据库连接正常，pgvector 已就绪。",
        "code": "ready",
        "remediation": ["无需处理。"],
    }
    probe.assert_called_once_with(database_url, service.connection_timeout)


def test_configuration_test_response_defaults_keep_other_sections_compatible():
    response = ConfigurationTestResponse(success=True, message="连接验证成功")

    assert response.model_dump() == {
        "success": True,
        "message": "连接验证成功",
        "code": None,
        "remediation": [],
    }
