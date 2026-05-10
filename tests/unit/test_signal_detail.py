"""信号详情、审计轨迹、全局搜索 API 测试"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from core.contracts import AlphaSignal

client = TestClient(app)


# ─── 信号详情 API ──────────────────────────────────────────


class TestSignalDetailAPI:
    def test_get_signal_detail_success(self):
        """信号详情 API 应返回完整关联数据"""
        mock_service = MagicMock()
        mock_signal = AlphaSignal(
            signal_id="sig-detail-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试信号详情",
            score=0.8,
            confidence=0.7,
            status="candidate",
        )
        mock_service.get_signal.return_value = mock_signal

        from app.api.routes.signals import get_signal_service

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            # Patch all the DB accesses inside the detail endpoint
            with patch("data_layer.repositories.base.SessionLocal") as mock_session_cls:
                mock_db = MagicMock()
                mock_session_cls.return_value = mock_db
                # All .query().filter().first() / .query().filter().order_by().first() return None
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
                    None
                )

                resp = client.get("/api/signals/sig-detail-001/detail")
                assert resp.status_code == 200
                data = resp.json()
                assert data["signal"]["signal_id"] == "sig-detail-001"
                assert data["signal"]["thesis"] == "测试信号详情"
                assert data["signal"]["score"] == 0.8
                assert data["timing"] is None
                assert data["outcome"] is None
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_get_signal_detail_not_found(self):
        """不存在的信号应返回 404"""
        mock_service = MagicMock()
        mock_service.get_signal.return_value = None

        from app.api.routes.signals import get_signal_service

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.get("/api/signals/nonexistent/detail")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_signal_service, None)


# ─── 审计轨迹 API ──────────────────────────────────────────


class TestAuditTrailAPI:
    def test_get_audit_trail(self):
        """审计轨迹 API 应返回指定实体的操作历史"""
        mock_service = MagicMock()
        mock_service.get_trail.return_value = [
            {
                "log_id": "log-001",
                "entity_type": "signal",
                "entity_id": "sig-001",
                "action": "created",
                "actor": "system",
                "details": {"status": "research_only"},
                "timestamp": "2026-05-05T12:00:00+00:00",
            }
        ]

        from app.api.routes.audit import get_audit_service

        app.dependency_overrides[get_audit_service] = lambda: mock_service
        try:
            resp = client.get("/api/audit/trail/signal/sig-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity_type"] == "signal"
            assert data["entity_id"] == "sig-001"
            assert len(data["trail"]) == 1
            assert data["trail"][0]["action"] == "created"
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    def test_get_audit_trail_invalid_entity_type(self):
        """无效的 entity_type 应返回 400"""
        resp = client.get("/api/audit/trail/invalid_type/some-id")
        assert resp.status_code == 400

    def test_get_audit_trail_empty(self):
        """无审计记录的实体应返回空列表"""
        mock_service = MagicMock()
        mock_service.get_trail.return_value = []

        from app.api.routes.audit import get_audit_service

        app.dependency_overrides[get_audit_service] = lambda: mock_service
        try:
            resp = client.get("/api/audit/trail/signal/sig-noaudit")
            assert resp.status_code == 200
            data = resp.json()
            assert data["trail"] == []
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    def test_record_audit_log(self):
        """手动记录审计日志"""
        mock_service = MagicMock()
        mock_service.record.return_value = {
            "log_id": "log-002",
            "entity_type": "signal",
            "entity_id": "sig-002",
            "action": "status_changed",
            "actor": "api",
            "details": {"old": "research_only", "new": "candidate"},
            "timestamp": "2026-05-05T13:00:00+00:00",
        }

        from app.api.routes.audit import get_audit_service

        app.dependency_overrides[get_audit_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/audit/record",
                params={
                    "entity_type": "signal",
                    "entity_id": "sig-002",
                    "action": "status_changed",
                    "actor": "api",
                    "details": '{"old": "research_only", "new": "candidate"}',
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["log_id"] == "log-002"
            assert data["action"] == "status_changed"
        finally:
            app.dependency_overrides.pop(get_audit_service, None)

    def test_record_audit_log_invalid_type(self):
        """记录审计日志时无效的 entity_type 应返回 400"""
        resp = client.post(
            "/api/audit/record",
            params={
                "entity_type": "invalid",
                "entity_id": "some-id",
                "action": "test",
            },
        )
        assert resp.status_code == 400


# ─── 全局搜索 API ──────────────────────────────────────────


class TestGlobalSearchAPI:
    def test_search_returns_all_groups(self):
        """全局搜索应返回所有分组（信号/事件/Outcome/审核）"""
        with patch("app.api.routes.search._search_signals") as mock_sig, patch(
            "app.api.routes.search._search_events"
        ) as mock_evt, patch("app.api.routes.search._search_outcomes") as mock_out, patch(
            "app.api.routes.search._search_reviews"
        ) as mock_rev:
            mock_sig.return_value = [
                {"signal_id": "s1", "thesis": "test thesis", "score": 0.8, "status": "candidate"}
            ]
            mock_evt.return_value = []
            mock_out.return_value = [{"outcome_id": "o1", "lesson": "test lesson"}]
            mock_rev.return_value = []

            resp = client.get("/api/search?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert "signals" in data
            assert "events" in data
            assert "outcomes" in data
            assert "reviews" in data
            assert len(data["signals"]) == 1
            assert len(data["outcomes"]) == 1

    def test_search_with_type_filter(self):
        """带类型过滤的搜索应只返回指定类型"""
        with patch("app.api.routes.search._search_signals") as mock_sig, patch(
            "app.api.routes.search._search_events"
        ) as mock_evt:
            mock_sig.return_value = [
                {"signal_id": "s1", "thesis": "test", "score": 0.8, "status": "candidate"}
            ]
            mock_evt.return_value = []

            resp = client.get("/api/search?q=test&types=signal,event")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["signals"]) == 1
            # outcomes and reviews should be empty when not in type filter
            assert data["outcomes"] == []
            assert data["reviews"] == []

    def test_search_invalid_type(self):
        """无效的搜索类型应返回 400"""
        resp = client.get("/api/search?q=test&types=invalid_type")
        assert resp.status_code == 400

    def test_search_missing_query(self):
        """缺少搜索关键词应返回 422"""
        resp = client.get("/api/search")
        assert resp.status_code == 422

    def test_search_empty_results(self):
        """搜索无匹配时返回空分组"""
        with patch("app.api.routes.search._search_signals") as mock_sig, patch(
            "app.api.routes.search._search_events"
        ) as mock_evt, patch("app.api.routes.search._search_outcomes") as mock_out, patch(
            "app.api.routes.search._search_reviews"
        ) as mock_rev:
            mock_sig.return_value = []
            mock_evt.return_value = []
            mock_out.return_value = []
            mock_rev.return_value = []

            resp = client.get("/api/search?q=nothingmatchesthis")
            assert resp.status_code == 200
            data = resp.json()
            assert data["signals"] == []
            assert data["events"] == []
            assert data["outcomes"] == []
            assert data["reviews"] == []


# ─── AuditService 单元测试 ────────────────────────────────


class TestAuditService:
    def test_record_and_get_trail_in_memory(self):
        """AuditService 内存版应能记录和查询审计日志"""
        from core.services.audit_service import AuditService

        service = AuditService()  # no repository → in-memory

        service.record("signal", "sig-001", "created", actor="test")
        service.record(
            "signal",
            "sig-001",
            "status_changed",
            actor="test",
            details={"old": "research_only", "new": "candidate"},
        )

        trail = service.get_trail("signal", "sig-001")
        assert len(trail) == 2
        # Memory fallback returns in insertion order; both actions should be present
        actions = [t["action"] for t in trail]
        assert "created" in actions
        assert "status_changed" in actions

    def test_search_in_memory(self):
        """AuditService 内存版搜索功能"""
        from core.services.audit_service import AuditService

        service = AuditService()

        service.record("signal", "sig-001", "created", details={"thesis": "黄金看涨"})
        service.record("outcome", "out-001", "recorded", details={"lesson": "黄金看涨失败"})

        results = service.search("黄金")
        assert len(results) >= 1

    def test_get_trail_nonexistent(self):
        """查询不存在的实体审计轨迹应返回空列表"""
        from core.services.audit_service import AuditService

        service = AuditService()

        trail = service.get_trail("signal", "nonexistent")
        assert trail == []
