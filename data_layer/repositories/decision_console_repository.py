"""决策控制台仓储实现"""
from typing import List, Optional
from datetime import datetime

from sqlalchemy import desc

from core.contracts.decision_console import (
    AnalystDecision,
    DecisionAction,
    DecisionAudit,
    DecisionWorkspace,
    PostMortemRecord,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import (
    DecisionWorkspaceDB,
    AnalystDecisionDB,
    DecisionAuditDB,
    PostMortemRecordDB,
)

logger = get_logger(__name__)


class DecisionConsoleRepository(BaseRepository):
    """决策控制台仓储实现"""

    # region Workspace
    def save_workspace(self, workspace: DecisionWorkspace) -> DecisionWorkspace:
        """保存决策工作区"""
        existing = (
            self.db.query(DecisionWorkspaceDB)
            .filter_by(workspace_id=workspace.workspace_id)
            .first()
        )
        if existing:
            existing.status = workspace.status
            existing.candidate_ids = workspace.candidate_ids
            existing.notes = workspace.notes
            existing.closed_at = workspace.closed_at
            db_workspace = existing
        else:
            db_workspace = DecisionWorkspaceDB(
                workspace_id=workspace.workspace_id,
                workspace_date=workspace.workspace_date,
                status=workspace.status,
                candidate_ids=workspace.candidate_ids,
                team_id=workspace.team_id,
                created_at=workspace.created_at,
                created_by=workspace.created_by,
                closed_at=workspace.closed_at,
                notes=workspace.notes,
            )
            self.db.add(db_workspace)
        self.db.flush()
        logger.info("decision workspace saved", workspace_id=workspace.workspace_id)
        return self._workspace_to_domain(db_workspace)

    def get_workspace(self, workspace_id: str) -> Optional[DecisionWorkspace]:
        """获取决策工作区"""
        db_workspace = (
            self.db.query(DecisionWorkspaceDB)
            .filter(DecisionWorkspaceDB.workspace_id == workspace_id)
            .first()
        )
        if not db_workspace:
            return None
        return self._workspace_to_domain(db_workspace)

    def list_open_workspaces(self, limit: int = 20) -> List[DecisionWorkspace]:
        """列出所有打开的工作区"""
        db_workspaces = (
            self.db.query(DecisionWorkspaceDB)
            .filter_by(status="open")
            .order_by(desc(DecisionWorkspaceDB.workspace_date))
            .limit(limit)
            .all()
        )
        return [self._workspace_to_domain(w) for w in db_workspaces]

    def list_workspaces_by_date(
        self, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> List[DecisionWorkspace]:
        """按日期范围列出工作区"""
        db_workspaces = (
            self.db.query(DecisionWorkspaceDB)
            .filter(
                DecisionWorkspaceDB.workspace_date >= start_date,
                DecisionWorkspaceDB.workspace_date <= end_date,
            )
            .order_by(desc(DecisionWorkspaceDB.workspace_date))
            .limit(limit)
            .all()
        )
        return [self._workspace_to_domain(w) for w in db_workspaces]
    # endregion

    # region AnalystDecision
    def save_decision(self, decision: AnalystDecision) -> AnalystDecision:
        """保存分析师决策"""
        existing = (
            self.db.query(AnalystDecisionDB)
            .filter_by(decision_id=decision.decision_id)
            .first()
        )
        if existing:
            existing.workspace_id = decision.workspace_id
            existing.candidate_id = decision.candidate_id
            existing.candidate_type = decision.candidate_type
            existing.previous_status = decision.previous_status
            existing.final_action_type = decision.final_action.action_type
            existing.action_by = decision.final_action.action_by
            existing.action_at = decision.final_action.action_at
            existing.rationale = decision.final_action.rationale
            existing.changes = decision.final_action.changes
            existing.revision_history = [a.model_dump() for a in decision.revision_history]
            existing.is_closed = decision.is_closed
            db_decision = existing
        else:
            db_decision = AnalystDecisionDB(
                decision_id=decision.decision_id,
                workspace_id=decision.workspace_id,
                candidate_id=decision.candidate_id,
                candidate_type=decision.candidate_type,
                previous_status=decision.previous_status,
                final_action_type=decision.final_action.action_type,
                action_by=decision.final_action.action_by,
                action_at=decision.final_action.action_at,
                rationale=decision.final_action.rationale,
                changes=decision.final_action.changes,
                revision_history=[a.model_dump() for a in decision.revision_history],
                is_closed=decision.is_closed,
            )
            self.db.add(db_decision)
        self.db.flush()
        logger.info("analyst decision saved", decision_id=decision.decision_id)
        return self._decision_to_domain(db_decision)

    def get_decision(self, decision_id: str) -> Optional[AnalystDecision]:
        """获取分析师决策"""
        db_decision = (
            self.db.query(AnalystDecisionDB)
            .filter(AnalystDecisionDB.decision_id == decision_id)
            .first()
        )
        if not db_decision:
            return None
        return self._decision_to_domain(db_decision)

    def get_decisions_for_workspace(self, workspace_id: str) -> List[AnalystDecision]:
        """获取工作区的所有决策"""
        db_decisions = (
            self.db.query(AnalystDecisionDB)
            .filter_by(workspace_id=workspace_id)
            .order_by(desc(AnalystDecisionDB.action_at))
            .all()
        )
        return [self._decision_to_domain(d) for d in db_decisions]

    def get_decision_by_candidate(
        self, workspace_id: str, candidate_id: str
    ) -> Optional[AnalystDecision]:
        """根据候选ID获取决策"""
        db_decision = (
            self.db.query(AnalystDecisionDB)
            .filter_by(workspace_id=workspace_id, candidate_id=candidate_id)
            .first()
        )
        if not db_decision:
            return None
        return self._decision_to_domain(db_decision)
    # endregion

    # region Audit
    def save_audit(self, audit: DecisionAudit) -> DecisionAudit:
        """保存审计记录"""
        db_audit = DecisionAuditDB(
            audit_id=audit.audit_id,
            decision_id=audit.decision_id,
            action=audit.action,
            actor=audit.actor,
            timestamp=audit.timestamp,
            before_state=audit.before_state,
            after_state=audit.after_state,
            ip_address=audit.ip_address,
            user_agent=audit.user_agent,
        )
        self.db.add(db_audit)
        self.db.flush()
        logger.debug("decision audit saved", audit_id=audit.audit_id, decision_id=audit.decision_id)
        return audit

    def get_audit_for_decision(self, decision_id: str) -> List[DecisionAudit]:
        """获取决策的所有审计记录"""
        db_audits = (
            self.db.query(DecisionAuditDB)
            .filter_by(decision_id=decision_id)
            .order_by(desc(DecisionAuditDB.timestamp))
            .all()
        )
        return [
            DecisionAudit(
                audit_id=db.audit_id,
                decision_id=db.decision_id,
                action=db.action,
                actor=db.actor,
                timestamp=db.timestamp,
                before_state=db.before_state,
                after_state=db.after_state,
                ip_address=db.ip_address,
                user_agent=db.user_agent,
            )
            for db in db_audits
        ]
    # endregion

    # region PostMortem
    def save_post_mortem(self, post_mortem: PostMortemRecord) -> PostMortemRecord:
        """保存复盘记录"""
        existing = (
            self.db.query(PostMortemRecordDB)
            .filter_by(post_mortem_id=post_mortem.post_mortem_id)
            .first()
        )
        if existing:
            existing.original_decision = post_mortem.original_decision
            existing.realized_outcome = post_mortem.realized_outcome
            existing.outcome_metrics = post_mortem.outcome_metrics
            existing.learning_points = post_mortem.learning_points
            existing.linked_signal_accuracy = post_mortem.linked_signal_accuracy
            existing.updated_at = datetime.utcnow()
            db_post_mortem = existing
        else:
            db_post_mortem = PostMortemRecordDB(
                post_mortem_id=post_mortem.post_mortem_id,
                decision_id=post_mortem.decision_id,
                original_decision=post_mortem.original_decision,
                realized_outcome=post_mortem.realized_outcome,
                outcome_metrics=post_mortem.outcome_metrics,
                learning_points=post_mortem.learning_points,
                linked_signal_accuracy=post_mortem.linked_signal_accuracy,
            )
            self.db.add(db_post_mortem)
        self.db.flush()
        logger.info("post mortem record saved", post_mortem_id=post_mortem.post_mortem_id)
        return self._post_mortem_to_domain(db_post_mortem)

    def get_post_mortem(self, post_mortem_id: str) -> Optional[PostMortemRecord]:
        """获取复盘记录"""
        db_post_mortem = (
            self.db.query(PostMortemRecordDB)
            .filter(PostMortemRecordDB.post_mortem_id == post_mortem_id)
            .first()
        )
        if not db_post_mortem:
            return None
        return self._post_mortem_to_domain(db_post_mortem)

    def get_post_mortem_for_decision(self, decision_id: str) -> Optional[PostMortemRecord]:
        """获取决策的复盘记录"""
        db_post_mortem = (
            self.db.query(PostMortemRecordDB)
            .filter_by(decision_id=decision_id)
            .first()
        )
        if not db_post_mortem:
            return None
        return self._post_mortem_to_domain(db_post_mortem)

    def list_post_mortems(self, limit: int = 100) -> List[PostMortemRecord]:
        """列出所有复盘记录"""
        db_post_mortems = (
            self.db.query(PostMortemRecordDB)
            .order_by(desc(PostMortemRecordDB.created_at))
            .limit(limit)
            .all()
        )
        return [self._post_mortem_to_domain(p) for p in db_post_mortems]
    # endregion

    # region Conversion Helpers
    def _workspace_to_domain(self, db: DecisionWorkspaceDB) -> DecisionWorkspace:
        """转换为领域模型"""
        return DecisionWorkspace(
            workspace_id=db.workspace_id,
            workspace_date=db.workspace_date,
            status=db.status,
            candidate_ids=db.candidate_ids,
            team_id=db.team_id,
            created_at=db.created_at,
            created_by=db.created_by,
            closed_at=db.closed_at,
            notes=db.notes,
        )

    def _decision_to_domain(self, db: AnalystDecisionDB) -> AnalystDecision:
        """转换为领域模型"""
        revision_history = [
            DecisionAction(**a) for a in db.revision_history
        ] if db.revision_history else []
        final_action = DecisionAction(
            action_type=db.final_action_type,
            action_by=db.action_by,
            action_at=db.action_at,
            rationale=db.rationale,
            changes=db.changes,
        )
        return AnalystDecision(
            decision_id=db.decision_id,
            workspace_id=db.workspace_id,
            candidate_id=db.candidate_id,
            candidate_type=db.candidate_type,
            previous_status=db.previous_status,
            final_action=final_action,
            revision_history=revision_history,
            is_closed=db.is_closed,
        )

    def _post_mortem_to_domain(self, db: PostMortemRecordDB) -> PostMortemRecord:
        """转换为领域模型"""
        return PostMortemRecord(
            post_mortem_id=db.post_mortem_id,
            decision_id=db.decision_id,
            original_decision=db.original_decision,
            realized_outcome=db.realized_outcome,
            outcome_metrics=db.outcome_metrics,
            learning_points=db.learning_points,
            created_at=db.created_at,
            updated_at=db.updated_at,
            linked_signal_accuracy=float(db.linked_signal_accuracy) if db.linked_signal_accuracy else None,
        )
