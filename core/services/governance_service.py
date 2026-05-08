"""Governance 服务 — 策略版本管理、实验追踪、回滚、治理报告。"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    """策略治理与实验追踪核心服务"""

    def __init__(self, governance_repository: Optional[Any] = None):
        self._gov_repo = governance_repository

    # ── 内部工具 ────────────────────────────────────────

    @staticmethod
    def _compute_hash(config: Dict[str, Any]) -> str:
        """计算配置内容的哈希值"""
        content = json.dumps(config, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ── 策略版本管理 ────────────────────────────────────

    def register_strategy_version(
        self,
        request: StrategyVersionCreateRequest,
    ) -> StrategyVersion:
        """注册新策略版本。

        自动分配 version_id、递增 version_number、计算 content_hash。
        新版本注册后自动成为活跃版本，之前活跃版本自动降级。
        """
        # 确定版本号
        latest_number = 0
        if self._gov_repo:
            latest_number = self._gov_repo.get_latest_version_number(
                request.component_type, request.component_name
            )

        version_number = latest_number + 1

        # 生成 version_id
        short_uuid = uuid.uuid4().hex[:8]
        version_id = f"sv-{request.component_type.value}-{request.component_name}-v{version_number}-{short_uuid}"

        # 计算内容哈希
        content_hash = self._compute_hash(request.config)

        # 将之前的活跃版本降级
        if self._gov_repo:
            active = self._gov_repo.get_active_version(
                request.component_type,
                request.component_name,
            )
            if active:
                self._gov_repo.deactivate_version(active.version_id)
                logger.info(
                    "previous active version deactivated",
                    component_name=request.component_name,
                    old_version_id=active.version_id,
                )

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

        if self._gov_repo:
            version = self._gov_repo.save_strategy_version(version)
            logger.info(
                "strategy version registered",
                version_id=version_id,
                component_name=request.component_name,
                version_number=version_number,
            )

        return version

    def get_strategy_version(self, version_id: str) -> Optional[StrategyVersion]:
        """获取指定版本"""
        if self._gov_repo:
            return self._gov_repo.get_strategy_version(version_id)
        return None

    def get_active_strategy_version(
        self,
        component_type: StrategyComponentType,
        component_name: str,
    ) -> Optional[StrategyVersion]:
        """获取指定组件的当前活跃版本"""
        if self._gov_repo:
            return self._gov_repo.get_active_version(component_type, component_name)
        return None

    def list_strategy_versions(
        self,
        component_type: Optional[str] = None,
        component_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
    ) -> List[StrategyVersion]:
        """列出策略版本"""
        if self._gov_repo:
            return self._gov_repo.list_strategy_versions(
                component_type=component_type,
                component_name=component_name,
                is_active=is_active,
                limit=limit,
            )
        return []

    # ── 回滚 ────────────────────────────────────────────

    def rollback_strategy(self, request: RollbackRequest) -> RollbackResult:
        """回滚到指定版本。

        将当前活跃版本降级，激活目标版本。
        """
        if not self._gov_repo:
            return RollbackResult(
                component_type=request.component_type,
                component_name=request.component_name,
                new_active_version_id=request.target_version_id,
                success=False,
                message="No repository available",
            )

        # 获取当前活跃版本
        previous_active = self._gov_repo.get_active_version(
            request.component_type,
            request.component_name,
        )
        previous_active_id = previous_active.version_id if previous_active else None

        # 验证目标版本存在
        target_version = self._gov_repo.get_strategy_version(request.target_version_id)
        if not target_version:
            return RollbackResult(
                component_type=request.component_type,
                component_name=request.component_name,
                previous_active_version_id=previous_active_id,
                new_active_version_id=request.target_version_id,
                success=False,
                message=f"Target version {request.target_version_id} not found",
            )

        # 降级当前活跃版本
        if previous_active:
            self._gov_repo.deactivate_version(previous_active.version_id)
            logger.info(
                "active version deactivated for rollback",
                component_name=request.component_name,
                old_version_id=previous_active.version_id,
            )

        # 激活目标版本
        self._gov_repo.activate_version(request.target_version_id)
        logger.info(
            "version activated via rollback",
            component_name=request.component_name,
            new_version_id=request.target_version_id,
        )

        return RollbackResult(
            component_type=request.component_type,
            component_name=request.component_name,
            previous_active_version_id=previous_active_id,
            new_active_version_id=request.target_version_id,
            success=True,
            message=f"Rolled back to version {target_version.version_number}",
        )

    # ── 实验追踪 ────────────────────────────────────────

    def create_experiment(
        self,
        request: ExperimentCreateRequest,
    ) -> ExperimentRecord:
        """创建新实验记录"""
        short_uuid = uuid.uuid4().hex[:8]
        experiment_id = f"exp-{request.experiment_type}-{short_uuid}"
        now = datetime.now(timezone.utc)

        experiment = ExperimentRecord(
            experiment_id=experiment_id,
            name=request.name,
            description=request.description,
            strategy_version_ids=request.strategy_version_ids,
            experiment_type=request.experiment_type,
            entity_id=request.entity_id,
            status="running",
            started_at=now,
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

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """获取实验记录"""
        if self._gov_repo:
            return self._gov_repo.get_experiment(experiment_id)
        return None

    def list_experiments(
        self,
        experiment_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExperimentRecord]:
        """列出实验记录"""
        if self._gov_repo:
            return self._gov_repo.list_experiments(
                experiment_type=experiment_type,
                status=status,
                limit=limit,
            )
        return []

    def complete_experiment(
        self,
        experiment_id: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[ExperimentRecord]:
        """完成实验"""
        if not self._gov_repo:
            return None

        experiment = self._gov_repo.get_experiment(experiment_id)
        if not experiment:
            return None

        if metrics:
            experiment.metrics = {**experiment.metrics, **metrics}

        now = datetime.now(timezone.utc)
        experiment.status = "completed"
        experiment.completed_at = now

        result = self._gov_repo.save_experiment(experiment)
        logger.info(
            "experiment completed",
            experiment_id=experiment_id,
            metrics=metrics,
        )
        return result

    def fail_experiment(
        self,
        experiment_id: str,
        reason: Optional[str] = None,
    ) -> Optional[ExperimentRecord]:
        """将实验标记为失败"""
        if not self._gov_repo:
            return None

        experiment = self._gov_repo.get_experiment(experiment_id)
        if not experiment:
            return None

        now = datetime.now(timezone.utc)
        experiment.status = "failed"
        experiment.completed_at = now
        if reason:
            experiment.metadata = {**experiment.metadata, "failure_reason": reason}

        result = self._gov_repo.save_experiment(experiment)
        logger.info(
            "experiment failed",
            experiment_id=experiment_id,
            reason=reason,
        )
        return result

    # ── 实验对比 ────────────────────────────────────────

    def compare_experiments(
        self,
        request: ExperimentCompareRequest,
    ) -> ExperimentComparison:
        """对比两个实验的指标"""
        exp_a = self.get_experiment(request.experiment_a_id)
        exp_b = self.get_experiment(request.experiment_b_id)

        if not exp_a or not exp_b:
            missing = []
            if not exp_a:
                missing.append(request.experiment_a_id)
            if not exp_b:
                missing.append(request.experiment_b_id)
            return ExperimentComparison(
                experiment_a_id=request.experiment_a_id,
                experiment_b_id=request.experiment_b_id,
                experiment_a_name=exp_a.name if exp_a else "",
                experiment_b_name=exp_b.name if exp_b else "",
                summary=f"Missing experiment(s): {', '.join(missing)}",
            )

        # 计算所有指标的差异
        all_keys = set(exp_a.metrics.keys()) | set(exp_b.metrics.keys())

        metric_diffs: List[ExperimentMetricDiff] = []
        for key in sorted(all_keys):
            a_val = exp_a.metrics.get(key)
            b_val = exp_b.metrics.get(key)

            diff = None
            pct_change = None
            if a_val is not None and b_val is not None:
                diff = b_val - a_val
                if abs(a_val) > 1e-10:
                    pct_change = (b_val - a_val) / abs(a_val)

            metric_diffs.append(
                ExperimentMetricDiff(
                    metric_name=key,
                    experiment_a_value=a_val,
                    experiment_b_value=b_val,
                    diff=diff,
                    pct_change=pct_change,
                )
            )

        # 策略版本差异
        strategy_diffs: Dict[str, Any] = {}
        a_versions = set(exp_a.strategy_version_ids)
        b_versions = set(exp_b.strategy_version_ids)
        if a_versions != b_versions:
            strategy_diffs["only_in_a"] = list(a_versions - b_versions)
            strategy_diffs["only_in_b"] = list(b_versions - a_versions)
            strategy_diffs["common"] = list(a_versions & b_versions)

        summary = (
            f"Experiment A ({exp_a.name}) vs Experiment B ({exp_b.name}): "
            f"{len(set(exp_a.metrics.keys()) & set(exp_b.metrics.keys()))} common metrics, "
            f"{len(set(exp_a.metrics.keys()) ^ set(exp_b.metrics.keys()))} unique metrics"
        )

        return ExperimentComparison(
            experiment_a_id=exp_a.experiment_id,
            experiment_b_id=exp_b.experiment_id,
            experiment_a_name=exp_a.name,
            experiment_b_name=exp_b.name,
            common_metrics=metric_diffs,
            strategy_diffs=strategy_diffs,
            summary=summary,
        )

    # ── 治理报告 ────────────────────────────────────────

    def generate_governance_report(self) -> GovernanceReport:
        """生成治理报告 — 所有策略组件的版本状态和实验摘要"""
        now = datetime.now(timezone.utc)

        summaries: List[StrategyVersionSummary] = []
        rollback_candidates: List[Dict[str, Any]] = []
        active_count = 0

        if self._gov_repo:
            # 收集所有组件
            all_versions = self._gov_repo.list_strategy_versions(limit=10000)
            component_map: Dict[str, List[StrategyVersion]] = {}
            for v in all_versions:
                key = f"{v.component_type.value}:{v.component_name}"
                component_map.setdefault(key, []).append(v)

            for key, versions in component_map.items():
                ctype, cname = key.split(":", 1)
                active_v = next((v for v in versions if v.is_active), None)

                summary = StrategyVersionSummary(
                    component_type=StrategyComponentType(ctype),
                    component_name=cname,
                    active_version_id=active_v.version_id if active_v else None,
                    active_version_number=active_v.version_number if active_v else None,
                    total_versions=len(versions),
                )
                summaries.append(summary)

                if active_v:
                    active_count += 1

                # 非活跃版本可作为回滚候选
                inactive = [v for v in versions if not v.is_active]
                for v in inactive:
                    rollback_candidates.append({
                        "component_type": ctype,
                        "component_name": cname,
                        "version_id": v.version_id,
                        "version_number": v.version_number,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                    })

        # 实验摘要
        total_experiments = 0
        recent_experiment_ids: List[str] = []
        if self._gov_repo:
            total_experiments = self._gov_repo.count_experiments()
            recent_experiment_ids = self._gov_repo.recent_experiment_ids()

        return GovernanceReport(
            generated_at=now,
            strategy_summaries=summaries,
            total_experiments=total_experiments,
            recent_experiment_ids=recent_experiment_ids,
            active_strategy_count=active_count,
            rollback_candidates=rollback_candidates,
        )

    # ── 治理元数据 ──────────────────────────────────────

    def build_governance_metadata(
        self,
        experiment_id: Optional[str] = None,
        strategy_version_id: Optional[str] = None,
        component_versions: Optional[Dict[str, str]] = None,
    ) -> GovernanceMetadata:
        """构建治理元数据。

        可从实验记录构建，或直接指定组件版本。
        """
        if experiment_id and self._gov_repo:
            experiment = self._gov_repo.get_experiment(experiment_id)
            if experiment:
                return GovernanceMetadata(
                    strategy_version_id=experiment.strategy_version_ids[0] if experiment.strategy_version_ids else None,
                    experiment_id=experiment_id,
                    component_versions=component_versions or {},
                )

        # If no experiment found via repo, or no repo, use provided values
        strategy_id = strategy_version_id
        if strategy_id is None and component_versions:
            # Use the first component version as the strategy_version_id
            first_value = next(iter(component_versions.values()), None)
            strategy_id = first_value

        return GovernanceMetadata(
            strategy_version_id=strategy_id,
            experiment_id=experiment_id,
            component_versions=component_versions or {},
        )

    # ── 实体治理关联 ────────────────────────────────────

    def record_entity_governance(
        self,
        entity_type: str,
        entity_id: str,
        strategy_version_ids: Optional[List[str]] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> ExperimentRecord:
        """为实体（signal/replay/simulation）记录治理元数据。

        如果提供了 metrics，实验会自动标记为 completed。
        """
        short_uuid = uuid.uuid4().hex[:8]
        experiment_id = f"exp-{entity_type}-{short_uuid}"
        now = datetime.now(timezone.utc)

        status = "running"
        completed_at = None
        final_metrics: Dict[str, float] = {}

        if metrics:
            status = "completed"
            completed_at = now
            final_metrics = metrics

        experiment = ExperimentRecord(
            experiment_id=experiment_id,
            name=f"{entity_type} governance: {entity_id}",
            experiment_type=entity_type,
            entity_id=entity_id,
            strategy_version_ids=strategy_version_ids or [],
            metrics=final_metrics,
            status=status,
            started_at=now,
            completed_at=completed_at,
        )

        if self._gov_repo:
            experiment = self._gov_repo.save_experiment(experiment)
            logger.info(
                "entity governance recorded",
                entity_type=entity_type,
                entity_id=entity_id,
                experiment_id=experiment_id,
            )

        return experiment
