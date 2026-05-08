"""全局搜索 API 路由"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.models import ErrorResponse
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.get(
    "",
    responses={500: {"model": ErrorResponse}},
)
async def global_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    types: Optional[str] = Query(None, description="类型过滤，逗号分隔: signal,event,outcome,review"),
):
    """全局搜索

    跨对象类型搜索：信号（按 thesis/事件类型）、事件（按 summary）、
    Outcome（按 lesson）、审核记录。

    使用 LIKE/substring 匹配，返回分组结果。
    """
    type_filter = None
    if types:
        type_filter = [t.strip() for t in types.split(",") if t.strip()]
        valid_types = {"signal", "event", "outcome", "review"}
        invalid = set(type_filter) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search types: {invalid}. Must be one of {valid_types}",
            )

    results: dict = {
        "signals": [],
        "events": [],
        "outcomes": [],
        "reviews": [],
    }

    # 搜索信号
    if type_filter is None or "signal" in type_filter:
        try:
            results["signals"] = _search_signals(q)
        except Exception as e:
            logger.warning(f"Signal search failed: {e}")

    # 搜索事件
    if type_filter is None or "event" in type_filter:
        try:
            results["events"] = _search_events(q)
        except Exception as e:
            logger.warning(f"Event search failed: {e}")

    # 搜索 Outcome
    if type_filter is None or "outcome" in type_filter:
        try:
            results["outcomes"] = _search_outcomes(q)
        except Exception as e:
            logger.warning(f"Outcome search failed: {e}")

    # 搜索审核记录
    if type_filter is None or "review" in type_filter:
        try:
            results["reviews"] = _search_reviews(q)
        except Exception as e:
            logger.warning(f"Review search failed: {e}")

    return results


def _search_signals(query: str, limit: int = 20) -> List[dict]:
    """搜索信号（按 thesis, subject_id, event_type）"""
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.models import AlphaSignalDB
        from sqlalchemy import or_

        db = SessionLocal()
        try:
            pattern = f"%{query}%"
            rows = (
                db.query(AlphaSignalDB)
                .filter(
                    or_(
                        AlphaSignalDB.thesis.ilike(pattern),
                        AlphaSignalDB.subject_id.ilike(pattern),
                        AlphaSignalDB.event_type.ilike(pattern),
                    )
                )
                .order_by(AlphaSignalDB.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "signal_id": r.signal_id,
                    "subject_id": r.subject_id,
                    "thesis": r.thesis,
                    "score": float(r.score),
                    "confidence": float(r.confidence),
                    "status": r.status,
                    "event_type": r.event_type,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Signal search DB query failed: {e}")
        return []


def _search_events(query: str, limit: int = 20) -> List[dict]:
    """搜索规范事件（按 summary, event_type）"""
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.models import CanonicalEvent
        from sqlalchemy import or_

        db = SessionLocal()
        try:
            pattern = f"%{query}%"
            rows = (
                db.query(CanonicalEvent)
                .filter(
                    or_(
                        CanonicalEvent.summary.ilike(pattern),
                        CanonicalEvent.event_type.ilike(pattern),
                    )
                )
                .order_by(CanonicalEvent.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "summary": r.summary,
                    "impact_direction": r.impact_direction,
                    "confidence": float(r.confidence),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Event search DB query failed: {e}")
        return []


def _search_outcomes(query: str, limit: int = 20) -> List[dict]:
    """搜索 Outcome（按 lesson, subject_id）"""
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.models import SignalOutcomeDB
        from sqlalchemy import or_

        db = SessionLocal()
        try:
            pattern = f"%{query}%"
            rows = (
                db.query(SignalOutcomeDB)
                .filter(
                    or_(
                        SignalOutcomeDB.lesson.ilike(pattern),
                        SignalOutcomeDB.subject_id.ilike(pattern),
                        SignalOutcomeDB.failure_reason.ilike(pattern),
                    )
                )
                .order_by(SignalOutcomeDB.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "outcome_id": r.outcome_id,
                    "signal_id": r.signal_id,
                    "subject_id": r.subject_id,
                    "outcome_return": float(r.outcome_return),
                    "outcome_excess_return": float(r.outcome_excess_return),
                    "lesson": r.lesson,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Outcome search DB query failed: {e}")
        return []


def _search_reviews(query: str, limit: int = 20) -> List[dict]:
    """搜索审核记录（按审计日志 details）"""
    try:
        from core.services.audit_service import AuditService
        from data_layer.repositories.audit_repository import AuditRepositoryImpl
        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        try:
            audit_repo = AuditRepositoryImpl(db)
            audit_service = AuditService(repository=audit_repo)
            return audit_service.search(query=query, limit=limit)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Review search failed: {e}")
        return []
