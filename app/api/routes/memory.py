"""Memory & Learning API 路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.models import ErrorResponse
from memory_learning.contracts import (
    MarketEpisode,
    StrategyMemory,
    AgentMemory,
    FailureMemory,
)
from memory_learning.journal import LearningJournal

router = APIRouter(prefix="/api/memory", tags=["memory"])


def get_learning_journal() -> LearningJournal:
    """获取 LearningJournal 实例（内存版）"""
    # 使用模块级单例，和 SignalService 模式一致
    if not hasattr(get_learning_journal, "_instance"):
        get_learning_journal._instance = LearningJournal()
    return get_learning_journal._instance


# ─── MarketEpisode 路由 ─────────────────────────────────────────────────


@router.post(
    "/episodes",
    response_model=MarketEpisode,
    responses={500: {"model": ErrorResponse}},
)
async def record_episode(
    episode: MarketEpisode,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """记录事件记忆"""
    try:
        return journal.record_episode(episode)
    except Exception as e:
        from core.observability import get_logger
        logger = get_logger(__name__)
        logger.error("Failed to record episode", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/episodes",
    response_model=list[MarketEpisode],
)
async def list_episodes(
    event_type: Optional[str] = Query(None),
    market_regime: Optional[str] = Query(None),
    journal: LearningJournal = Depends(get_learning_journal),
):
    """查询事件记忆（支持 event_type, market_regime 过滤）"""
    return journal.list_episodes(event_type=event_type, market_regime=market_regime)


@router.get(
    "/episodes/{episode_id}",
    response_model=MarketEpisode,
    responses={404: {"model": ErrorResponse}},
)
async def get_episode(
    episode_id: str,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """获取单个事件记忆"""
    episode = journal.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found")
    return episode


# ─── StrategyMemory 路由 ───────────────────────────────────────────────


@router.post(
    "/strategies",
    response_model=StrategyMemory,
    responses={500: {"model": ErrorResponse}},
)
async def record_strategy(
    strategy: StrategyMemory,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """记录策略记忆"""
    try:
        return journal.record_strategy(strategy)
    except Exception as e:
        from core.observability import get_logger
        logger = get_logger(__name__)
        logger.error("Failed to record strategy memory", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/strategies",
    response_model=list[StrategyMemory],
)
async def list_strategies(
    signal_family: Optional[str] = Query(None),
    market_regime: Optional[str] = Query(None),
    journal: LearningJournal = Depends(get_learning_journal),
):
    """查询策略记忆（支持 signal_family, market_regime 过滤）"""
    return journal.list_strategies(signal_family=signal_family, market_regime=market_regime)


# ─── AgentMemory 路由 ─────────────────────────────────────────────────


@router.post(
    "/agent-memories",
    response_model=AgentMemory,
    responses={500: {"model": ErrorResponse}},
)
async def record_agent_memory(
    memory: AgentMemory,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """记录 Agent 记忆"""
    try:
        return journal.record_agent_memory(memory)
    except Exception as e:
        from core.observability import get_logger
        logger = get_logger(__name__)
        logger.error("Failed to record agent memory", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agent-memories",
    response_model=list[AgentMemory],
)
async def list_agent_memories(
    agent_name: Optional[str] = Query(None),
    agent_role: Optional[str] = Query(None),
    journal: LearningJournal = Depends(get_learning_journal),
):
    """查询 Agent 记忆（支持 agent_name, agent_role 过滤）"""
    return journal.list_agent_memories(agent_name=agent_name, agent_role=agent_role)


# ─── FailureMemory 路由 ───────────────────────────────────────────────


@router.post(
    "/failures",
    response_model=FailureMemory,
    responses={500: {"model": ErrorResponse}},
)
async def record_failure(
    failure: FailureMemory,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """记录失败记忆"""
    try:
        return journal.record_failure(failure)
    except Exception as e:
        from core.observability import get_logger
        logger = get_logger(__name__)
        logger.error("Failed to record failure memory", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/failures",
    response_model=list[FailureMemory],
)
async def list_failures(
    failure_type: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    journal: LearningJournal = Depends(get_learning_journal),
):
    """查询失败记忆（支持 failure_type, source_id 过滤）"""
    return journal.list_failures(failure_type=failure_type, source_id=source_id)


# ─── Summarize 路由 ───────────────────────────────────────────────────


@router.get(
    "/summarize/{event_type}",
    response_model=dict[str, float | int],
)
async def summarize_event_type(
    event_type: str,
    journal: LearningJournal = Depends(get_learning_journal),
):
    """按事件类型汇总统计"""
    return journal.summarize_event_type(event_type)
