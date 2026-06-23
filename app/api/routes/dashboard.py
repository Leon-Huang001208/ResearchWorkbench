"""Dashboard 首页数据 API 路由"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.models import ErrorResponse
from core.contracts.dashboard import DashboardResponse
from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from services.dashboard_service import DashboardService

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
        None,
        description="来源类型过滤: cls / cninfo / cnstock / cnstock_flash / zhiqiu_reports",
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


@router.get(
    "/sector-movers",
    responses={500: {"model": ErrorResponse}},
)
async def get_sector_movers(
    view_key: str = Query("ths_industry", description="市场口径 key"),
    view: Optional[str] = Query(None, description="兼容旧版市场口径参数"),
    limit: int = Query(10, ge=1, le=30, description="每个方向返回数量上限"),
):
    """按需获取某一个市场口径的上涨/下跌列表。"""
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            return service.get_market_sector_view(view_key=view or view_key, limit=limit)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get market sector movers")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load market sector movers: {str(e)}",
        )
