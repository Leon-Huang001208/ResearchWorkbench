# tests/unit/app/api/test_configuration_security.py
"""Configuration control-plane local access tests."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.configuration_security import require_configuration_origin_only
from app.api.configuration_models import ConfigurationSnapshotResponse


def _loopback_request(host: str = "127.0.0.1") -> Mock:
    return Mock(client=Mock(host=host))


def _minimal_configuration_snapshot() -> dict:
    """Return a complete, value-free configuration snapshot contract fixture."""
    return {
        "sections": {
            "llm": {"providers": [], "task_routes": []},
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


class TestRequireConfigurationOriginOnly:
    """Configuration token issuance is restricted to the local machine."""

    def test_no_origin_passes_for_loopback_client(self):
        require_configuration_origin_only(request=_loopback_request(), origin=None)

    def test_localhost_origin_passes(self):
        require_configuration_origin_only(
            request=_loopback_request(), origin="http://localhost:8765"
        )

    def test_127_origin_passes(self):
        require_configuration_origin_only(
            request=_loopback_request(), origin="http://127.0.0.1:8765"
        )

    def test_ipv6_loopback_origin_passes(self):
        require_configuration_origin_only(
            request=_loopback_request("::1"), origin="http://[::1]:8765"
        )

    def test_tauri_origin_passes(self):
        require_configuration_origin_only(request=_loopback_request(), origin="tauri://localhost")

    def test_tauri_http_origin_passes(self):
        require_configuration_origin_only(
            request=_loopback_request(), origin="http://tauri.localhost"
        )

    def test_tauri_https_origin_passes(self):
        require_configuration_origin_only(
            request=_loopback_request(), origin="https://tauri.localhost"
        )

    def test_external_origin_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(
                request=_loopback_request(), origin="https://evil.example.com"
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"

    def test_non_loopback_client_is_forbidden_without_origin(self):
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(
                request=_loopback_request("192.168.1.100"), origin=None
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"


def test_snapshot_response_accepts_complete_catalog_and_environment_contract():
    """The API response model accepts the service's complete safe capability snapshot."""
    snapshot = ConfigurationSnapshotResponse.model_validate(_minimal_configuration_snapshot())

    assert snapshot.catalog.sections[0].fields[0].environment_keys == ["DATABASE_URL"]
    assert snapshot.environment.capabilities[0].status == "not_detected"
