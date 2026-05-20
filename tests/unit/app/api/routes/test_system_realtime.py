"""Health + Realtime API 端点测试"""


class TestSystemHealthEndpoint:
    """测试 /api/system/health 端点"""

    def test_minimal_health_returns_ok(self):
        import asyncio

        from app.api.routes.system import get_health_minimal

        result = asyncio.run(get_health_minimal())
        assert result["status"] == "ok"
        assert "worker_heartbeats" in result
        assert "timestamp" in result


class TestRealtimeStream:
    """测试 /api/realtime/stream 端点"""

    def test_router_imports(self):
        from app.api.routes.realtime import router

        assert router.prefix == "/api/realtime"
        assert "realtime" in router.tags
