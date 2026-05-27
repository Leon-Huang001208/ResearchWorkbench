"""Agent 观点仓储实现"""
from typing import List, Optional

from core.contracts.agent_types import AgentView, BlackboardConflict
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import AgentViewDB, BlackboardConflictDB

logger = get_logger(__name__)


class AgentViewRepositoryImpl(BaseRepository):
    """Agent 观点仓储实现"""

    def save(self, view: AgentView) -> AgentView:
        """保存观点"""
        existing = self.db.query(AgentViewDB).filter_by(view_id=view.view_id).first()
        if existing:
            existing.agent_name = view.agent_name
            existing.agent_role = view.agent_role
            existing.target_id = view.target_id
            existing.view = view.view
            existing.thesis = view.thesis
            existing.confidence = view.confidence
            existing.event_id = view.event_id
            existing.reasoning = view.reasoning
            existing.evidence_refs = view.evidence_refs
            existing.tool_refs = view.tool_refs
            existing.memory_refs = view.memory_refs
            existing.workflow_id = view.workflow_id
            existing.evaluation = view.evaluation
            existing.view_metadata = view.metadata
            db_view = existing
        else:
            db_view = AgentViewDB(
                view_id=view.view_id,
                agent_name=view.agent_name,
                agent_role=view.agent_role,
                target_id=view.target_id,
                view=view.view,
                thesis=view.thesis,
                confidence=view.confidence,
                event_id=view.event_id,
                reasoning=view.reasoning,
                evidence_refs=view.evidence_refs,
                tool_refs=view.tool_refs,
                memory_refs=view.memory_refs,
                workflow_id=view.workflow_id,
                evaluation=view.evaluation,
                view_metadata=view.metadata,
            )
            self.db.add(db_view)
        self.db.flush()
        logger.info(f"Saved agent view: {view.view_id}")
        return view

    def list(
        self,
        target_id: Optional[str] = None,
        event_id: Optional[str] = None,
        agent_role: Optional[str] = None,
    ) -> List[AgentView]:
        """列出观点"""
        query = self.db.query(AgentViewDB)
        if target_id:
            query = query.filter(AgentViewDB.target_id == target_id)
        if event_id:
            query = query.filter(AgentViewDB.event_id == event_id)
        if agent_role:
            query = query.filter(AgentViewDB.agent_role == agent_role)
        db_views = query.order_by(AgentViewDB.created_at.desc()).all()
        return [self._to_domain_view(v) for v in db_views]

    def save_conflict(self, conflict: BlackboardConflict) -> BlackboardConflict:
        """保存冲突"""
        existing = (
            self.db.query(BlackboardConflictDB).filter_by(conflict_id=conflict.conflict_id).first()
        )
        if existing:
            existing.target_id = conflict.target_id
            existing.event_id = conflict.event_id
            existing.view_ids = conflict.view_ids
            existing.summary = conflict.summary
            existing.severity = conflict.severity
            existing.confidence = conflict.confidence
            db_conflict = existing
        else:
            db_conflict = BlackboardConflictDB(
                conflict_id=conflict.conflict_id,
                target_id=conflict.target_id,
                event_id=conflict.event_id,
                view_ids=conflict.view_ids,
                summary=conflict.summary,
                severity=conflict.severity,
                confidence=conflict.confidence,
            )
            self.db.add(db_conflict)
        self.db.flush()
        logger.info(f"Saved blackboard conflict: {conflict.conflict_id}")
        return conflict

    def list_conflicts(
        self,
        target_id: Optional[str] = None,
    ) -> List[BlackboardConflict]:
        """列出冲突"""
        query = self.db.query(BlackboardConflictDB)
        if target_id:
            query = query.filter(BlackboardConflictDB.target_id == target_id)
        db_conflicts = query.order_by(BlackboardConflictDB.created_at.desc()).all()
        return [self._to_domain_conflict(c) for c in db_conflicts]

    def _to_domain_view(self, db_view: AgentViewDB) -> AgentView:
        """转换为领域模型"""
        return AgentView(
            view_id=db_view.view_id,
            agent_name=db_view.agent_name,
            agent_role=db_view.agent_role,
            target_id=db_view.target_id,
            view=db_view.view,
            thesis=db_view.thesis,
            confidence=float(db_view.confidence),
            event_id=db_view.event_id,
            reasoning=db_view.reasoning,
            evidence_refs=db_view.evidence_refs,
            tool_refs=db_view.tool_refs,
            memory_refs=db_view.memory_refs,
            workflow_id=db_view.workflow_id,
            evaluation=db_view.evaluation,
            metadata=db_view.view_metadata,
        )

    def _to_domain_conflict(self, db_conflict: BlackboardConflictDB) -> BlackboardConflict:
        """转换为领域模型"""
        return BlackboardConflict(
            conflict_id=db_conflict.conflict_id,
            target_id=db_conflict.target_id,
            event_id=db_conflict.event_id,
            view_ids=db_conflict.view_ids,
            summary=db_conflict.summary,
            severity=db_conflict.severity,
            confidence=float(db_conflict.confidence),
        )
