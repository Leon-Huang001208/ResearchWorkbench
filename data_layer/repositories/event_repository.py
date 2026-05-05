from typing import List, Optional

from core.contracts import CanonicalEvent
from core.interfaces import EventRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import CanonicalEvent as CanonicalEventModel

logger = get_logger(__name__)


class EventRepositoryImpl(BaseRepository, EventRepository):
    """事件仓储实现"""

    def _to_domain(self, model: CanonicalEventModel) -> CanonicalEvent:
        """转换为领域模型"""
        return CanonicalEvent(
            event_id=model.event_id,
            event_type=model.event_type,
            summary=model.summary,
            event_time=model.event_time,
            impact_direction=model.impact_direction,
            confidence=float(model.confidence),
            needs_review=model.needs_review,
            entities=model.payload.get("entities", []),
            assertions=model.payload.get("assertions", []),
            evidence_spans=model.payload.get("evidence_spans", []),
            source_doc_id=model.source_doc_id or "",
            reviewer_status=model.reviewer_status or "draft",
            reviewer=model.reviewer,
            reviewed_at=model.reviewed_at,
        )

    def _to_model(self, domain: CanonicalEvent) -> CanonicalEventModel:
        """转换为数据库模型"""
        return CanonicalEventModel(
            event_id=domain.event_id,
            event_type=domain.event_type,
            summary=domain.summary,
            event_time=domain.event_time,
            impact_direction=domain.impact_direction,
            confidence=domain.confidence,
            needs_review=domain.needs_review,
            source_doc_id=domain.source_doc_id,
            payload={
                "entities": domain.entities,
                "assertions": domain.assertions,
                "evidence_spans": domain.evidence_spans,
            },
            reviewer_status=domain.reviewer_status,
            reviewer=domain.reviewer,
            reviewed_at=domain.reviewed_at,
        )

    def save(self, entity: CanonicalEvent) -> CanonicalEvent:
        """保存事件"""
        model = self.db.query(CanonicalEventModel).filter_by(event_id=entity.event_id).first()
        if model:
            model.event_type = entity.event_type
            model.summary = entity.summary
            model.event_time = entity.event_time
            model.impact_direction = entity.impact_direction
            model.confidence = entity.confidence
            model.needs_review = entity.needs_review
            model.source_doc_id = entity.source_doc_id
            model.payload = {
                "entities": entity.entities,
                "assertions": entity.assertions,
                "evidence_spans": entity.evidence_spans,
            }
            model.reviewer_status = entity.reviewer_status
            model.reviewer = entity.reviewer
            model.reviewed_at = entity.reviewed_at
        else:
            model = self._to_model(entity)
            self.db.add(model)
        self.db.flush()
        logger.debug("event saved", event_id=entity.event_id)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[CanonicalEvent]:
        """根据 ID 获取事件"""
        model = self.db.query(CanonicalEventModel).filter_by(event_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[CanonicalEvent]:
        """列出事件"""
        models = self.db.query(CanonicalEventModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除事件"""
        count = self.db.query(CanonicalEventModel).filter_by(event_id=id).delete()
        return count > 0

    def get_by_entity(self, entity_id: str) -> List[CanonicalEvent]:
        """获取关联到某实体的事件"""
        models = self.db.query(CanonicalEventModel).all()
        results = []
        for m in models:
            entities = m.payload.get("entities", [])
            for e in entities:
                if e.get("entity_id") == entity_id:
                    results.append(self._to_domain(m))
                    break
        return results

    def get_by_time_range(self, start: str, end: str) -> List[CanonicalEvent]:
        """获取时间范围内的事件"""
        from datetime import datetime

        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            models = (
                self.db.query(CanonicalEventModel)
                .filter(
                    CanonicalEventModel.event_time >= start_dt,
                    CanonicalEventModel.event_time <= end_dt,
                )
                .all()
            )
            return [self._to_domain(m) for m in models]
        except Exception:
            return []

    def get_pending_review(self) -> List[CanonicalEvent]:
        """获取待审核的事件"""
        models = self.db.query(CanonicalEventModel).filter_by(reviewer_status="pending").all()
        return [self._to_domain(m) for m in models]

    def list_by_status(self, status: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据审核状态列出事件"""
        models = (
            self.db.query(CanonicalEventModel)
            .filter_by(reviewer_status=status)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]
