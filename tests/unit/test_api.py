"""API 端点测试"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.assets import get_asset_service
from app.api.routes.scenarios import get_scenario_service
from app.api.routes.review import get_review_service
from app.api.routes.signals import get_signal_service
from app.api.routes.ingest import get_ingest_service
from core.contracts import AssetAnalysisSnapshot, AlphaSignal, ScenarioSet, ScenarioHypothesis

client = TestClient(app)


# ─── 健康检查 ───────────────────────────────────────────

class TestHealthCheck:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_index(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "AlphaFoundry" in resp.text


# ─── 资产分析 ───────────────────────────────────────────

class TestAssetsAPI:
    def test_analyze_asset(self):
        mock_service = MagicMock()
        mock_snapshot = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of="2026-05-05T12:00:00Z",
            financial={"revenue": {"ttm": 15000000000}},
            valuation={"pe_ttm": 24.9},
        )
        mock_service.generate_snapshot.return_value = mock_snapshot

        app.dependency_overrides[get_asset_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/assets/analyze",
                json={"canonical_id": "600000.SH", "source": "mock"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["canonical_id"] == "600000.SH"
            assert "financial" in data
            assert "valuation" in data
        finally:
            app.dependency_overrides.pop(get_asset_service, None)

    def test_get_asset_snapshot(self):
        mock_service = MagicMock()
        mock_snapshot = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of="2026-05-05T12:00:00Z",
            valuation={"pe_ttm": 24.9},
        )
        mock_service.get_latest_snapshot.return_value = mock_snapshot

        app.dependency_overrides[get_asset_service] = lambda: mock_service
        try:
            resp = client.get("/api/assets/600000.SH")
            assert resp.status_code == 200
            data = resp.json()
            assert data["canonical_id"] == "600000.SH"
        finally:
            app.dependency_overrides.pop(get_asset_service, None)

    def test_get_asset_snapshot_not_found(self):
        mock_service = MagicMock()
        mock_service.get_latest_snapshot.return_value = None

        app.dependency_overrides[get_asset_service] = lambda: mock_service
        try:
            resp = client.get("/api/assets/NOTEXIST")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_asset_service, None)

    def test_analyze_with_as_of(self):
        mock_service = MagicMock()
        mock_snapshot = AssetAnalysisSnapshot(
            canonical_id="000001.SZ",
            as_of="2026-01-01T00:00:00Z",
        )
        mock_service.generate_snapshot.return_value = mock_snapshot

        app.dependency_overrides[get_asset_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/assets/analyze",
                json={
                    "canonical_id": "000001.SZ",
                    "as_of": "2026-01-01T00:00:00Z",
                    "source": "mock",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["canonical_id"] == "000001.SZ"
        finally:
            app.dependency_overrides.pop(get_asset_service, None)


# ─── 情景分析 ───────────────────────────────────────────

class TestScenariosAPI:
    def test_generate_scenarios(self):
        mock_service = MagicMock()
        mock_scenario_set = ScenarioSet(
            set_id="set-001",
            question="黄金价格走势",
            hypotheses=[
                ScenarioHypothesis(
                    scenario_id="h1",
                    title="看涨",
                    horizon="mid",
                    probability=0.4,
                    confidence=0.7,
                    assumptions=["美联储降息"],
                ),
            ],
            normalization_check=True,
        )
        mock_service.generate_scenario_set.return_value = mock_scenario_set

        app.dependency_overrides[get_scenario_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/scenarios/generate",
                json={"topic": "黄金价格走势"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["set_id"] == "set-001"
            assert data["question"] == "黄金价格走势"
            assert len(data["hypotheses"]) == 1
            assert data["hypotheses"][0]["title"] == "看涨"
        finally:
            app.dependency_overrides.pop(get_scenario_service, None)

    def test_get_scenario_set_not_found(self):
        resp = client.get("/api/scenarios/nonexistent")
        assert resp.status_code == 404


# ─── 审核 ───────────────────────────────────────────────

class TestReviewAPI:
    def test_list_pending_empty(self):
        mock_service = MagicMock()
        mock_service.list_pending_assertions.return_value = []

        app.dependency_overrides[get_review_service] = lambda: mock_service
        try:
            resp = client.get("/api/review/pending")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.pop(get_review_service, None)

    def test_review_stats(self):
        mock_service = MagicMock()
        mock_service.get_statistics.return_value = {
            "pending_assertions": 5,
            "approved_assertions": 10,
            "rejected_assertions": 2,
            "pending_events": 0,
        }

        app.dependency_overrides[get_review_service] = lambda: mock_service
        try:
            resp = client.get("/api/review/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pending_assertions"] == 5
            assert data["approved_assertions"] == 10
        finally:
            app.dependency_overrides.pop(get_review_service, None)

    def test_approve_item(self):
        mock_service = MagicMock()
        mock_service.approve_assertion.return_value = True

        app.dependency_overrides[get_review_service] = lambda: mock_service
        try:
            resp = client.post("/api/review/approve/assertion-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "approved"
            assert data["success"] is True
        finally:
            app.dependency_overrides.pop(get_review_service, None)

    def test_reject_item(self):
        mock_service = MagicMock()
        mock_service.reject_assertion.return_value = True

        app.dependency_overrides[get_review_service] = lambda: mock_service
        try:
            resp = client.post("/api/review/reject/assertion-002")
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "rejected"
            assert data["success"] is True
        finally:
            app.dependency_overrides.pop(get_review_service, None)

    def test_approve_not_found(self):
        mock_service = MagicMock()
        mock_service.approve_assertion.return_value = False

        app.dependency_overrides[get_review_service] = lambda: mock_service
        try:
            resp = client.post("/api/review/approve/nonexistent")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_review_service, None)


# ─── 信号 ───────────────────────────────────────────────

class TestSignalsAPI:
    def test_create_signal(self):
        mock_service = MagicMock()
        mock_signal = AlphaSignal(
            signal_id="sig-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="黄金看涨",
            score=0.8,
            confidence=0.7,
            status="research_only",
        )
        mock_service.create_signal.return_value = mock_signal

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/signals/create",
                json={
                    "subject_id": "600000.SH",
                    "thesis": "黄金看涨",
                    "horizon": "20d",
                    "score": 0.8,
                    "confidence": 0.7,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["signal_id"] == "sig-001"
            assert data["thesis"] == "黄金看涨"
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_list_signals(self):
        mock_service = MagicMock()
        mock_service.list_signals.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.get("/api/signals/list")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_validate_signal(self):
        mock_service = MagicMock()
        mock_signal = AlphaSignal(
            signal_id="sig-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试",
            score=0.5,
            confidence=0.5,
        )
        mock_service.get_signal.return_value = mock_signal
        mock_service.validate_signal.return_value = {
            "signal_id": "sig-001",
            "composite_score": 0.65,
            "features": {"f1": 1.0},
            "backtest": {"sharpe": 1.2},
            "validated_at": "2026-05-05T12:00:00",
        }

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.post("/api/signals/validate/sig-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["composite_score"] == 0.65
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_validate_signal_not_found(self):
        mock_service = MagicMock()
        mock_service.get_signal.return_value = None

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.post("/api/signals/validate/nonexistent")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_promote_signal(self):
        mock_service = MagicMock()
        mock_signal = AlphaSignal(
            signal_id="sig-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试",
            score=0.5,
            confidence=0.5,
            status="research_only",
        )
        mock_service.get_signal.return_value = mock_signal
        promoted_signal = AlphaSignal(
            signal_id="sig-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试",
            score=0.5,
            confidence=0.5,
            status="candidate",
        )
        mock_service.promote_signal.return_value = promoted_signal

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.post("/api/signals/promote/sig-001?new_status=candidate")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["new_status"] == "candidate"
        finally:
            app.dependency_overrides.pop(get_signal_service, None)

    def test_promote_signal_not_found(self):
        mock_service = MagicMock()
        mock_service.get_signal.return_value = None

        app.dependency_overrides[get_signal_service] = lambda: mock_service
        try:
            resp = client.post("/api/signals/promote/nonexistent")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_signal_service, None)


# ─── 摄入 ───────────────────────────────────────────────

class TestIngestAPI:
    def test_ingest_text(self):
        mock_service = MagicMock()
        mock_service.ingest_text.return_value = {
            "doc_id": "doc-001",
            "title": "测试文档",
            "assertions_extracted": 3,
            "assertions_approved": 2,
            "assertions_pending": 1,
            "events_extracted": 1,
            "events_approved": 1,
            "events_pending": 0,
        }

        app.dependency_overrides[get_ingest_service] = lambda: mock_service
        try:
            resp = client.post(
                "/api/ingest/text",
                json={
                    "text": "这是测试文本",
                    "source_type": "report",
                    "source_name": "test",
                    "title": "测试文档",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["doc_id"] == "doc-001"
            assert data["assertions_extracted"] == 3
        finally:
            app.dependency_overrides.pop(get_ingest_service, None)


# ─── 流水线 ────────────────────────────────────────────

from unittest.mock import patch
from core.services.pipeline_service import ResearchPipeline

class TestPipelineAPI:
    def test_run_asset_analysis(self):
        from datetime import datetime, timezone
        mock_snapshot = AssetAnalysisSnapshot(
            snapshot_id="snap-001",
            canonical_id="asset-001",
            as_of=datetime.now(timezone.utc),
        )
        
        with patch.object(ResearchPipeline, 'run_asset_analysis', return_value=mock_snapshot):
            resp = client.post(
                "/api/pipeline/asset-analysis",
                json={"asset_id": "asset-001"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["canonical_id"] == "asset-001"


# ─── 图谱 ───────────────────────────────────────────────

class TestGraphAPI:
    def test_get_industry_chain(self):
        resp = client.get("/api/graph/industry-chain/semiconductor")
        assert resp.status_code == 200
        data = resp.json()
        assert data["industry"] == "semiconductor"
        assert "nodes" in data
        assert "edges" in data

    def test_get_propagation_path(self):
        resp = client.get("/api/graph/propagation/evt-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] == "evt-001"

