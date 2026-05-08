"""分析师循环决策控制台服务。

提供每日候选审核、决策动作记录、审计追踪和复盘查询功能。
"""
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple

from core.contracts.decision_console import (
    AnalystDecision,
    DecisionAction,
    DecisionAudit,
    DecisionWorkspace,
    PostMortemRecord,
)
from core.contracts.portfolio import PortfolioProposal
from core.observability import get_logger
from data_layer.repositories.decision_console_repository import DecisionConsoleRepository

logger = get_logger(__name__)


class DecisionConsoleService:
    """分析师循环决策控制台服务"""

    def __init__(
        self,
        repository: DecisionConsoleRepository,
    ):
        """
        初始化决策控制台服务。

        Args:
            repository: 决策控制台仓储
        """
        self.repo = repository

    # region Workspace Management
    def create_workspace(
        self,
        created_by: str,
        workspace_date: Optional[datetime] = None,
        team_id: Optional[str] = None,
        candidate_ids: Optional[List[str]] = None,
    ) -> DecisionWorkspace:
        """创建新的每日决策工作区"""
        if workspace_date is None:
            workspace_date = datetime.now(UTC).replace(tzinfo=None)

        workspace = DecisionWorkspace(
            workspace_id=str(uuid.uuid4()),
            workspace_date=workspace_date,
            created_by=created_by,
            team_id=team_id,
            candidate_ids=candidate_ids or [],
        )
        return self.repo.save_workspace(workspace)

    def get_workspace(self, workspace_id: str) -> Optional[DecisionWorkspace]:
        """获取决策工作区"""
        return self.repo.get_workspace(workspace_id)

    def list_open_workspaces(self, limit: int = 20) -> List[DecisionWorkspace]:
        """列出所有打开的工作区"""
        return self.repo.list_open_workspaces(limit=limit)

    def close_workspace(
        self,
        workspace_id: str,
        notes: Optional[str] = None,
    ) -> Optional[DecisionWorkspace]:
        """关闭决策工作区"""
        workspace = self.repo.get_workspace(workspace_id)
        if not workspace:
            logger.warning("workspace not found for closing", workspace_id=workspace_id)
            return None

        workspace.status = "closed"
        workspace.closed_at = datetime.now(UTC).replace(tzinfo=None)
        if notes:
            workspace.notes = notes

        return self.repo.save_workspace(workspace)

    def add_candidates_to_workspace(
        self,
        workspace_id: str,
        candidate_ids: List[str],
    ) -> Optional[DecisionWorkspace]:
        """添加候选到工作区"""
        workspace = self.repo.get_workspace(workspace_id)
        if not workspace:
            logger.warning("workspace not found when adding candidates", workspace_id=workspace_id)
            return None

        existing_candidates = set(workspace.candidate_ids)
        for cid in candidate_ids:
            existing_candidates.add(cid)
        workspace.candidate_ids = list(existing_candidates)

        return self.repo.save_workspace(workspace)
    # endregion

    # region Decision Actions
    def record_decision(
        self,
        workspace_id: str,
        candidate_id: str,
        candidate_type: str,
        previous_status: str,
        action: DecisionAction,
    ) -> Tuple[AnalystDecision, DecisionAudit]:
        """记录分析师对单个候选的决策"""
        # Check existing decision for this candidate in workspace
        existing = self.repo.get_decision_by_candidate(workspace_id, candidate_id)

        decision_id = str(uuid.uuid4())
        revision_history = []
        before_state = {}
        if existing:
            decision_id = existing.decision_id
            revision_history = existing.revision_history.copy()
            revision_history.append(existing.final_action)
            before_state = {
                "previous_status": existing.previous_status,
                "final_action": existing.final_action.model_dump(),
                "is_closed": existing.is_closed,
            }

        decision = AnalystDecision(
            decision_id=decision_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            candidate_type=candidate_type,
            previous_status=previous_status,
            final_action=action,
            revision_history=revision_history,
        )

        # Create audit record
        audit_id = str(uuid.uuid4())
        audit = DecisionAudit(
            audit_id=audit_id,
            decision_id=decision_id,
            action=action.action_type,
            actor=action.action_by,
            timestamp=action.action_at,
            before_state=before_state,
            after_state={
                "previous_status": previous_status,
                "final_action": action.model_dump(),
                "is_closed": decision.is_closed,
            },
        )

        saved_decision = self.repo.save_decision(decision)
        self.repo.save_audit(audit)

        logger.info(
            "decision recorded",
            decision_id=saved_decision.decision_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            action=action.action_type,
        )

        return saved_decision, audit

    def get_decision(self, decision_id: str) -> Optional[AnalystDecision]:
        """获取单个决策"""
        return self.repo.get_decision(decision_id)

    def get_workspace_decisions(self, workspace_id: str) -> List[AnalystDecision]:
        """获取工作区所有决策"""
        return self.repo.get_decisions_for_workspace(workspace_id)

    def get_decision_for_candidate(
        self, workspace_id: str, candidate_id: str
    ) -> Optional[AnalystDecision]:
        """获取候选的决策"""
        return self.repo.get_decision_by_candidate(workspace_id, candidate_id)
    # endregion

    # region Post-Mortem
    def create_post_mortem(
        self,
        decision_id: str,
        original_decision: str,
        realized_outcome: str,
        learning_points: str,
        outcome_metrics: Optional[Dict[str, float]] = None,
        linked_signal_accuracy: Optional[float] = None,
    ) -> PostMortemRecord:
        """创建新复盘记录"""
        post_mortem = PostMortemRecord(
            post_mortem_id=str(uuid.uuid4()),
            decision_id=decision_id,
            original_decision=original_decision,
            realized_outcome=realized_outcome,
            outcome_metrics=outcome_metrics or {},
            learning_points=learning_points,
            linked_signal_accuracy=linked_signal_accuracy,
        )
        saved = self.repo.save_post_mortem(post_mortem)
        logger.info(
            "post-mortem created",
            post_mortem_id=saved.post_mortem_id,
            decision_id=decision_id,
            outcome=realized_outcome,
        )
        return saved

    def update_post_mortem(
        self,
        post_mortem_id: str,
        realized_outcome: Optional[str] = None,
        learning_points: Optional[str] = None,
        outcome_metrics: Optional[Dict[str, float]] = None,
        linked_signal_accuracy: Optional[float] = None,
    ) -> Optional[PostMortemRecord]:
        """更新复盘记录"""
        existing = self.repo.get_post_mortem(post_mortem_id)
        if not existing:
            logger.warning("post-mortem not found for update", post_mortem_id=post_mortem_id)
            return None

        if realized_outcome:
            existing.realized_outcome = realized_outcome
        if learning_points:
            existing.learning_points = learning_points
        if outcome_metrics:
            existing.outcome_metrics = outcome_metrics
        if linked_signal_accuracy is not None:
            existing.linked_signal_accuracy = linked_signal_accuracy
        existing.updated_at = datetime.now(UTC).replace(tzinfo=None)

        return self.repo.save_post_mortem(existing)

    def get_post_mortem(self, post_mortem_id: str) -> Optional[PostMortemRecord]:
        """获取复盘记录"""
        return self.repo.get_post_mortem(post_mortem_id)

    def get_post_mortem_for_decision(self, decision_id: str) -> Optional[PostMortemRecord]:
        """获取决策的复盘记录"""
        return self.repo.get_post_mortem_for_decision(decision_id)

    def list_post_mortems(self, limit: int = 100) -> List[PostMortemRecord]:
        """列出所有复盘记录"""
        return self.repo.list_post_mortems(limit=limit)
    # endregion

    # region Audit
    def get_audit_history(self, decision_id: str) -> List[DecisionAudit]:
        """获取决策的审计历史"""
        return self.repo.get_audit_for_decision(decision_id)
    # endregion
