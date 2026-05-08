"""研究流水线 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, ScenarioSet
from core.observability import get_logger
from core.services.pipeline_service import ResearchPipeline
from data_layer.repositories.base import get_db
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl as TimingRepository
from core.services.signal_service import SignalService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class AssetAnalysisRequest(BaseModel):
    asset_id: str


class EventSignalRequest(BaseModel):
    event: CanonicalEvent


class ScenarioAnalysisRequest(BaseModel):
    question: str
    subject_ids: List[str]


# 模块级缓存：避免每次请求都重建 pipeline
_pipeline: ResearchPipeline | None = None


def get_pipeline(db: Session = Depends(get_db)) -> ResearchPipeline:
    """获取流水线实例（带信号/择时持久化能力）"""
    global _pipeline
    if _pipeline is None:
        signal_repo = SignalRepositoryImpl(db)
        signal_service = SignalService(repository=signal_repo)
        timing_repo = TimingRepository(db)
        _pipeline = ResearchPipeline(
            signal_service=signal_service,
            timing_repository=timing_repo,
        )
    else:
        # 每次请求更新 db session
        if _pipeline.signal_service and _pipeline.signal_service.repository:
            _pipeline.signal_service.repository.db = db
        if _pipeline.timing_repository:
            _pipeline.timing_repository.db = db
    return _pipeline


def _reset_pipeline():
    """重置模块级流水线（仅用于测试）"""
    global _pipeline
    _pipeline = None


@router.post("/asset-analysis", response_model=AssetAnalysisSnapshot)
async def run_asset_analysis(request: AssetAnalysisRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """触发资产分析流水线"""
    try:
        result = await pipeline.run_asset_analysis(request.asset_id)
        return result
    except Exception as e:
        logger.error(f"Asset analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event-signal", response_model=dict)
async def run_event_signal(request: EventSignalRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """触发事件信号流水线 — Golden Path"""
    try:
        signal = await pipeline.run_event_signal(request.event)
        result = signal.model_dump()
        # 确保关键字段存在，便于前端渲染
        result.setdefault("signal_id", None)
        result.setdefault("timing_decision", None)
        result.setdefault("event_id", request.event.event_id)
        return result
    except Exception as e:
        logger.error(f"Event signal pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario", response_model=ScenarioSet)
async def run_scenario_analysis(request: ScenarioAnalysisRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """触发情景分析流水线"""
    try:
        result = await pipeline.run_scenario_analysis(request.question, request.subject_ids)
        return result
    except Exception as e:
        logger.error(f"Scenario analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
