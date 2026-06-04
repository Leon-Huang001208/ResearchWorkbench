"""Adapter: DB CanonicalEvent (SQLAlchemy, payload JSON) ↔ Pydantic CanonicalEvent."""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.contracts.events import CanonicalEvent

if TYPE_CHECKING:
    from data_layer.repositories.models import CanonicalEvent as DBCanonicalEvent


def db_event_to_pydantic(db_event: DBCanonicalEvent) -> CanonicalEvent:
    """将 DB CanonicalEvent (payload JSON 列) 转为 Pydantic CanonicalEvent。

    DB 的 payload JSON 列中存储了 source_type、source_name、title 等字段，
    这些在 Pydantic 模型中是显式字段。
    """
    payload: dict = getattr(db_event, "payload", {}) or {}

    impact_direction = _coerce_impact_direction(str(db_event.impact_direction))

    return CanonicalEvent(
        event_id=db_event.event_id,
        event_type=db_event.event_type,
        event_time=db_event.event_time,
        source_type=payload.get("source_type", ""),
        source_name=payload.get("source_name", ""),
        title=payload.get("title", db_event.summary),
        raw_text=payload.get("raw_text"),
        extracted_assertions=payload.get("extracted_assertions", []),
        impacted_industries=payload.get("impacted_industries", []),
        impacted_symbols=payload.get("impacted_symbols", []),
        confidence=float(db_event.confidence),
        novelty_score=float(payload.get("novelty_score", 0.0)),
        summary=db_event.summary,
        impact_direction=impact_direction,
        needs_review=bool(db_event.needs_review),
        entities=payload.get("entities", []),
        assertions=payload.get("assertions", []),
        evidence_spans=payload.get("evidence_spans", []),
        source_doc_id=db_event.source_doc_id or "",
        reviewer_status=db_event.reviewer_status or "draft",
        reviewer=db_event.reviewer,
        reviewed_at=db_event.reviewed_at,
    )


def _coerce_impact_direction(raw: str) -> str:
    valid = {"positive", "negative", "mixed", "unknown"}
    if raw in valid:
        return raw
    return "unknown"
