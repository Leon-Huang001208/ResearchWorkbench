"""Governance & Experiment Tracking 测试。

测试覆盖：
- 策略版本注册与管理
- 实验记录创建与完成
- 实验对比分析
- 策略回滚
- 治理报告生成
- 治理元数据构建
- 实体治理关联
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from core.contracts.governance import (
    ExperimentCompareRequest,
    ExperimentComparison,
    ExperimentCreateRequest,
    ExperimentMetricDiff,
    ExperimentRecord,
    GovernanceMetadata,
    RollbackRequest,
    RollbackResult,
    StrategyComponentType,
    StrategyVersion,
    StrategyVersionCreateRequest,
)
from core.services.governance_service import GovernanceService


# ─── 辅助函数 ────────────────────────────────────────────

def _make_mock_repo():
    """创建 mock 仓储"""
    repo = MagicMock()
    repo.get_latest_version_number.return_value = 0
    repo.get_active_version.return_value = None
    repo.get_strategy_version.return_value = None
    repo.get_experiment.return_value = None
    repo.list_strategy_versions.return_value = []
    repo.list_experiments.return_value = []
    repo.count_experiments.return_value = 0
    repo.recent_experiment_ids.return_value = []
    return repo


def _make_version(
    version_id: str = "sv-test-v1",
    component_type: StrategyComponentType = StrategyComponentType.PROMPT,
    component_name: str = "earnings_extractor",
    version_number: int = 1,
    is_active: bool = True,
    **kwargs,
) -> StrategyVersion:
    """创建测试用策略版本"""
    return StrategyVersion(
        version_id=version_id,
        component_type=component_type,
        component_name=component_name,
        version_number=version_number,
        description=kwargs.get("description", "Test version"),
        config=kwargs.get("config", {"model": "gpt-4", "temperature": 0.7}),
        content_hash=kwargs.get("content_hash", "abc123"),
        parent_version_id=kwargs.get("parent_version_id"),
        is_active=is_active,
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        created_by=kwargs.get("created_by", "test_user"),
        tags=kwargs.get("tags", []),
    )


def _make_experiment(
    experiment_id: str = "exp-test-001",
    name: str = "Test Experiment",
    metrics: dict = None,
    strategy_version_ids: list = None,
    **kwargs,
) -> ExperimentRecord:
    """创建测试用实验记录"""
    return ExperimentRecord(
        experiment_id=experiment_id,
        name=name,
        description=kwargs.get("description", ""),
        strategy_version_ids=strategy_version_ids or ["sv-test-v1"],
        experiment_type=kwargs.get("experiment_type", "signal"),
        entity_id=kwargs.get("entity_id"),
        metrics=metrics or {},
        status=kwargs.get("status", "running"),
        started_at=kwargs.get("started_at", datetime.now(timezone.utc)),
        completed_at=kwargs.get("completed_at"),
        tags=kwargs.get("tags", []),
        metadata=kwargs.get("metadata", {}),
    )


# ─── 策略版本注册测试 ───────────────────────────────────

class TestStrategyVersionRegistration:
    """策略版本注册测试"""

    def test_register_first_version(self):
        """注册第一个版本，版本号为1"""
        repo = _make_mock_repo()
        repo.get_latest_version_number.return_value = 0
        repo.save_strategy_version.side_effect = lambda v: v

        service = GovernanceService(governance_repository=repo)
        request = StrategyVersionCreateRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            description="Initial prompt version",
            config={"model": "gpt-4", "template": "Extract earnings..."},
            created_by="test_user",
        )

        version = service.register_strategy_version(request)

        assert version.version_number == 1
        assert version.component_type == StrategyComponentType.PROMPT
        assert version.component_name == "earnings_extractor"
        assert version.is_active is True
        assert version.content_hash  # 内容哈希已计算
        assert version.version_id.startswith("sv-prompt-earnings_extractor-v1-")

    def test_register_subsequent_version_increments(self):
        """注册后续版本，版本号递增"""
        repo = _make_mock_repo()
        repo.get_latest_version_number.return_value = 2
        repo.save_strategy_version.side_effect = lambda v: v

        service = GovernanceService(governance_repository=repo)
        request = StrategyVersionCreateRequest(
            component_type=StrategyComponentType.SCORING_LOGIC,
            component_name="alpha_scorer",
        )

        version = service.register_strategy_version(request)
        assert version.version_number == 3

    def test_register_deactivates_old_active_version(self):
        """注册新版本时自动停用旧活跃版本"""
        repo = _make_mock_repo()
        old_version = _make_version(version_id="sv-old", is_active=True)
        repo.get_active_version.return_value = old_version
        repo.save_strategy_version.side_effect = lambda v: v

        service = GovernanceService(governance_repository=repo)
        request = StrategyVersionCreateRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
        )

        version = service.register_strategy_version(request)

        repo.deactivate_version.assert_called_once_with("sv-old")
        assert version.is_active is True

    def test_register_without_repository(self):
        """无仓储时仍可注册（内存模式）"""
        service = GovernanceService(governance_repository=None)
        request = StrategyVersionCreateRequest(
            component_type=StrategyComponentType.TIMING_WEIGHT,
            component_name="momentum_weights",
        )

        version = service.register_strategy_version(request)
        # 版本号为1（无仓储默认0+1）
        assert version.version_number == 1
        assert version.is_active is True

    def test_content_hash_deterministic(self):
        """相同配置产生相同哈希"""
        service = GovernanceService()
        config = {"model": "gpt-4", "temperature": 0.7}
        hash1 = service._compute_hash(config)
        hash2 = service._compute_hash(config)
        assert hash1 == hash2

    def test_content_hash_differs_for_different_config(self):
        """不同配置产生不同哈希"""
        service = GovernanceService()
        hash1 = service._compute_hash({"model": "gpt-4"})
        hash2 = service._compute_hash({"model": "claude-3"})
        assert hash1 != hash2


# ─── 策略版本查询测试 ───────────────────────────────────

class TestStrategyVersionQuery:
    """策略版本查询测试"""

    def test_get_strategy_version(self):
        """获取策略版本"""
        repo = _make_mock_repo()
        version = _make_version()
        repo.get_strategy_version.return_value = version

        service = GovernanceService(governance_repository=repo)
        result = service.get_strategy_version("sv-test-v1")

        assert result is not None
        assert result.version_id == "sv-test-v1"

    def test_get_strategy_version_not_found(self):
        """获取不存在的版本返回 None"""
        repo = _make_mock_repo()
        repo.get_strategy_version.return_value = None

        service = GovernanceService(governance_repository=repo)
        result = service.get_strategy_version("nonexistent")
        assert result is None

    def test_list_strategy_versions_with_filters(self):
        """按条件过滤策略版本"""
        repo = _make_mock_repo()
        versions = [_make_version(component_name="a"), _make_version(component_name="b")]
        repo.list_strategy_versions.return_value = versions

        service = GovernanceService(governance_repository=repo)
        result = service.list_strategy_versions(
            component_type="prompt", is_active=True
        )

        repo.list_strategy_versions.assert_called_once_with(
            component_type="prompt",
            component_name=None,
            is_active=True,
            limit=100,
        )
        assert len(result) == 2

    def test_get_active_strategy_version(self):
        """获取活跃策略版本"""
        repo = _make_mock_repo()
        active = _make_version(is_active=True)
        repo.get_active_version.return_value = active

        service = GovernanceService(governance_repository=repo)
        result = service.get_active_strategy_version(
            StrategyComponentType.PROMPT, "earnings_extractor"
        )
        assert result is not None
        assert result.is_active is True


# ─── 实验记录测试 ───────────────────────────────────────

class TestExperimentRecord:
    """实验记录测试"""

    def test_create_experiment(self):
        """创建实验记录"""
        repo = _make_mock_repo()
        repo.save_experiment.side_effect = lambda e: e

        service = GovernanceService(governance_repository=repo)
        request = ExperimentCreateRequest(
            name="Earnings Signal Test",
            strategy_version_ids=["sv-v1"],
            experiment_type="signal",
            entity_id="sig-001",
        )

        experiment = service.create_experiment(request)

        assert experiment.experiment_id.startswith("exp-signal-")
        assert experiment.name == "Earnings Signal Test"
        assert experiment.status == "running"
        assert experiment.strategy_version_ids == ["sv-v1"]
        assert experiment.entity_id == "sig-001"

    def test_complete_experiment(self):
        """完成实验并记录指标"""
        repo = _make_mock_repo()
        experiment = _make_experiment(experiment_id="exp-001", status="running")
        repo.get_experiment.return_value = experiment
        repo.save_experiment.side_effect = lambda e: e

        service = GovernanceService(governance_repository=repo)
        result = service.complete_experiment(
            "exp-001",
            metrics={"precision": 0.85, "recall": 0.72},
        )

        assert result is not None
        assert result.status == "completed"
        assert result.metrics == {"precision": 0.85, "recall": 0.72}
        assert result.completed_at is not None

    def test_complete_experiment_not_found(self):
        """完成不存在的实验返回 None"""
        repo = _make_mock_repo()
        repo.get_experiment.return_value = None

        service = GovernanceService(governance_repository=repo)
        result = service.complete_experiment("nonexistent", metrics={})
        assert result is None

    def test_list_experiments(self):
        """列出实验记录"""
        repo = _make_mock_repo()
        experiments = [_make_experiment(), _make_experiment(experiment_id="exp-002")]
        repo.list_experiments.return_value = experiments

        service = GovernanceService(governance_repository=repo)
        result = service.list_experiments(experiment_type="signal", status="completed")

        repo.list_experiments.assert_called_once_with(
            experiment_type="signal",
            status="completed",
            limit=100,
        )
        assert len(result) == 2

    def test_create_experiment_without_repository(self):
        """无仓储时创建实验（内存模式）"""
        service = GovernanceService(governance_repository=None)
        request = ExperimentCreateRequest(name="Test")

        experiment = service.create_experiment(request)
        assert experiment.experiment_id.startswith("exp-signal-")
        assert experiment.status == "running"


# ─── 实验对比测试 ───────────────────────────────────────

class TestExperimentComparison:
    """实验对比测试"""

    def test_compare_experiments_basic(self):
        """基本实验对比"""
        repo = _make_mock_repo()
        exp_a = _make_experiment(
            experiment_id="exp-a",
            name="Baseline",
            metrics={"precision": 0.80, "recall": 0.70, "f1": 0.75},
            strategy_version_ids=["sv-v1"],
        )
        exp_b = _make_experiment(
            experiment_id="exp-b",
            name="Improved",
            metrics={"precision": 0.85, "recall": 0.75, "f1": 0.80},
            strategy_version_ids=["sv-v2"],
        )

        def get_exp_side_effect(eid):
            if eid == "exp-a":
                return exp_a
            elif eid == "exp-b":
                return exp_b
            return None

        service = GovernanceService(governance_repository=repo)
        # Patch get_experiment
        service.get_experiment = get_exp_side_effect

        comparison = service.compare_experiments(
            ExperimentCompareRequest(
                experiment_a_id="exp-a",
                experiment_b_id="exp-b",
            )
        )

        assert comparison.experiment_a_id == "exp-a"
        assert comparison.experiment_b_id == "exp-b"
        assert comparison.experiment_a_name == "Baseline"
        assert comparison.experiment_b_name == "Improved"

        # 检查指标差异
        metric_map = {m.metric_name: m for m in comparison.common_metrics}
        assert metric_map["precision"].diff == pytest.approx(0.05)
        assert metric_map["recall"].diff == pytest.approx(0.05)
        assert metric_map["f1"].diff == pytest.approx(0.05)

        # 检查策略版本差异
        assert "sv-v1" in comparison.strategy_diffs["only_in_a"]
        assert "sv-v2" in comparison.strategy_diffs["only_in_b"]

    def test_compare_experiments_pct_change(self):
        """实验对比的百分比变化计算"""
        service = GovernanceService()

        exp_a = _make_experiment(
            experiment_id="exp-a",
            name="A",
            metrics={"sharpe": 1.0},
            strategy_version_ids=["sv-v1"],
        )
        exp_b = _make_experiment(
            experiment_id="exp-b",
            name="B",
            metrics={"sharpe": 1.2},
            strategy_version_ids=["sv-v1"],
        )

        service.get_experiment = lambda eid: exp_a if eid == "exp-a" else exp_b

        comparison = service.compare_experiments(
            ExperimentCompareRequest(
                experiment_a_id="exp-a",
                experiment_b_id="exp-b",
            )
        )

        metric_map = {m.metric_name: m for m in comparison.common_metrics}
        assert metric_map["sharpe"].pct_change == pytest.approx(0.2)

    def test_compare_experiments_missing_metrics(self):
        """一个实验有而另一个缺少的指标"""
        service = GovernanceService()

        exp_a = _make_experiment(
            experiment_id="exp-a",
            name="A",
            metrics={"precision": 0.8},
            strategy_version_ids=[],
        )
        exp_b = _make_experiment(
            experiment_id="exp-b",
            name="B",
            metrics={"recall": 0.7},
            strategy_version_ids=[],
        )

        service.get_experiment = lambda eid: exp_a if eid == "exp-a" else exp_b

        comparison = service.compare_experiments(
            ExperimentCompareRequest(
                experiment_a_id="exp-a",
                experiment_b_id="exp-b",
            )
        )

        metric_map = {m.metric_name: m for m in comparison.common_metrics}
        assert metric_map["precision"].experiment_a_value == 0.8
        assert metric_map["precision"].experiment_b_value is None
        assert metric_map["recall"].experiment_a_value is None
        assert metric_map["recall"].experiment_b_value == 0.7

    def test_compare_nonexistent_experiment(self):
        """对比不存在的实验"""
        service = GovernanceService()
        service.get_experiment = lambda eid: None

        comparison = service.compare_experiments(
            ExperimentCompareRequest(
                experiment_a_id="nonexistent-a",
                experiment_b_id="nonexistent-b",
            )
        )

        assert "Missing" in comparison.summary

    def test_compare_common_strategy_versions(self):
        """对比时正确识别共同的策略版本"""
        service = GovernanceService()

        exp_a = _make_experiment(
            experiment_id="exp-a",
            name="A",
            metrics={},
            strategy_version_ids=["sv-v1", "sv-v2"],
        )
        exp_b = _make_experiment(
            experiment_id="exp-b",
            name="B",
            metrics={},
            strategy_version_ids=["sv-v2", "sv-v3"],
        )

        service.get_experiment = lambda eid: exp_a if eid == "exp-a" else exp_b

        comparison = service.compare_experiments(
            ExperimentCompareRequest(
                experiment_a_id="exp-a",
                experiment_b_id="exp-b",
            )
        )

        assert "sv-v2" in comparison.strategy_diffs["common"]
        assert "sv-v1" in comparison.strategy_diffs["only_in_a"]
        assert "sv-v3" in comparison.strategy_diffs["only_in_b"]


# ─── 回滚测试 ───────────────────────────────────────────

class TestRollback:
    """策略回滚测试"""

    def test_rollback_success(self):
        """成功回滚策略"""
        repo = _make_mock_repo()
        target_version = _make_version(
            version_id="sv-target",
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            version_number=1,
            is_active=False,
        )
        current_version = _make_version(
            version_id="sv-current",
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            version_number=3,
            is_active=True,
        )

        repo.get_strategy_version.return_value = target_version
        repo.get_active_version.return_value = current_version

        service = GovernanceService(governance_repository=repo)
        result = service.rollback_strategy(RollbackRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            target_version_id="sv-target",
        ))

        assert result.success is True
        assert result.previous_active_version_id == "sv-current"
        assert result.new_active_version_id == "sv-target"
        repo.deactivate_version.assert_called_once_with("sv-current")
        repo.activate_version.assert_called_once_with("sv-target")

    def test_rollback_target_not_found(self):
        """回滚目标版本不存在"""
        repo = _make_mock_repo()
        repo.get_strategy_version.return_value = None

        service = GovernanceService(governance_repository=repo)
        result = service.rollback_strategy(RollbackRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            target_version_id="nonexistent",
        ))

        assert result.success is False
        assert "not found" in result.message

    def test_rollback_no_current_active(self):
        """回滚时没有当前活跃版本"""
        repo = _make_mock_repo()
        target_version = _make_version(version_id="sv-target", is_active=False)
        repo.get_strategy_version.return_value = target_version
        repo.get_active_version.return_value = None

        service = GovernanceService(governance_repository=repo)
        result = service.rollback_strategy(RollbackRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            target_version_id="sv-target",
        ))

        assert result.success is True
        assert result.previous_active_version_id is None

    def test_rollback_without_repository(self):
        """无仓储时回滚失败"""
        service = GovernanceService(governance_repository=None)
        result = service.rollback_strategy(RollbackRequest(
            component_type=StrategyComponentType.PROMPT,
            component_name="earnings_extractor",
            target_version_id="sv-target",
        ))

        assert result.success is False
        assert "No repository" in result.message


# ─── 治理报告测试 ───────────────────────────────────────

class TestGovernanceReport:
    """治理报告测试"""

    def test_generate_report_basic(self):
        """基本治理报告生成"""
        repo = _make_mock_repo()
        versions = [
            _make_version(
                component_type=StrategyComponentType.PROMPT,
                component_name="earnings_extractor",
                version_number=1,
                is_active=True,
            ),
            _make_version(
                component_type=StrategyComponentType.PROMPT,
                component_name="earnings_extractor",
                version_number=2,
                is_active=False,
            ),
            _make_version(
                component_type=StrategyComponentType.SCORING_LOGIC,
                component_name="alpha_scorer",
                version_number=1,
                is_active=True,
            ),
        ]
        repo.list_strategy_versions.return_value = versions
        repo.count_experiments.return_value = 5
        repo.recent_experiment_ids.return_value = ["exp-1", "exp-2"]

        service = GovernanceService(governance_repository=repo)
        report = service.generate_governance_report()

        assert report.total_experiments == 5
        assert len(report.strategy_summaries) == 2
        assert report.active_strategy_count == 2
        assert len(report.recent_experiment_ids) == 2

        # 检查回滚候选
        # earnings_extractor 有2个版本且当前活跃，应出现在回滚候选中
        rollback_names = [r["component_name"] for r in report.rollback_candidates]
        assert "earnings_extractor" in rollback_names

    def test_generate_report_empty(self):
        """空数据治理报告"""
        repo = _make_mock_repo()

        service = GovernanceService(governance_repository=repo)
        report = service.generate_governance_report()

        assert report.total_experiments == 0
        assert len(report.strategy_summaries) == 0
        assert report.active_strategy_count == 0
        assert report.rollback_candidates == []

    def test_generate_report_without_repository(self):
        """无仓储时生成空报告"""
        service = GovernanceService(governance_repository=None)
        report = service.generate_governance_report()

        assert report.total_experiments == 0
        assert report.active_strategy_count == 0


# ─── 治理元数据测试 ─────────────────────────────────────

class TestGovernanceMetadata:
    """治理元数据测试"""

    def test_build_metadata_with_component_versions(self):
        """使用组件版本构建治理元数据"""
        service = GovernanceService()
        metadata = service.build_governance_metadata(
            experiment_id="exp-001",
            component_versions={"earnings_extractor": "sv-v1", "alpha_scorer": "sv-v2"},
        )

        assert metadata.experiment_id == "exp-001"
        assert metadata.strategy_version_id == "sv-v1"
        assert metadata.component_versions == {"earnings_extractor": "sv-v1", "alpha_scorer": "sv-v2"}

    def test_build_metadata_from_experiment(self):
        """从实验记录构建治理元数据"""
        repo = _make_mock_repo()
        experiment = _make_experiment(
            experiment_id="exp-001",
            strategy_version_ids=["sv-v1", "sv-v2"],
        )
        repo.get_experiment.return_value = experiment

        service = GovernanceService(governance_repository=repo)
        metadata = service.build_governance_metadata(experiment_id="exp-001")

        assert metadata.experiment_id == "exp-001"
        assert metadata.strategy_version_id == "sv-v1"

    def test_build_metadata_empty(self):
        """空治理元数据"""
        service = GovernanceService()
        metadata = service.build_governance_metadata()

        assert metadata.strategy_version_id is None
        assert metadata.experiment_id is None
        assert metadata.component_versions == {}


# ─── 实体治理关联测试 ───────────────────────────────────

class TestEntityGovernance:
    """实体治理关联测试"""

    def test_record_entity_governance_signal(self):
        """为信号记录治理元数据"""
        repo = _make_mock_repo()
        saved_experiments = {}

        def save_side_effect(e):
            saved_experiments[e.experiment_id] = e
            return e

        def get_side_effect(eid):
            return saved_experiments.get(eid)

        repo.save_experiment.side_effect = save_side_effect
        repo.get_experiment.side_effect = get_side_effect

        service = GovernanceService(governance_repository=repo)
        experiment = service.record_entity_governance(
            entity_type="signal",
            entity_id="sig-001",
            strategy_version_ids=["sv-v1"],
            metrics={"score": 0.85},
        )

        assert experiment is not None
        assert experiment.experiment_type == "signal"
        assert experiment.entity_id == "sig-001"
        assert experiment.strategy_version_ids == ["sv-v1"]
        # 由于有 metrics，应自动完成
        assert experiment.status == "completed"
        assert experiment.metrics == {"score": 0.85}

    def test_record_entity_governance_without_metrics(self):
        """无指标时实验保持 running 状态"""
        repo = _make_mock_repo()
        repo.save_experiment.side_effect = lambda e: e

        service = GovernanceService(governance_repository=repo)
        experiment = service.record_entity_governance(
            entity_type="replay",
            entity_id="job-001",
            strategy_version_ids=["sv-v2"],
        )

        assert experiment is not None
        assert experiment.experiment_type == "replay"
        assert experiment.status == "running"

    def test_record_entity_governance_simulation(self):
        """为模拟记录治理元数据"""
        repo = _make_mock_repo()
        saved_experiments = {}

        def save_side_effect(e):
            saved_experiments[e.experiment_id] = e
            return e

        def get_side_effect(eid):
            return saved_experiments.get(eid)

        repo.save_experiment.side_effect = save_side_effect
        repo.get_experiment.side_effect = get_side_effect

        service = GovernanceService(governance_repository=repo)
        experiment = service.record_entity_governance(
            entity_type="simulation",
            entity_id="sim-001",
            strategy_version_ids=["sv-v3"],
            metrics={"sharpe": 1.5, "max_drawdown": -0.12},
        )

        assert experiment is not None
        assert experiment.experiment_type == "simulation"
        assert experiment.metrics == {"sharpe": 1.5, "max_drawdown": -0.12}


# ─── Pydantic 契约验证测试 ───────────────────────────────

class TestGovernanceContracts:
    """Governance 契约模型验证测试"""

    def test_strategy_version_create_request(self):
        """StrategyVersionCreateRequest 验证"""
        req = StrategyVersionCreateRequest(
            component_type=StrategyComponentType.EXTRACTION_STRATEGY,
            component_name="event_extractor",
            description="Extract events from documents",
            config={"model": "gpt-4"},
            tags=["v2", "production"],
        )
        assert req.component_type == StrategyComponentType.EXTRACTION_STRATEGY
        assert req.tags == ["v2", "production"]

    def test_experiment_create_request(self):
        """ExperimentCreateRequest 验证"""
        req = ExperimentCreateRequest(
            name="Test Experiment",
            strategy_version_ids=["sv-1"],
            experiment_type="replay",
        )
        assert req.experiment_type == "replay"

    def test_governance_metadata_model(self):
        """GovernanceMetadata 模型"""
        meta = GovernanceMetadata(
            strategy_version_id="sv-v1",
            experiment_id="exp-001",
            component_versions={"prompt": "sv-v1"},
        )
        assert meta.strategy_version_id == "sv-v1"
        assert meta.experiment_id == "exp-001"

    def test_experiment_comparison_model(self):
        """ExperimentComparison 模型"""
        comp = ExperimentComparison(
            experiment_a_id="exp-a",
            experiment_b_id="exp-b",
            common_metrics=[
                ExperimentMetricDiff(
                    metric_name="precision",
                    experiment_a_value=0.8,
                    experiment_b_value=0.85,
                    diff=0.05,
                    pct_change=0.0625,
                )
            ],
            strategy_diffs={"only_in_a": [], "only_in_b": ["sv-v2"]},
            summary="B improved by 0.05",
        )
        assert comp.common_metrics[0].metric_name == "precision"
        assert comp.common_metrics[0].diff == 0.05

    def test_rollback_result_model(self):
        """RollbackResult 模型"""
        result = RollbackResult(
            component_type=StrategyComponentType.PROMPT,
            component_name="test",
            previous_active_version_id="sv-old",
            new_active_version_id="sv-new",
            success=True,
            message="Rolled back",
        )
        assert result.success is True

    def test_strategy_component_type_enum(self):
        """StrategyComponentType 枚举值"""
        assert StrategyComponentType.PROMPT.value == "prompt"
        assert StrategyComponentType.EXTRACTION_STRATEGY.value == "extraction_strategy"
        assert StrategyComponentType.MAPPING_HEURISTIC.value == "mapping_heuristic"
        assert StrategyComponentType.TIMING_WEIGHT.value == "timing_weight"
        assert StrategyComponentType.SCORING_LOGIC.value == "scoring_logic"


# ─── Contracts 导出测试 ─────────────────────────────────

class TestContractsExport:
    """测试 contracts __init__.py 导出"""

    def test_governance_imports_from_contracts(self):
        """从 core.contracts 导入 governance 类"""
        from core.contracts import (
            ExperimentRecord,
            StrategyComponentType,
        )
        # 所有类可正常导入
        assert StrategyComponentType.PROMPT is not None
        assert ExperimentRecord is not None
