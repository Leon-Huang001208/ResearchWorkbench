"""情景分析路由"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.models import (
    ErrorResponse,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioHypothesisResponse,
)
from core.contracts import ScenarioSet
from core.services.scenario_service import ScenarioService

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _scenario_set_to_response(scenario_set: ScenarioSet) -> ScenarioResponse:
    """将核心契约转换为 API 响应模型"""
    hypotheses = []
    for h in scenario_set.hypotheses:
        hypotheses.append(
            ScenarioHypothesisResponse(
                scenario_id=h.scenario_id,
                title=h.title,
                horizon=h.horizon,
                probability=h.probability,
                assumptions=h.assumptions,
                key_triggers=h.key_triggers,
                invalidation_signals=h.invalidation_signals,
                impact_map=h.impact_map,
                evidence_assertion_ids=h.evidence_assertion_ids,
                confidence=h.confidence,
            )
        )
    return ScenarioResponse(
        set_id=scenario_set.set_id,
        question=scenario_set.question,
        hypotheses=hypotheses,
        normalization_check=scenario_set.normalization_check,
        residual_uncertainty=scenario_set.residual_uncertainty,
    )


def get_scenario_service() -> ScenarioService:
    """获取情景服务实例"""
    return ScenarioService()


@router.post(
    "/generate",
    response_model=ScenarioResponse,
    responses={500: {"model": ErrorResponse}},
)
async def generate_scenarios(
    request: ScenarioRequest,
    service: ScenarioService = Depends(get_scenario_service),
):
    """生成多情景分析"""
    try:
        scenario_set = service.generate_scenario_set(
            topic=request.topic,
            subject_ids=request.subject_ids,
        )
        return _scenario_set_to_response(scenario_set)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{set_id}",
    response_model=ScenarioResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_scenario_set(
    set_id: str,
):
    """查询情景集（当前为占位实现，后续接入持久化）"""
    raise HTTPException(
        status_code=404,
        detail=f"Scenario set {set_id} not found. Use POST /api/scenarios/generate to create one.",
    )
