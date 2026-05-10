"""Dashboard 首页数据 API 路由"""
from fastapi import APIRouter, HTTPException

from app.api.models import ErrorResponse
from core.observability import get_logger
from core.contracts.dashboard import DashboardResponse
from core.services.dashboard_service import DashboardService
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    responses={500: {"model": ErrorResponse}},
)
async def get_dashboard():
    """获取首页仪表盘完整聚合数据

    包括 Today, Research Queue, Candidate Board, Learning 四个板块
    """
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            return service.get_full_dashboard()
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get dashboard data")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load dashboard: {str(e)}",
        )
