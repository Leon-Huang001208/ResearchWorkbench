"""Web 工作台 API"""
from fastapi import APIRouter, HTTPException
from typing import Optional

from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/workbench", tags=["workbench"])


@router.get("/dashboard")
async def get_dashboard():
    """仪表盘数据（信号统计、审核队列、最近事件）"""
    try:
        # TODO: implement real logic
        return {
            "signal_stats": {"total": 0, "research_only": 0, "candidate": 0, "paper_trade": 0},
            "review_queue": [],
            "recent_events": [],
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def global_search(q: Optional[str] = None):
    """全局搜索（实体、事件、信号）"""
    try:
        # TODO: implement real logic
        return {"entities": [], "events": [], "signals": []}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
