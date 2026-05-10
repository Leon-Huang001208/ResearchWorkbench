"""测试 ScenarioDataService 和 GraphDataService，以及场景/图谱 API 集成。"""
from unittest.mock import MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.main import app
from core.services.scenario_data_service import ScenarioDataService, _compute_evidence_strength
from core.services.graph_data_service import GraphDataService
from core.contracts import ScenarioSet, ScenarioHypothesis, CanonicalEvent
from core.contracts.outcomes import SignalOutcome
from memory_learning.contracts import MarketEpisode, StrategyMemory


# ─── Helpers ────────────────────────────────────────────

def _make_event(event_id="evt-1", event_type="earnings", summary="test", confidence=0.8):
    """创建测试用 CanonicalEvent"""
    return CanonicalEvent(
        event_id=event_id,
        event_type=event_type,
        summary=summary,
        impact_direction="positive",
        confidence=confidence,
        source_doc_id="doc-1",
        entities=[{"entity_id": "ent-1", "name": "TestEntity", "type": "company"}],
    )


def _make_outcome(outcome_id="out-1", event_id="evt-1", subject_id="600000.SH"):
    """创建测试用 SignalOutcome"""
    return SignalOutcome(
        outcome_id=outcome_id,
        event_id=event_id,
        signal_id="sig-1",
        subject_id=subject_id,
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.03,
        max_drawdown=-0.02,
        decay=0.1,
        lesson="Test lesson",
        metadata={"event_type": "earnings"},
    )


def _make_episode(episode_id="ep-1", event_type="earnings", excess_return=0.03):
    """创建测试用 MarketEpisode"""
    return MarketEpisode(
        episode_id=episode_id,
        event_id="evt-1",
        event_type=event_type,
        market_regime="bull",
        initial_reaction="positive",
        outcome_horizon="20d",
        outcome_return=0.05,
        outcome_excess_return=excess_return,
        timing_action="enter",
    )


# ─── ScenarioDataService 单元测试 ───────────────────────

class TestScenarioDataService:
    """ScenarioDataService 测试"""

    def test_compute_evidence_strength_high(self):
        assert _compute_evidence_strength(10) == "high"
        assert _compute_evidence_strength(5) == "high"

    def test_compute_evidence_strength_medium(self):
        assert _compute_evidence_strength(3) == "medium"
        assert _compute_evidence_strength(4) == "medium"

    def test_compute_evidence_strength_low(self):
        assert _compute_evidence_strength(1) == "low"
        assert _compute_evidence_strength(2) == "low"

    def test_compute_evidence_strength_none(self):
        assert _compute_evidence_strength(0) == "none"

    def test_get_event_evidence_with_data(self):
        """有历史数据时返回真实证据"""
        mock_repo = MagicMock()
        mock_repo.list.return_value = [_make_event(), _make_event("evt-2")]
        svc = ScenarioDataService(event_repository=mock_repo)

        result = svc.get_event_evidence(event_type="earnings")
        assert len(result) == 2
        assert result[0]["event_id"] == "evt-1"
        assert result[0]["event_type"] == "earnings"

    def test_get_event_evidence_no_repo(self):
        """无仓储时返回空列表"""
        svc = ScenarioDataService()
        result = svc.get_event_evidence()
        assert result == []

    def test_get_event_evidence_repo_error(self):
        """仓储报错时返回空列表"""
        mock_repo = MagicMock()
        mock_repo.list.side_effect = Exception("DB error")
        svc = ScenarioDataService(event_repository=mock_repo)

        result = svc.get_event_evidence()
        assert result == []

    def test_get_event_evidence_by_entity(self):
        """按 subject_id 查询事件"""
        mock_repo = MagicMock()
        mock_repo.get_by_entity.return_value = [_make_event()]
        svc = ScenarioDataService(event_repository=mock_repo)

        result = svc.get_event_evidence(subject_id="ent-1")
        mock_repo.get_by_entity.assert_called_once_with("ent-1")
        assert len(result) == 1

    def test_get_outcome_evidence_with_data(self):
        """有 Outcome 数据时返回真实证据"""
        mock_repo = MagicMock()
        mock_repo.list.return_value = [_make_outcome(), _make_outcome("out-2")]
        svc = ScenarioDataService(outcome_repository=mock_repo)

        result = svc.get_outcome_evidence(subject_id="600000.SH")
        assert len(result) == 2
        assert result[0]["outcome_id"] == "out-1"
        assert result[0]["outcome_return"] == 0.05

    def test_get_outcome_evidence_no_repo(self):
        """无 Outcome 仓储时返回空列表"""
        svc = ScenarioDataService()
        result = svc.get_outcome_evidence()
        assert result == []

    def test_get_outcome_evidence_repo_error(self):
        """Outcome 仓储报错时返回空列表"""
        mock_repo = MagicMock()
        mock_repo.list.side_effect = Exception("DB error")
        svc = ScenarioDataService(outcome_repository=mock_repo)

        result = svc.get_outcome_evidence()
        assert result == []

    def test_get_propagation_patterns_with_journal(self):
        """有 Journal 数据时返回传播模式"""
        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_episode(_make_episode())
        journal.record_episode(_make_episode("ep-2", excess_return=-0.01))
        svc = ScenarioDataService(journal=journal)

        result = svc.get_propagation_patterns(event_type="earnings")
        assert len(result) == 1
        assert result[0]["event_type"] == "earnings"
        assert result[0]["sample_size"] == 2
        assert result[0]["win_rate"] == 0.5

    def test_get_propagation_patterns_no_journal(self):
        """无 Journal 时返回空列表"""
        svc = ScenarioDataService()
        result = svc.get_propagation_patterns()
        assert result == []

    def test_get_propagation_patterns_no_matching_type(self):
        """无匹配 event_type 时返回空列表"""
        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_episode(_make_episode())
        svc = ScenarioDataService(journal=journal)

        result = svc.get_propagation_patterns(event_type="nonexistent")
        assert result == []

    def test_get_regime_summaries(self):
        """获取市场环境摘要"""
        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_strategy(StrategyMemory(
            strategy_id="strat-1",
            signal_family="earnings",
            market_regime="bull",
            sample_size=10,
            win_rate=0.6,
            average_excess_return=0.02,
            sharpe_ratio=1.5,
        ))
        svc = ScenarioDataService(journal=journal)

        result = svc.get_regime_summaries(regime="bull")
        assert len(result) == 1
        assert result[0]["market_regime"] == "bull"
        assert result[0]["win_rate"] == 0.6

    def test_get_regime_summaries_no_journal(self):
        """无 Journal 时返回空列表"""
        svc = ScenarioDataService()
        result = svc.get_regime_summaries()
        assert result == []

    def test_enrich_scenario(self):
        """enrich_scenario 整合测试"""
        mock_event_repo = MagicMock()
        mock_event_repo.list.return_value = [_make_event(), _make_event("evt-2"), _make_event("evt-3")]

        mock_outcome_repo = MagicMock()
        mock_outcome_repo.list.return_value = [_make_outcome(), _make_outcome("out-2")]

        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_episode(_make_episode())

        svc = ScenarioDataService(
            event_repository=mock_event_repo,
            outcome_repository=mock_outcome_repo,
            journal=journal,
        )

        result = svc.enrich_scenario("scenario-1", event_type="earnings")
        assert result["scenario_id"] == "scenario-1"
        assert result["evidence_strength"] == "high"  # 3 events + 2 outcomes = 5
        assert result["evidence_count"] == 5
        assert len(result["evidence"]["events"]) == 3
        assert len(result["evidence"]["outcomes"]) == 2
        assert len(result["propagation_patterns"]) >= 0

    def test_enrich_scenario_no_data(self):
        """enrich_scenario 无数据时 graceful fallback"""
        svc = ScenarioDataService()
        result = svc.enrich_scenario("scenario-1")
        assert result["scenario_id"] == "scenario-1"
        assert result["evidence_strength"] == "none"
        assert result["evidence_count"] == 0
        assert result["evidence"]["events"] == []
        assert result["evidence"]["outcomes"] == []


# ─── GraphDataService 单元测试 ──────────────────────────

class TestGraphDataService:
    """GraphDataService 测试"""

    def test_get_real_entities_from_events(self):
        """从事件中获取真实实体"""
        mock_event_repo = MagicMock()
        mock_event_repo.list.return_value = [_make_event()]
        svc = GraphDataService(event_repository=mock_event_repo)

        result = svc.get_real_entities(event_type="earnings")
        assert len(result) == 1
        assert result[0]["entity_id"] == "ent-1"
        assert result[0]["real_entity"] is True

    def test_get_real_entities_from_entity_repo(self):
        """从实体仓储获取真实实体"""
        from core.contracts.ids import CanonicalId
        mock_entity_repo = MagicMock()
        mock_entity_repo.list.return_value = [
            CanonicalId(
                canonical_id="600000.SH",
                asset_type="equity",
                market="SH",
                venue="SSE",
                symbol="600000",
                name_zh="浦发银行",
            )
        ]
        svc = GraphDataService(entity_repository=mock_entity_repo)

        result = svc.get_real_entities()
        assert len(result) == 1
        assert result[0]["entity_id"] == "600000.SH"
        assert result[0]["name"] == "浦发银行"
        assert result[0]["real_entity"] is True

    def test_get_real_entities_no_data(self):
        """无数据时返回空列表"""
        svc = GraphDataService()
        result = svc.get_real_entities()
        assert result == []

    def test_get_real_entities_repo_error(self):
        """仓储报错时返回空列表"""
        mock_event_repo = MagicMock()
        mock_event_repo.list.side_effect = Exception("DB error")
        svc = GraphDataService(event_repository=mock_event_repo)

        result = svc.get_real_entities(event_type="earnings")
        assert result == []

    def test_get_propagation_paths_with_journal(self):
        """从 Journal 获取传播路径"""
        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_episode(_make_episode())
        svc = GraphDataService(journal=journal)

        result = svc.get_propagation_paths(event_type="earnings")
        assert len(result) >= 1
        assert result[0]["event_type"] == "earnings"
        assert result[0]["evidence_count"] >= 1
        assert "realized_outcomes" in result[0]

    def test_get_propagation_paths_no_data(self):
        """无数据时返回 placeholder hint"""
        svc = GraphDataService()
        result = svc.get_propagation_paths()
        assert len(result) == 1
        assert "hint" in result[0]

    def test_get_propagation_paths_journal_error(self):
        """Journal 报错时 graceful fallback"""
        mock_journal = MagicMock()
        mock_journal.list_episodes.side_effect = Exception("error")
        svc = GraphDataService(journal=mock_journal)

        result = svc.get_propagation_paths()
        # Should fall back gracefully
        assert isinstance(result, list)

    def test_get_outcome_paths_with_data(self):
        """从 Outcome 记录获取路径"""
        mock_outcome_repo = MagicMock()
        mock_outcome_repo.list.return_value = [_make_outcome(), _make_outcome("out-2")]
        svc = GraphDataService(outcome_repository=mock_outcome_repo)

        result = svc.get_outcome_paths(subject_id="600000.SH")
        assert len(result) >= 1
        assert result[0]["subject_id"] == "600000.SH"
        assert len(result[0]["outcomes"]) >= 1

    def test_get_outcome_paths_no_repo(self):
        """无 Outcome 仓储时返回空列表"""
        svc = GraphDataService()
        result = svc.get_outcome_paths()
        assert result == []

    def test_get_outcome_paths_repo_error(self):
        """Outcome 仓储报错时返回空列表"""
        mock_outcome_repo = MagicMock()
        mock_outcome_repo.list.side_effect = Exception("DB error")
        svc = GraphDataService(outcome_repository=mock_outcome_repo)

        result = svc.get_outcome_paths()
        assert result == []

    def test_enrich_graph_real_data(self):
        """enrich_graph 有真实数据时"""
        mock_event_repo = MagicMock()
        mock_event_repo.list.return_value = [_make_event()]

        mock_outcome_repo = MagicMock()
        mock_outcome_repo.list.return_value = [_make_outcome()]

        from memory_learning.journal import LearningJournal
        journal = LearningJournal()
        journal.record_episode(_make_episode())

        svc = GraphDataService(
            event_repository=mock_event_repo,
            outcome_repository=mock_outcome_repo,
            journal=journal,
        )

        result = svc.enrich_graph("industry_chain", {"event_type": "earnings"})
        assert result["graph_type"] == "industry_chain"
        assert len(result["nodes"]) >= 1
        assert result["data_source"] == "real"

    def test_enrich_graph_placeholder(self):
        """enrich_graph 无数据时使用 placeholder"""
        svc = GraphDataService()
        result = svc.enrich_graph("industry_chain")
        assert result["graph_type"] == "industry_chain"
        assert result["data_source"] == "placeholder"
        # 节点应包含 placeholder hint
        assert any(not n.get("real_entity", True) for n in result["nodes"])


# ─── 场景 API 集成测试 ─────────────────────────────────

class TestScenariosAPIWithEvidence:
    """场景 API 集成测试"""

    def test_scenario_output_contains_evidence_fields(self):
        """场景输出包含 evidence 字段"""
        from app.api.routes.scenarios import get_scenario_service, get_scenario_data_service

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

        # mock data_service 返回空证据
        mock_data_service = MagicMock()
        mock_data_service.enrich_scenario.return_value = {
            "scenario_id": "h1",
            "evidence": {"events": [], "outcomes": []},
            "evidence_strength": "none",
            "evidence_count": 0,
            "propagation_patterns": [],
            "regime_summaries": [],
        }

        client = TestClient(app)
        app.dependency_overrides[get_scenario_service] = lambda: mock_service
        app.dependency_overrides[get_scenario_data_service] = lambda: mock_data_service
        try:
            resp = client.post(
                "/api/scenarios/generate",
                json={"topic": "黄金价格走势", "use_evidence": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "hypotheses" in data
            assert len(data["hypotheses"]) >= 1
            # 检查 evidence 字段
            h = data["hypotheses"][0]
            assert "evidence" in h
            assert "evidence_strength" in h
            assert h["evidence_strength"] == "none"
            assert "events" in h["evidence"]
            assert "outcomes" in h["evidence"]
            # 检查 propagation_patterns 和 regime_summaries
            assert "propagation_patterns" in data
            assert "regime_summaries" in data
        finally:
            app.dependency_overrides.pop(get_scenario_service, None)
            app.dependency_overrides.pop(get_scenario_data_service, None)

    def test_use_evidence_false_skips_data(self):
        """use_evidence=false 时不查询真实数据"""
        from app.api.routes.scenarios import get_scenario_service, get_scenario_data_service

        mock_service = MagicMock()
        mock_scenario_set = ScenarioSet(
            set_id="set-002",
            question="测试",
            hypotheses=[
                ScenarioHypothesis(
                    scenario_id="h1",
                    title="假设1",
                    horizon="short",
                    probability=0.5,
                    confidence=0.5,
                ),
            ],
        )
        mock_service.generate_scenario_set.return_value = mock_scenario_set

        mock_data_service = MagicMock()

        client = TestClient(app)
        app.dependency_overrides[get_scenario_service] = lambda: mock_service
        app.dependency_overrides[get_scenario_data_service] = lambda: mock_data_service
        try:
            resp = client.post(
                "/api/scenarios/generate",
                json={"topic": "测试", "use_evidence": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            # data_service.enrich_scenario 不应被调用
            mock_data_service.enrich_scenario.assert_not_called()
            # evidence 应该是默认空
            h = data["hypotheses"][0]
            assert h["evidence"]["events"] == []
            assert h["evidence"]["outcomes"] == []
            assert h["evidence_strength"] == "none"
        finally:
            app.dependency_overrides.pop(get_scenario_service, None)
            app.dependency_overrides.pop(get_scenario_data_service, None)

    def test_scenario_with_real_evidence(self):
        """场景输出包含真实证据"""
        from app.api.routes.scenarios import get_scenario_service, get_scenario_data_service

        mock_service = MagicMock()
        mock_scenario_set = ScenarioSet(
            set_id="set-003",
            question="测试",
            hypotheses=[
                ScenarioHypothesis(
                    scenario_id="h1",
                    title="假设1",
                    horizon="mid",
                    probability=0.6,
                    confidence=0.8,
                ),
            ],
        )
        mock_service.generate_scenario_set.return_value = mock_scenario_set

        mock_data_service = MagicMock()
        mock_data_service.enrich_scenario.return_value = {
            "scenario_id": "h1",
            "evidence": {
                "events": [{"event_id": "evt-1", "event_type": "earnings", "summary": "test"}],
                "outcomes": [{"outcome_id": "out-1", "outcome_return": 0.05}],
            },
            "evidence_strength": "low",
            "evidence_count": 2,
            "propagation_patterns": [{"event_type": "earnings", "sample_size": 5}],
            "regime_summaries": [{"market_regime": "bull", "win_rate": 0.6}],
        }

        client = TestClient(app)
        app.dependency_overrides[get_scenario_service] = lambda: mock_service
        app.dependency_overrides[get_scenario_data_service] = lambda: mock_data_service
        try:
            resp = client.post(
                "/api/scenarios/generate",
                json={"topic": "测试", "use_evidence": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            h = data["hypotheses"][0]
            assert len(h["evidence"]["events"]) == 1
            assert len(h["evidence"]["outcomes"]) == 1
            assert h["evidence_strength"] == "low"
            assert len(data["propagation_patterns"]) == 1
            assert len(data["regime_summaries"]) == 1
        finally:
            app.dependency_overrides.pop(get_scenario_service, None)
            app.dependency_overrides.pop(get_scenario_data_service, None)


# ─── 图谱 API 集成测试 ─────────────────────────────────

class TestGraphAPIWithEvidence:
    """图谱 API 集成测试"""

    def test_graph_nodes_contain_real_entity_marker(self):
        """图谱节点包含 real_entity 标记"""
        from app.api.routes.graph import get_graph_data_service

        mock_data_service = MagicMock()
        mock_data_service.enrich_graph.return_value = {
            "graph_type": "industry_chain",
            "nodes": [
                {"entity_id": "ent-1", "name": "TestEntity", "type": "company", "real_entity": True},
            ],
            "edges": [],
            "propagation_paths": [],
            "outcome_paths": [],
            "data_source": "real",
        }

        client = TestClient(app)
        app.dependency_overrides[get_graph_data_service] = lambda: mock_data_service
        try:
            resp = client.get("/api/graph/industry-chain/semiconductor?use_evidence=true")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["nodes"]) == 1
            assert data["nodes"][0]["real_entity"] is True
            assert data["data_source"] == "real"
        finally:
            app.dependency_overrides.pop(get_graph_data_service, None)

    def test_graph_propagation_path_contains_realized_outcomes(self):
        """传播路径包含 realized_outcomes"""
        from app.api.routes.graph import get_graph_data_service

        mock_data_service = MagicMock()
        mock_data_service.enrich_graph.return_value = {
            "graph_type": "propagation",
            "nodes": [{"entity_id": "ent-1", "real_entity": True}],
            "edges": [],
            "propagation_paths": [
                {
                    "event_type": "earnings",
                    "path": ["ent-1"],
                    "evidence_count": 3,
                    "evidence_strength": "medium",
                    "realized_outcomes": [
                        {
                            "episode_id": "ep-1",
                            "outcome_return": 0.05,
                            "outcome_excess_return": 0.03,
                            "timing_action": "enter",
                            "market_regime": "bull",
                        }
                    ],
                }
            ],
            "outcome_paths": [],
            "data_source": "real",
        }

        client = TestClient(app)
        app.dependency_overrides[get_graph_data_service] = lambda: mock_data_service
        try:
            resp = client.get("/api/graph/propagation/evt-001?use_evidence=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_source"] == "real"
            assert len(data["path"]) >= 1
            assert len(data["path"][0]["realized_outcomes"]) >= 1
            assert data["path"][0]["realized_outcomes"][0]["outcome_return"] == 0.05
        finally:
            app.dependency_overrides.pop(get_graph_data_service, None)

    def test_graph_use_evidence_false(self):
        """use_evidence=false 时不查询真实数据"""
        from app.api.routes.graph import get_graph_data_service

        mock_data_service = MagicMock()

        client = TestClient(app)
        app.dependency_overrides[get_graph_data_service] = lambda: mock_data_service
        try:
            resp = client.get("/api/graph/industry-chain/semiconductor?use_evidence=false")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_source"] == "disabled"
            mock_data_service.enrich_graph.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_graph_data_service, None)

    def test_graph_no_data_placeholder(self):
        """无数据时返回 placeholder"""
        from app.api.routes.graph import get_graph_data_service

        mock_data_service = MagicMock()
        mock_data_service.enrich_graph.return_value = {
            "graph_type": "industry_chain",
            "nodes": [{"hint": "No real entity data available; showing placeholder", "real_entity": False}],
            "edges": [],
            "propagation_paths": [],
            "outcome_paths": [],
            "data_source": "placeholder",
        }

        client = TestClient(app)
        app.dependency_overrides[get_graph_data_service] = lambda: mock_data_service
        try:
            resp = client.get("/api/graph/industry-chain/unknown?use_evidence=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_source"] == "placeholder"
        finally:
            app.dependency_overrides.pop(get_graph_data_service, None)

    def test_graph_edges_contain_evidence_count(self):
        """图谱边包含 evidence_count 和 evidence_strength"""
        from app.api.routes.graph import get_graph_data_service

        mock_data_service = MagicMock()
        mock_data_service.enrich_graph.return_value = {
            "graph_type": "industry_chain",
            "nodes": [
                {"entity_id": "ent-1", "real_entity": True},
                {"entity_id": "ent-2", "real_entity": True},
            ],
            "edges": [
                {
                    "source": "ent-1",
                    "target": "ent-2",
                    "evidence_count": 3,
                    "evidence_strength": "medium",
                    "real_edge": True,
                }
            ],
            "propagation_paths": [],
            "outcome_paths": [],
            "data_source": "real",
        }

        client = TestClient(app)
        app.dependency_overrides[get_graph_data_service] = lambda: mock_data_service
        try:
            resp = client.get("/api/graph/industry-chain/tech?use_evidence=true")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["edges"]) == 1
            assert data["edges"][0]["evidence_count"] == 3
            assert data["edges"][0]["evidence_strength"] == "medium"
            assert data["edges"][0]["real_edge"] is True
        finally:
            app.dependency_overrides.pop(get_graph_data_service, None)
