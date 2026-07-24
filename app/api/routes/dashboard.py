"""Dashboard 首页数据 API 路由"""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.models import ErrorResponse
from core.contracts.dashboard import DashboardResponse, MarketOverviewSection
from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from services.crawl_feed_content_service import CrawlFeedContentService
from services.dashboard_service import DashboardService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get(
    "/sector-movers",
    responses={500: {"model": ErrorResponse}},
)
async def get_sector_movers(
    view_key: str = Query("wind_hot_concept", description="Wind 市场视图 key"),
    limit: int = Query(10, ge=1, le=50, description="每个方向返回数量上限"),
):
    """获取市场板块涨跌视图。"""
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            return service.get_market_sector_view(view_key=view_key, limit=limit)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get sector movers")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load sector movers: {str(e)}",
        )


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


@router.post("/crawl-feed/{doc_id}/content", responses={500: {"model": ErrorResponse}})
async def refresh_crawl_feed_content(doc_id: str):
    """按需补全实时事件流单条文档正文。"""
    try:
        db = SessionLocal()
        try:
            service = CrawlFeedContentService(db)
            return await asyncio.to_thread(service.refresh_content, doc_id)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to refresh crawl feed content")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh crawl feed content: {str(e)}",
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
    "/market-overview",
    response_model=MarketOverviewSection,
    responses={500: {"model": ErrorResponse}},
)
async def get_market_overview(
    force_refresh: bool = Query(False, description="是否绕过行情缓存强制刷新"),
):
    """获取市场总览独立快照，用于前端局部实时刷新。"""
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            return service.get_market_overview_section(force_refresh=force_refresh)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get market overview")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load market overview: {str(e)}",
        )


@router.get(
    "/sector-movers",
    responses={500: {"model": ErrorResponse}},
)
async def get_sector_movers(
    view_key: str = Query("ths_industry", description="市场口径 key"),
    view: Optional[str] = Query(None, description="兼容旧版市场口径参数"),
    limit: int = Query(10, ge=1, le=30, description="每个方向返回数量上限"),
    force_refresh: bool = Query(False, description="是否绕过缓存强制读取实时源"),
):
    """按需获取某一个市场口径的上涨/下跌列表。"""
    try:
        db = SessionLocal()
        try:
            service = DashboardService(db)
            selected_view = view or view_key
            return service.get_market_sector_view(
                view_key=selected_view,
                limit=limit,
                force_refresh=force_refresh,
            )
        finally:
            db.close()
    except Exception as e:
        logger.exception("Failed to get market sector movers")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load market sector movers: {str(e)}",
        )
