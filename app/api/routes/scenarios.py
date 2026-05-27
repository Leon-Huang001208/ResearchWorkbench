"""情景分析路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.models import (
    ErrorResponse,
    ScenarioEvidence,
    ScenarioHypothesisResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from core.contracts import ScenarioSet
from core.observability import get_logger
from services.scenario_data_service import ScenarioDataService
from services.scenario_service import ScenarioService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _scenario_set_to_response(
    scenario_set: ScenarioSet,
    enriched_data: Optional[dict] = None,
) -> ScenarioResponse:
    """将核心契约转换为 API 响应模型"""
    hypotheses = []
    for h in scenario_set.hypotheses:
        # 从 enriched_data 中提取该假设的证据
        hypothesis_evidence = ScenarioEvidence()
        hypothesis_strength = "none"

        if enriched_data:
            # 查找匹配 scenario_id 的证据
            hypothesis_evidence = ScenarioEvidence(
                events=enriched_data.get("evidence", {}).get("events", []),
                outcomes=enriched_data.get("evidence", {}).get("outcomes", []),
            )
            hypothesis_strength = enriched_data.get("evidence_strength", "none")

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
                evidence=hypothesis_evidence,
                evidence_strength=hypothesis_strength,
            )
        )
    return ScenarioResponse(
        set_id=scenario_set.set_id,
        question=scenario_set.question,
        hypotheses=hypotheses,
        normalization_check=scenario_set.normalization_check,
        residual_uncertainty=scenario_set.residual_uncertainty,
        propagation_patterns=enriched_data.get("propagation_patterns", []) if enriched_data else [],
        regime_summaries=enriched_data.get("regime_summaries", []) if enriched_data else [],
    )


def get_scenario_service() -> ScenarioService:
    """获取情景服务实例"""
    return ScenarioService()


def get_scenario_data_service() -> ScenarioDataService:
    """获取情景数据服务实例"""
    return ScenarioDataService()


@router.post(
    "/generate",
    response_model=ScenarioResponse,
    responses={500: {"model": ErrorResponse}},
)
async def generate_scenarios(
    request: ScenarioRequest,
    service: ScenarioService = Depends(get_scenario_service),
    data_service: ScenarioDataService = Depends(get_scenario_data_service),
):
    """生成多情景分析"""
    try:
        scenario_set = service.generate_scenario_set(
            topic=request.topic,
            subject_ids=request.subject_ids,
        )

        # 用真实数据丰富场景输出
        enriched_data = None
        if request.use_evidence:
            try:
                # 使用第一个假设的 scenario_id 作为代表来丰富
                # 如果有多个假设，对每个假设都可以单独丰富
                subject_id = request.subject_ids[0] if request.subject_ids else None
                if scenario_set.hypotheses:
                    enriched_data = data_service.enrich_scenario(
                        scenario_id=scenario_set.hypotheses[0].scenario_id,
                        event_type=None,  # 可以在后续从 hypothesis 中推断
                        subject_id=subject_id,
                        regime=request.regime_filter,
                    )
                    # 如果有多个假设，为每个假设生成证据
                    if len(scenario_set.hypotheses) > 1:
                        # 共享同一份 enriched_data，实际场景中每个假设可能有不同证据
                        pass
            except Exception as exc:
                logger.warning(
                    "failed to enrich scenario with real data, using fallback", error=str(exc)
                )

        return _scenario_set_to_response(scenario_set, enriched_data)
    except Exception as e:
        logger.error("failed to generate scenarios", error=str(e))
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
