"""Web 工作台 API"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/workbench", tags=["workbench"])


def get_signal_service():
    """获取 SignalService 实例"""
    from data_layer.repositories.signal_repository import SignalRepositoryImpl
    from services.signal_service import SignalService

    try:
        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        repo = SignalRepositoryImpl(db)
        return SignalService(repository=repo)
    except Exception as e:
        logger.warning(f"Failed to init SignalService with DB, falling back to in-memory: {e}")
        return SignalService()


def get_review_service():
    """获取 ReviewService 实例"""
    from services.review_service import ReviewService

    try:
        from data_layer.repositories.base import ensure_schema

        ensure_schema()
    except Exception as e:
        logger.warning(f"ensure_schema failed: {e}")
    return ReviewService()


def get_learning_journal():
    """获取 LearningJournal 实例（内存版）"""
    from memory_learning.journal import LearningJournal

    if not hasattr(get_learning_journal, "_instance"):
        get_learning_journal._instance = LearningJournal()
    return get_learning_journal._instance


@router.get("/dashboard")
async def get_dashboard(
    signal_service=Depends(get_signal_service),
    review_service=Depends(get_review_service),
    journal=Depends(get_learning_journal),
):
    """仪表盘数据（信号统计、审核队列、最近事件）"""
    try:
        # ── 信号统计 ──
        signal_stats = _gather_signal_stats(signal_service)

        # ── 审核队列 ──
        review_queue = _gather_review_queue(review_service)

        # ── 最近事件（来自 LearningJournal） ──
        recent_events = _gather_recent_events(journal)

        return {
            "signal_stats": signal_stats,
            "review_queue": review_queue,
            "recent_events": recent_events,
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _gather_signal_stats(signal_service) -> dict:
    """从 SignalService 聚合各状态信号数量"""
    try:
        all_signals = signal_service.list_signals(limit=10000)
        total = len(all_signals)
        research_only = sum(1 for s in all_signals if s.status == "research_only")
        candidate = sum(1 for s in all_signals if s.status == "candidate")
        paper_trade = sum(1 for s in all_signals if s.status == "paper_trade")
        return {
            "total": total,
            "research_only": research_only,
            "candidate": candidate,
            "paper_trade": paper_trade,
        }
    except Exception as e:
        logger.warning(f"Failed to gather signal stats: {e}")
        return {"total": 0, "research_only": 0, "candidate": 0, "paper_trade": 0}


def _gather_review_queue(review_service) -> list:
    """从 ReviewService 获取待审核断言的摘要列表"""
    try:
        pending = review_service.list_pending_assertions(limit=20)
        return [
            {
                "assertion_id": a.assertion_id,
                "subject_entity_id": a.subject_entity_id,
                "predicate": a.predicate,
                "confidence": a.confidence,
                "source_doc_id": a.source_doc_id,
            }
            for a in pending
        ]
    except Exception as e:
        logger.warning(f"Failed to gather review queue: {e}")
        return []


def _gather_recent_events(journal) -> list:
    """从 LearningJournal 获取最近的事件记录"""
    try:
        episodes = journal.list_episodes()
        # 取最近 10 条，按 episode_id 倒序（内存版没有时间戳排序）
        recent = episodes[-10:] if len(episodes) > 10 else episodes
        return [
            {
                "event_id": ep.event_id,
                "event_type": ep.event_type,
                "title": f"{ep.event_type} — {ep.market_regime}",
                "market_regime": ep.market_regime,
                "outcome_return": ep.outcome_return,
                "outcome_excess_return": ep.outcome_excess_return,
                "lesson": ep.lesson,
            }
            for ep in reversed(recent)
        ]
    except Exception as e:
        logger.warning(f"Failed to gather recent events: {e}")
        return []


@router.get("/search")
async def global_search(q: Optional[str] = None):
    """全局搜索（实体、事件、信号）"""
    try:
        # TODO: implement real logic
        return {"entities": [], "events": [], "signals": []}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
