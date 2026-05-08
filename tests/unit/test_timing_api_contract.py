"""回归测试：timing API 前后端契约一致性。

Issue #1: 修复前端 GET 与后端 POST 的 HTTP 方法不匹配问题。
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestTimingAPIContract:
    """验证 /api/timing/evaluate-signal 端点的 HTTP 方法契约。"""

    def test_post_returns_timing_decision(self):
        """POST /api/timing/evaluate-signal/{signal_id} 应返回 TimingDecision。"""
        mock_signal = MagicMock()
        mock_signal.model_dump.return_value = {"signal_id": "sig-001", "thesis": "test"}

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_signal.return_value = mock_signal
        MockSignalService = MagicMock(return_value=mock_svc_instance)

        # 配置 get_db 生成器
        mock_db = MagicMock()
        mock_db_gen = MagicMock()
        mock_db_gen.__next__ = MagicMock(side_effect=[mock_db, StopIteration()])

        with patch("core.services.signal_service.SignalService", MockSignalService), \
             patch("data_layer.repositories.signal_repository.SignalRepositoryImpl"), \
             patch("data_layer.repositories.base.get_db", return_value=mock_db_gen):
            resp = client.post("/api/timing/evaluate-signal/sig-001")
            assert resp.status_code == 200
            data = resp.json()
            # TimingDecision 必须包含 action 字段
            assert "action" in data
            assert data["action"] in ("enter", "wait", "reduce", "exit", "block")

    def test_post_signal_not_found_returns_404(self):
        """POST /api/timing/evaluate-signal/{signal_id} 在信号不存在时应返回 404。"""
        mock_svc_instance = MagicMock()
        mock_svc_instance.get_signal.return_value = None
        MockSignalService = MagicMock(return_value=mock_svc_instance)

        # 配置 get_db 生成器
        mock_db = MagicMock()
        mock_db_gen = MagicMock()
        mock_db_gen.__next__ = MagicMock(side_effect=[mock_db, StopIteration()])

        with patch("core.services.signal_service.SignalService", MockSignalService), \
             patch("data_layer.repositories.signal_repository.SignalRepositoryImpl"), \
             patch("data_layer.repositories.base.get_db", return_value=mock_db_gen):
            resp = client.post("/api/timing/evaluate-signal/nonexistent-signal")
            assert resp.status_code == 404
            data = resp.json()
            assert "not found" in data["detail"].lower()

    def test_get_method_returns_405(self):
        """GET /api/timing/evaluate-signal/{signal_id} 应返回 405 Method Not Allowed。

        这确保前端不会再因使用 GET 方法而静默失败。
        """
        resp = client.get("/api/timing/evaluate-signal/sig-001")
        assert resp.status_code == 405
