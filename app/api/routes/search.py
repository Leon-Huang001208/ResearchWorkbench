"""全局搜索 API 路由"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.models import ErrorResponse
from core.observability import get_logger
from core.services.search_service import GlobalSearchService
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.get(
    "",
    responses={500: {"model": ErrorResponse}},
)
async def global_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    types: Optional[str] = Query(None, description="类型过滤，逗号分隔: symbol,event_type,thesis,source_doc,failure_memory,market_episode,signal,event,outcome,review"),
):
    """全局搜索

    跨所有对象类型全局搜索：
    - symbol: 标的代码/名称
    - event_type: 事件类型
    - thesis: 论题关键词
    - source_doc: 源文档
    - failure_memory: 失败记忆/经验教训
    - market_episode: 市场片段
    - signal: 信号
    - event: 事件
    - outcome: 结果
    - review: 审核记录

    使用 LIKE/substring 匹配，返回分组结果。
    """
    type_filter = None
    if types:
        type_filter = [t.strip() for t in types.split(",") if t.strip()]
        valid_types = {"symbol", "event_type", "thesis", "source_doc", "failure_memory", "market_episode", "signal", "event", "outcome", "review"}
        invalid = set(type_filter) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search types: {invalid}. Must be one of {valid_types}",
            )

    try:
        db = SessionLocal()
        try:
            service = GlobalSearchService(db)
            results = service.search(q, type_filter=type_filter)
            return results
        finally:
            db.close()
    except Exception as e:
        logger.exception("Global search failed")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}",
        )
