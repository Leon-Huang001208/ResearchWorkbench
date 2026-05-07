"""研究流水线 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, ScenarioSet
from core.observability import get_logger
from core.services.pipeline_service import ResearchPipeline

logger = get_logger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class AssetAnalysisRequest(BaseModel):
    asset_id: str


class EventSignalRequest(BaseModel):
    event: CanonicalEvent


class ScenarioAnalysisRequest(BaseModel):
    question: str
    subject_ids: List[str]


pipeline = ResearchPipeline()


@router.post("/asset-analysis", response_model=AssetAnalysisSnapshot)
async def run_asset_analysis(request: AssetAnalysisRequest):
    """触发资产分析流水线"""
    try:
        result = await pipeline.run_asset_analysis(request.asset_id)
        return result
    except Exception as e:
        logger.error(f"Asset analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event-signal", response_model=dict)
async def run_event_signal(request: EventSignalRequest):
    """触发事件信号流水线"""
    try:
        signal = await pipeline.run_event_signal(request.event)
        return signal.model_dump()
    except Exception as e:
        logger.error(f"Event signal pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario", response_model=ScenarioSet)
async def run_scenario_analysis(request: ScenarioAnalysisRequest):
    """触发情景分析流水线"""
    try:
        result = await pipeline.run_scenario_analysis(request.question, request.subject_ids)
        return result
    except Exception as e:
        logger.error(f"Scenario analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
