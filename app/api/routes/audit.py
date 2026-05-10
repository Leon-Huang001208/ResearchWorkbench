"""审计轨迹 API 路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.models import ErrorResponse
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


def get_audit_service():
    """获取 AuditService 实例"""
    from core.services.audit_service import AuditService

    try:
        from data_layer.repositories.audit_repository import AuditRepositoryImpl
        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        repo = AuditRepositoryImpl(db)
        return AuditService(repository=repo)
    except Exception as e:
        logger.warning(f"Failed to init AuditService with DB, falling back to in-memory: {e}")
        return AuditService()


@router.get(
    "/trail/{entity_type}/{entity_id}",
    responses={500: {"model": ErrorResponse}},
)
async def get_audit_trail(
    entity_type: str,
    entity_id: str,
    limit: int = Query(100, ge=1, le=1000),
    service=Depends(get_audit_service),
):
    """获取实体的操作审计轨迹

    entity_type: signal, event, outcome, review
    """
    valid_types = {"signal", "event", "outcome", "review"}
    if entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type: {entity_type}. Must be one of {valid_types}",
        )
    try:
        trail = service.get_trail(entity_type, entity_id, limit=limit)
        return {"entity_type": entity_type, "entity_id": entity_id, "trail": trail}
    except Exception as e:
        logger.error(f"Failed to get audit trail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/record",
    responses={500: {"model": ErrorResponse}},
)
async def record_audit_log(
    entity_type: str = Query(..., description="Entity type: signal, event, outcome, review"),
    entity_id: str = Query(..., description="Entity ID"),
    action: str = Query(
        ..., description="Action: created, status_changed, approved, rejected, etc."
    ),
    actor: str = Query("system", description="Actor who performed the action"),
    details: Optional[str] = Query(None, description="JSON string of extra details"),
    service=Depends(get_audit_service),
):
    """手动记录审计日志"""
    import json

    valid_types = {"signal", "event", "outcome", "review"}
    if entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type: {entity_type}. Must be one of {valid_types}",
        )
    try:
        parsed_details = {}
        if details:
            try:
                parsed_details = json.loads(details)
            except json.JSONDecodeError:
                parsed_details = {"raw": details}
        log = service.record(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=parsed_details,
        )
        return log
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
