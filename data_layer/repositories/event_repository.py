from typing import List, Optional, cast

from sqlalchemy import Text
from sqlalchemy import cast as sql_cast
from sqlalchemy import false, func

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
        payload = model.payload or {}
        return CanonicalEvent(
            event_id=model.event_id,
            event_type=model.event_type,
            event_time=model.event_time,
            source_type=payload.get("source_type", "unknown"),
            source_name=payload.get("source_name", "unknown"),
            title=payload.get("title", model.summary or ""),
            raw_text=payload.get("raw_text"),
            extracted_assertions=payload.get("extracted_assertions", []),
            impacted_industries=payload.get("impacted_industries", []),
            impacted_symbols=payload.get("impacted_symbols", []),
            confidence=float(model.confidence),
            novelty_score=payload.get("novelty_score", 0.0),
            # Legacy fields
            summary=model.summary,
            impact_direction=model.impact_direction or "unknown",
            needs_review=model.needs_review,
            entities=payload.get("entities", []),
            assertions=payload.get("assertions", []),
            evidence_spans=payload.get("evidence_spans", []),
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
            summary=domain.title if domain.summary is None else domain.summary,
            event_time=domain.event_time,
            impact_direction=domain.impact_direction,
            confidence=domain.confidence,
            needs_review=domain.needs_review,
            source_doc_id=domain.source_doc_id,
            payload={
                "source_type": domain.source_type,
                "source_name": domain.source_name,
                "title": domain.title,
                "raw_text": domain.raw_text,
                "extracted_assertions": domain.extracted_assertions,
                "impacted_industries": domain.impacted_industries,
                "impacted_symbols": domain.impacted_symbols,
                "novelty_score": domain.novelty_score,
                # Legacy fields
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
        if not entity.source_doc_id:
            logger.warning(
                "Skipping event with empty source_doc_id — would violate FK constraint",
                event_id=entity.event_id,
                event_type=entity.event_type,
                source_type=entity.source_type,
            )
            raise ValueError(
                f"Event {entity.event_id} has empty source_doc_id, "
                f"cannot save due to FK constraint on source_document"
            )

        model = self.db.query(CanonicalEventModel).filter_by(event_id=entity.event_id).first()
        if model:
            model.event_type = entity.event_type
            model.summary = entity.title if entity.summary is None else entity.summary
            model.event_time = entity.event_time
            model.impact_direction = entity.impact_direction
            model.confidence = entity.confidence
            model.needs_review = entity.needs_review
            model.source_doc_id = entity.source_doc_id
            model.payload = {
                "source_type": entity.source_type,
                "source_name": entity.source_name,
                "title": entity.title,
                "raw_text": entity.raw_text,
                "extracted_assertions": entity.extracted_assertions,
                "impacted_industries": entity.impacted_industries,
                "impacted_symbols": entity.impacted_symbols,
                "novelty_score": entity.novelty_score,
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
        return int(count) > 0

    def get_by_entity(self, entity_id: str) -> List[CanonicalEvent]:
        """获取关联到某实体的事件"""
        payload_text = sql_cast(CanonicalEventModel.payload, Text)
        models = self.db.query(CanonicalEventModel).filter(payload_text.contains(entity_id)).all()
        results = []
        for m in models:
            payload = m.payload or {}
            entities = payload.get("entities", [])
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
        except ValueError:
            logger.warning("Invalid event time range", start=start, end=end)
            return []

        models = (
            self.db.query(CanonicalEventModel)
            .filter(
                CanonicalEventModel.event_time >= start_dt,
                CanonicalEventModel.event_time <= end_dt,
            )
            .all()
        )
        return [self._to_domain(m) for m in models]

    def get_pending_review(self) -> List[CanonicalEvent]:
        """获取待审核的事件"""
        models = self.db.query(CanonicalEventModel).filter_by(reviewer_status="pending").all()
        return [self._to_domain(m) for m in models]

    def list_by_status(self, status: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据审核状态列出事件"""
        models = (
            self.db.query(CanonicalEventModel).filter_by(reviewer_status=status).limit(limit).all()
        )
        return [self._to_domain(m) for m in models]

    def list_by_event_type(self, event_type: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据事件类型列出事件"""
        models = (
            self.db.query(CanonicalEventModel).filter_by(event_type=event_type).limit(limit).all()
        )
        return [self._to_domain(m) for m in models]

    def list_by_impacted_symbol(self, symbol: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据影响股票列出事件"""
        payload_text = sql_cast(CanonicalEventModel.payload, Text)
        models = self.db.query(CanonicalEventModel).filter(payload_text.contains(symbol)).all()
        results = []
        for m in models:
            payload = m.payload or {}
            impacted_symbols = payload.get("impacted_symbols", [])
            if symbol in impacted_symbols:
                results.append(self._to_domain(m))
                if len(results) >= limit:
                    break
        return results

    def list_approved_pending_signal(self, limit: int = 100) -> List[CanonicalEvent]:
        """列出已批准且尚未自动生成信号的事件。"""
        signal_generated = CanonicalEventModel.payload["signal_generated"].as_boolean()
        models = (
            self.db.query(CanonicalEventModel)
            .filter(
                CanonicalEventModel.reviewer_status == "approved",
                func.coalesce(signal_generated, false()).is_(false()),
            )
            .order_by(CanonicalEventModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(model) for model in models]

    def mark_signal_generated(self, event_id: str) -> None:
        """标记事件已完成自动信号生成。"""
        model = self.db.query(CanonicalEventModel).filter_by(event_id=event_id).first()
        if model is None:
            logger.warning("Cannot mark missing event as signal generated", event_id=event_id)
            return

        payload = cast(dict, model.payload or {})
        model.payload = {**payload, "signal_generated": True}
        self.db.flush()
        logger.info("event signal generation marked", event_id=event_id)
