"""回归测试：timing API 前后端契约一致性。

Issue #1: 修复前端 GET 与后端 POST 的 HTTP 方法不匹配问题。
"""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.timing import get_signal_repo, get_timing_repo

client = TestClient(app)


def _make_mock_signal_repo(signal=None):
    """创建 mock SignalRepository，get 返回指定信号"""
    repo = MagicMock()
    repo.get.return_value = signal
    return repo


def _make_mock_timing_repo():
    """创建 mock TimingRepository，save 直接返回传入的 decision"""
    repo = MagicMock()
    repo.save.side_effect = lambda decision: decision
    return repo


class TestTimingAPIContract:
    """验证 /api/timing/evaluate-signal 端点的 HTTP 方法契约。"""

    def test_post_returns_timing_decision(self):
        """POST /api/timing/evaluate-signal/{signal_id} 应返回 TimingDecision。"""
        mock_signal = MagicMock()
        mock_signal.model_dump.return_value = {"signal_id": "sig-001", "thesis": "test"}
        mock_signal_repo = _make_mock_signal_repo(signal=mock_signal)
        mock_timing_repo = _make_mock_timing_repo()

        app.dependency_overrides[get_signal_repo] = lambda: mock_signal_repo
        app.dependency_overrides[get_timing_repo] = lambda: mock_timing_repo
        try:
            resp = client.post("/api/timing/evaluate-signal/sig-001")
            assert resp.status_code == 200
            data = resp.json()
            # TimingDecision 必须包含 action 字段
            assert "action" in data
            assert data["action"] in ("enter", "wait", "reduce", "exit", "block")
        finally:
            app.dependency_overrides.clear()

    def test_post_signal_not_found_returns_404(self):
        """POST /api/timing/evaluate-signal/{signal_id} 在信号不存在时应返回 404。"""
        mock_signal_repo = _make_mock_signal_repo(signal=None)
        mock_timing_repo = _make_mock_timing_repo()

        app.dependency_overrides[get_signal_repo] = lambda: mock_signal_repo
        app.dependency_overrides[get_timing_repo] = lambda: mock_timing_repo
        try:
            resp = client.post("/api/timing/evaluate-signal/nonexistent-signal")
            assert resp.status_code == 404
            data = resp.json()
            assert "not found" in data["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_method_returns_405(self):
        """GET /api/timing/evaluate-signal/{signal_id} 应返回 405 Method Not Allowed。

        这确保前端不会再因使用 GET 方法而静默失败。
        """
        resp = client.get("/api/timing/evaluate-signal/sig-001")
        assert resp.status_code == 405
