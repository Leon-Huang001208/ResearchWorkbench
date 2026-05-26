"""Dashboard 首页数据 API 路由"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.models import ErrorResponse
from core.contracts.dashboard import DashboardResponse
from core.observability import get_logger
from core.services.dashboard_service import DashboardService
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get(
    "/crawl-feed",
    responses={500: {"model": ErrorResponse}},
)
async def get_crawl_feed(
    limit: int = Query(20, ge=1, le=500, description="返回数量上限"),
    since: Optional[str] = Query(None, description="ISO 时间戳，只返回此时间之后的数据"),
    source_type: Optional[str] = Query(
        None, description="来源类型过滤: cls / cnstock / zhiqiu_reports"
    ),
):
    """获取实时抓取数据流（最近抓取的文档列表）"""
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            return service.get_crawl_feed(limit=limit, since=since, source_type=source_type)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get crawl feed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load crawl feed: {str(e)}",
        )


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
