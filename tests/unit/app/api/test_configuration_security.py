# tests/unit/app/api/test_configuration_security.py
"""Configuration control-plane local access tests."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.configuration_security import require_configuration_origin_only


def _loopback_request(host: str = "127.0.0.1") -> Mock:
    return Mock(client=Mock(host=host))


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
