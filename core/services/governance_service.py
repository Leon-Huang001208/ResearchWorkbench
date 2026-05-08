"""Model/Prompt/Strategy Governance & Experiment Tracking 服务。

版本化管理策略组件，追踪实验，支持实验对比和回滚。
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from core.contracts.governance import (
    ExperimentCompareRequest,
    ExperimentComparison,
    ExperimentCreateRequest,
    ExperimentMetricDiff,
    ExperimentRecord,
    GovernanceMetadata,
    GovernanceReport,
    RollbackRequest,
    RollbackResult,
    StrategyComponentType,
    StrategyVersion,
    StrategyVersionCreateRequest,
    StrategyVersionSummary,
)
from core.observability import get_logger

logger = get_logger(__name__)


class GovernanceService:
    """治理与实验追踪核心服务"""

    def __init__(
        self,
        governance_repository: Optional[Any] = None,
    ):
        self._gov_repo = governance_repository

    # ── 策略版本管理 ────────────────────────────────────

    def register_strategy_version(
        self,
        request: StrategyVersionCreateRequest,
    ) -> StrategyVersion:
        """注册新的策略版本。

        自动计算版本号和内容哈希，停用同组件的旧活跃版本。
        """
        # 计算版本号
        latest_num = 0
        if self._gov_repo:
            latest_num = self._gov_repo.get_latest_version_number(
                request.component_type.value, request.component_name
            )

        version_number = latest_num + 1
        version_id = f"sv-{request.component_type.value}-{request.component_name}-v{version_number}-{uuid.uuid4().hex[:8]}"

        # 计算内容哈希
        content_hash = self._compute_hash(request.config)

        now = datetime.now(timezone.utc)

        version = StrategyVersion(
            version_id=version_id,
            component_type=request.component_type,
            component_name=request.component_name,
            version_number=version_number,
            description=request.description,
            config=request.config,
            content_hash=content_hash,
            parent_version_id=request.parent_version_id,
            is_active=True,
            created_at=now,
            created_by=request.created_by,
            tags=request.tags,
        )

        # 停用同组件的旧活跃版本
        if self._gov_repo:
            old_active = self._gov_repo.get_active_version(
                request.component_type.value, request.component_name
            )
            if old_active:
                self._gov_repo.deactivate_version(old_active.version_id)

            version = self._gov_repo.save_strategy_version(version)

        logger.info(
            "strategy version registered",
            version_id=version_id,
            component_type=request.component_type.value,
            component_name=request.component_name,
            version_number=version_number,
        )

        return version

    def get_strategy_version(self, version_id: str) -> Optional[StrategyVersion]:
        """获取策略版本"""
        if not self._gov_repo:
            return None
        return self._gov_repo.get_strategy_version(version_id)

    def list_strategy_versions(
        self,
        component_type: Optional[str] = None,
        component_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
    ) -> List[StrategyVersion]:
        """列出策略版本"""
        if not self._gov_repo:
            return []
        return self._gov_repo.list_strategy_versions(
            component_type=component_type,
            component_name=component_name,
            is_active=is_active,
            limit=limit,
        )

    def get_active_strategy_version(
        self,
        component_type: StrategyComponentType,
        component_name: str,
    ) -> Optional[StrategyVersion]:
        """获取某组件的当前活跃版本"""
        if not self._gov_repo:
            return None
        return self._gov_repo.get_active_version(component_type.value, component_name)

    # ── 实验追踪 ────────────────────────────────────────

    def create_experiment(
        self,
        request: ExperimentCreateRequest,
    ) -> ExperimentRecord:
        """创建实验记录"""
        experiment_id = f"exp-{request.experiment_type}-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        experiment = ExperimentRecord(
            experiment_id=experiment_id,
            name=request.name,
            description=request.description,
            strategy_version_ids=request.strategy_version_ids,
            experiment_type=request.experiment_type,
            entity_id=request.entity_id,
            metrics={},
            status="running",
            started_at=now,
            completed_at=None,
            tags=request.tags,
            metadata=request.metadata,
        )

        if self._gov_repo:
            experiment = self._gov_repo.save_experiment(experiment)

        logger.info(
            "experiment created",
            experiment_id=experiment_id,
            name=request.name,
            experiment_type=request.experiment_type,
        )

        return experiment

    def complete_experiment(
        self,
        experiment_id: str,
        metrics: Dict[str, float],
        status: str = "completed",
    ) -> Optional[ExperimentRecord]:
        """完成实验，记录指标"""
        if not self._gov_repo:
            return None

        experiment = self._gov_repo.get_experiment(experiment_id)
        if not experiment:
            return None

        experiment.metrics = metrics
        experiment.status = status
        experiment.completed_at = datetime.now(timezone.utc)

        experiment = self._gov_repo.save_experiment(experiment)

        logger.info(
            "experiment completed",
            experiment_id=experiment_id,
            status=status,
            metrics_count=len(metrics),
        )

        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """获取实验记录"""
        if not self._gov_repo:
            return None
        return self._gov_repo.get_experiment(experiment_id)

    def list_experiments(
        self,
        experiment_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExperimentRecord]:
        """列出实验记录"""
        if not self._gov_repo:
            return []
        return self._gov_repo.list_experiments(
            experiment_type=experiment_type,
            status=status,
            limit=limit,
        )

    # ── 实验对比 ────────────────────────────────────────

    def compare_experiments(
        self,
        request: ExperimentCompareRequest,
    ) -> ExperimentComparison:
        """对比两个实验的指标差异"""
        exp_a = self.get_experiment(request.experiment_a_id)
        exp_b = self.get_experiment(request.experiment_b_id)

        if exp_a is None or exp_b is None:
            missing = []
            if exp_a is None:
                missing.append(request.experiment_a_id)
            if exp_b is None:
                missing.append(request.experiment_b_id)
            logger.warning("experiments not found for comparison", missing=missing)
            return ExperimentComparison(
                experiment_a_id=request.experiment_a_id,
                experiment_b_id=request.experiment_b_id,
                summary=f"Missing experiments: {', '.join(missing)}",
            )

        # 计算共同指标的差异
        common_metrics: List[ExperimentMetricDiff] = []
        all_metric_names = set(exp_a.metrics.keys()) | set(exp_b.metrics.keys())

        for name in sorted(all_metric_names):
            a_val = exp_a.metrics.get(name)
            b_val = exp_b.metrics.get(name)
            diff = None
            pct_change = None

            if a_val is not None and b_val is not None:
                diff = b_val - a_val
                if abs(a_val) > 1e-9:
                    pct_change = diff / abs(a_val)

            common_metrics.append(ExperimentMetricDiff(
                metric_name=name,
                experiment_a_value=a_val,
                experiment_b_value=b_val,
                diff=diff,
                pct_change=pct_change,
            ))

        # 分析策略版本差异
        a_versions = set(exp_a.strategy_version_ids)
        b_versions = set(exp_b.strategy_version_ids)
        strategy_diffs: Dict[str, Any] = {
            "only_in_a": list(a_versions - b_versions),
            "only_in_b": list(b_versions - a_versions),
            "common": list(a_versions & b_versions),
        }

        # 生成摘要
        improved = sum(
            1 for m in common_metrics
            if m.diff is not None and m.diff > 0
        )
        degraded = sum(
            1 for m in common_metrics
            if m.diff is not None and m.diff < 0
        )
        summary = (
            f"Compared '{exp_a.name}' vs '{exp_b.name}': "
            f"{improved} metrics improved, {degraded} degraded, "
            f"{len(strategy_diffs['only_in_b'])} strategy versions changed in B."
        )

        logger.info(
            "experiments compared",
            experiment_a_id=request.experiment_a_id,
            experiment_b_id=request.experiment_b_id,
            improved=improved,
            degraded=degraded,
        )

        return ExperimentComparison(
            experiment_a_id=request.experiment_a_id,
            experiment_b_id=request.experiment_b_id,
            experiment_a_name=exp_a.name,
            experiment_b_name=exp_b.name,
            common_metrics=common_metrics,
            strategy_diffs=strategy_diffs,
            summary=summary,
        )

    # ── 回滚 ────────────────────────────────────────────

    def rollback_strategy(self, request: RollbackRequest) -> RollbackResult:
        """回滚策略组件到指定版本。

        停用当前活跃版本，激活目标版本。
        """
        if not self._gov_repo:
            return RollbackResult(
                component_type=request.component_type,
                component_name=request.component_name,
                new_active_version_id=request.target_version_id,
                success=False,
                message="No repository available",
            )

        # 验证目标版本存在
        target = self._gov_repo.get_strategy_version(request.target_version_id)
        if target is None:
            return RollbackResult(
                component_type=request.component_type,
                component_name=request.component_name,
                new_active_version_id=request.target_version_id,
                success=False,
                message=f"Target version {request.target_version_id} not found",
            )

        # 获取当前活跃版本
        previous_active = self._gov_repo.get_active_version(
            request.component_type.value, request.component_name
        )
        previous_id = previous_active.version_id if previous_active else None

        # 停用当前活跃版本
        if previous_active:
            self._gov_repo.deactivate_version(previous_active.version_id)

        # 激活目标版本
        self._gov_repo.activate_version(request.target_version_id)

        logger.info(
            "strategy rolled back",
            component_type=request.component_type.value,
            component_name=request.component_name,
            previous_active_version_id=previous_id,
            new_active_version_id=request.target_version_id,
        )

        return RollbackResult(
            component_type=request.component_type,
            component_name=request.component_name,
            previous_active_version_id=previous_id,
            new_active_version_id=request.target_version_id,
            success=True,
            message=f"Rolled back from {previous_id} to {request.target_version_id}",
        )

    # ── 治理报告 ────────────────────────────────────────

    def generate_governance_report(self) -> GovernanceReport:
        """生成治理报告"""
        summaries: List[StrategyVersionSummary] = []
        active_count = 0
        rollback_candidates: List[Dict[str, Any]] = []

        if self._gov_repo:
            # 按组件类型和名称聚合
            seen_components: Dict[str, StrategyVersionSummary] = {}

            all_versions = self._gov_repo.list_strategy_versions(limit=10000)
            for v in all_versions:
                key = f"{v.component_type.value}:{v.component_name}"
                if key not in seen_components:
                    seen_components[key] = StrategyVersionSummary(
                        component_type=v.component_type,
                        component_name=v.component_name,
                        total_versions=0,
                    )
                summary = seen_components[key]
                summary.total_versions += 1
                if v.is_active:
                    summary.active_version_id = v.version_id
                    summary.active_version_number = v.version_number
                    active_count += 1

            summaries = list(seen_components.values())

            # 回滚候选：有多个版本且当前活跃版本不是最早的组件
            for s in summaries:
                if s.total_versions > 1 and s.active_version_id:
                    rollback_candidates.append({
                        "component_type": s.component_type.value,
                        "component_name": s.component_name,
                        "active_version_id": s.active_version_id,
                        "active_version_number": s.active_version_number,
                        "available_versions": s.total_versions - 1,
                    })

        total_experiments = 0
        recent_ids: List[str] = []
        if self._gov_repo:
            total_experiments = self._gov_repo.count_experiments()
            recent_ids = self._gov_repo.recent_experiment_ids(limit=10)

        now = datetime.now(timezone.utc)
        return GovernanceReport(
            generated_at=now,
            strategy_summaries=summaries,
            total_experiments=total_experiments,
            recent_experiment_ids=recent_ids,
            active_strategy_count=active_count,
            rollback_candidates=rollback_candidates,
        )

    # ── Governance Metadata ──────────────────────────────

    def build_governance_metadata(
        self,
        experiment_id: Optional[str] = None,
        component_versions: Optional[Dict[str, str]] = None,
    ) -> GovernanceMetadata:
        """构建治理元数据，可嵌入到 signal/replay/simulation 记录中。"""
        strategy_version_id = None

        if component_versions:
            # 使用第一个组件版本作为主 strategy_version_id
            strategy_version_id = next(iter(component_versions.values()), None)
        elif self._gov_repo and experiment_id:
            # 从实验记录中获取
            exp = self._gov_repo.get_experiment(experiment_id)
            if exp and exp.strategy_version_ids:
                strategy_version_id = exp.strategy_version_ids[0]

        return GovernanceMetadata(
            strategy_version_id=strategy_version_id,
            experiment_id=experiment_id,
            component_versions=component_versions or {},
        )

    def record_entity_governance(
        self,
        entity_type: str,
        entity_id: str,
        strategy_version_ids: List[str],
        metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[ExperimentRecord]:
        """为信号/回放/模拟记录治理元数据（创建关联实验）。

        Args:
            entity_type: signal / replay / simulation
            entity_id: 关联实体ID
            strategy_version_ids: 使用的策略版本列表
            metrics: 实验指标
        """
        experiment = self.create_experiment(ExperimentCreateRequest(
            name=f"{entity_type}-{entity_id}",
            description=f"Auto-tracked experiment for {entity_type} {entity_id}",
            strategy_version_ids=strategy_version_ids,
            experiment_type=entity_type,
            entity_id=entity_id,
        ))

        if metrics:
            experiment = self.complete_experiment(
                experiment.experiment_id,
                metrics=metrics,
            )

        return experiment

    # ── 内部辅助 ────────────────────────────────────────

    @staticmethod
    def _compute_hash(config: Dict[str, Any]) -> str:
        """计算配置内容的 SHA256 哈希"""
        content = json.dumps(config, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
