# tests/unit/app/api/test_configuration_security.py
"""require_configuration_origin_only 依赖的单元测试"""

import pytest
from fastapi import HTTPException

from app.api.configuration_security import require_configuration_origin_only


class TestRequireConfigurationOriginOnly:
    """只校验 Origin/Host，不校验 CSRF token"""

    def test_no_origin_passes(self):
        """无 Origin 头时（同源 Tauri 请求）应通过"""
        require_configuration_origin_only(origin=None)

    def test_localhost_origin_passes(self):
        """localhost origin 应通过"""
        require_configuration_origin_only(origin="http://localhost:8765")

    def test_127_origin_passes(self):
        """127.0.0.1 origin 应通过"""
        require_configuration_origin_only(origin="http://127.0.0.1:8765")

    def test_ipv6_loopback_origin_passes(self):
        """IPv6 loopback (::1) origin 应通过"""
        require_configuration_origin_only(origin="http://[::1]:8765")

    def test_tauri_origin_passes(self):
        """Tauri 本地 origin 应通过"""
        require_configuration_origin_only(origin="tauri://localhost")

    def test_tauri_http_origin_passes(self):
        """Tauri http origin 应通过"""
        require_configuration_origin_only(origin="http://tauri.localhost")

    def test_tauri_https_origin_passes(self):
        """Tauri https origin 应通过"""
        require_configuration_origin_only(origin="https://tauri.localhost")

    def test_external_origin_forbidden(self):
        """外部 origin 应返回 403"""
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(origin="https://evil.example.com")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"

    def test_arbitrary_http_origin_forbidden(self):
        """任意非白名单 http origin 应返回 403"""
        with pytest.raises(HTTPException) as exc_info:
            require_configuration_origin_only(origin="http://192.168.1.100:8765")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"
