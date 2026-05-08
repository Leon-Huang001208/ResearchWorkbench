"""Dashboard wiring tests — 验证 /api/workbench/dashboard 返回真实聚合数据"""
import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.workbench import get_signal_service, get_review_service, get_learning_journal
from core.contracts import AlphaSignal, Assertion
from memory_learning.contracts import MarketEpisode


# ─── helpers ────────────────────────────────────────────

def _make_signal(signal_id="s1", status="research_only", subject_id="600000.SH"):
    return AlphaSignal(
        signal_id=signal_id,
        subject_id=subject_id,
        horizon="20d",
        thesis="test thesis",
        score=0.5,
        confidence=0.5,
        status=status,
    )


def _make_episode(episode_id="ep1", event_id="ev1", event_type="earnings"):
    return MarketEpisode(
        episode_id=episode_id,
        event_id=event_id,
        event_type=event_type,
        market_regime="bull",
        initial_reaction="positive",
        outcome_horizon="20d",
        outcome_return=0.05,
        outcome_excess_return=0.02,
        lesson="patience pays",
    )


def _make_assertion(assertion_id="a1", predicate="is_growing"):
    a = MagicMock(spec=Assertion)
    a.assertion_id = assertion_id
    a.subject_entity_id = "600000.SH"
    a.predicate = predicate
    a.confidence = 0.8
    a.source_doc_id = "doc-001"
    return a


# ─── test: signal stats ─────────────────────────────────

class TestDashboardSignalStats:
    def test_signal_stats_reflect_real_data(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = [
            _make_signal("s1", "research_only"),
            _make_signal("s2", "research_only"),
            _make_signal("s3", "candidate"),
            _make_signal("s4", "paper_trade"),
        ]
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            stats = data["signal_stats"]
            assert stats["total"] == 4
            assert stats["research_only"] == 2
            assert stats["candidate"] == 1
            assert stats["paper_trade"] == 1
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)

    def test_signal_stats_empty(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = []
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            assert data["signal_stats"]["total"] == 0
            assert data["signal_stats"]["research_only"] == 0
            assert data["signal_stats"]["candidate"] == 0
            assert data["signal_stats"]["paper_trade"] == 0
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)


# ─── test: review queue ────────────────────────────────

class TestDashboardReviewQueue:
    def test_review_queue_reflects_pending(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = []
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = [
            _make_assertion("a1", "is_growing"),
            _make_assertion("a2", "has_dividend"),
        ]
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            queue = data["review_queue"]
            assert len(queue) == 2
            assert queue[0]["assertion_id"] == "a1"
            assert queue[0]["predicate"] == "is_growing"
            assert queue[1]["assertion_id"] == "a2"
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)


# ─── test: recent events ───────────────────────────────

class TestDashboardRecentEvents:
    def test_recent_events_from_journal(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = []
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = [
            _make_episode("ep1", "ev1", "earnings"),
            _make_episode("ep2", "ev2", "policy"),
        ]

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            events = data["recent_events"]
            assert len(events) == 2
            # Most recent first (reversed)
            assert events[0]["event_type"] == "policy"
            assert events[0]["title"] == "policy — bull"
            assert events[0]["lesson"] == "patience pays"
            assert events[0]["outcome_return"] == 0.05
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)

    def test_recent_events_empty(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = []
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            assert data["recent_events"] == []
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)


# ─── test: graceful fallback ────────────────────────────

class TestDashboardGracefulFallback:
    def test_signal_service_failure_returns_zeros(self):
        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.side_effect = RuntimeError("DB down")
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []
        mock_journal = MagicMock()
        mock_journal.list_episodes.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: mock_journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            # Should fallback to zeros, not 500
            assert data["signal_stats"]["total"] == 0
            assert data["review_queue"] == []
            assert data["recent_events"] == []
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)


# ─── test: full integration with real LearningJournal ──

class TestDashboardWithRealJournal:
    def test_dashboard_with_real_journal_instance(self):
        from memory_learning.journal import LearningJournal

        journal = LearningJournal()
        journal.record_episode(_make_episode("ep1", "ev1", "earnings"))
        journal.record_episode(_make_episode("ep2", "ev2", "policy"))

        mock_signal_svc = MagicMock()
        mock_signal_svc.list_signals.return_value = [
            _make_signal("s1", "candidate"),
        ]
        mock_review_svc = MagicMock()
        mock_review_svc.list_pending_assertions.return_value = []

        app.dependency_overrides[get_signal_service] = lambda: mock_signal_svc
        app.dependency_overrides[get_review_service] = lambda: mock_review_svc
        app.dependency_overrides[get_learning_journal] = lambda: journal

        try:
            client = TestClient(app)
            resp = client.get("/api/workbench/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            assert data["signal_stats"]["candidate"] == 1
            assert len(data["recent_events"]) == 2
            assert data["recent_events"][0]["event_type"] == "policy"
        finally:
            app.dependency_overrides.pop(get_signal_service, None)
            app.dependency_overrides.pop(get_review_service, None)
            app.dependency_overrides.pop(get_learning_journal, None)
