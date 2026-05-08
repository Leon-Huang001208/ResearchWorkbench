"""Governance API — 策略版本管理、实验追踪、回滚、治理报告路由"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.governance import (
    ExperimentComparison,
    ExperimentCreateRequest,
    ExperimentMetricDiff,
    ExperimentRecord,
    GovernanceReport,
    RollbackRequest,
    RollbackResult,
    StrategyComponentType,
    StrategyVersion,
    StrategyVersionCreateRequest,
    StrategyVersionSummary,
)
from core.observability import get_logger
from core.services.governance_service import GovernanceService
from data_layer.repositories.base import get_db
from data_layer.repositories.governance_repository import GovernanceRepositoryImpl

logger = get_logger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])

# 模块级单例
_governance_service: GovernanceService | None = None


# ── 请求/响应模型 ──────────────────────────────────────

class StrategyVersionCreateBody(BaseModel):
    """创建策略版本请求体"""
    component_type: StrategyComponentType
    component_name: str
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    parent_version_id: Optional[str] = None
    created_by: str = "system"
    tags: List[str] = Field(default_factory=list)


class StrategyVersionResponse(BaseModel):
    """策略版本响应"""
    version_id: str
    component_type: str
    component_name: str
    version_number: int
    description: str
    config: Dict[str, Any]
    content_hash: str
    parent_version_id: Optional[str] = None
    is_active: bool
    created_at: str
    created_by: str
    tags: List[str]


class RollbackBody(BaseModel):
    """回滚请求体"""
    component_type: StrategyComponentType
    component_name: str
    target_version_id: str


class RollbackResponse(BaseModel):
    """回滚响应"""
    component_type: str
    component_name: str
    previous_active_version_id: Optional[str] = None
    new_active_version_id: str
    success: bool
    message: str = ""


class ExperimentCreateBody(BaseModel):
    """创建实验请求体"""
    name: str
    description: str = ""
    strategy_version_ids: List[str] = Field(default_factory=list)
    experiment_type: str = "signal"
    entity_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentCompleteBody(BaseModel):
    """完成实验请求体"""
    metrics: Optional[Dict[str, float]] = None


class ExperimentResponse(BaseModel):
    """实验记录响应"""
    experiment_id: str
    name: str
    description: str
    strategy_version_ids: List[str]
    experiment_type: str
    entity_id: Optional[str] = None
    metrics: Dict[str, Any]
    status: str
    started_at: str
    completed_at: Optional[str] = None
    tags: List[str]
    metadata: Dict[str, Any]


class ExperimentCompareBody(BaseModel):
    """实验对比请求体"""
    experiment_a_id: str
    experiment_b_id: str


class ExperimentMetricDiffResponse(BaseModel):
    """实验指标差异响应"""
    metric_name: str
    experiment_a_value: Optional[float] = None
    experiment_b_value: Optional[float] = None
    diff: Optional[float] = None
    pct_change: Optional[float] = None


class ExperimentComparisonResponse(BaseModel):
    """实验对比响应"""
    experiment_a_id: str
    experiment_b_id: str
    experiment_a_name: str
    experiment_b_name: str
    common_metrics: List[ExperimentMetricDiffResponse]
    strategy_diffs: Dict[str, Any]
    summary: str


class StrategyVersionSummaryResponse(BaseModel):
    """策略版本摘要响应"""
    component_type: str
    component_name: str
    active_version_id: Optional[str] = None
    active_version_number: Optional[int] = None
    total_versions: int = 0


class GovernanceReportResponse(BaseModel):
    """治理报告响应"""
    generated_at: str
    strategy_summaries: List[StrategyVersionSummaryResponse]
    total_experiments: int = 0
    recent_experiment_ids: List[str] = Field(default_factory=list)
    active_strategy_count: int = 0
    rollback_candidates: List[Dict[str, Any]] = Field(default_factory=list)


# ── 依赖注入 ───────────────────────────────────────────

def get_governance_service(db: Session = Depends(get_db)) -> GovernanceService:
    """获取治理服务实例（单例 + 请求级 DB session）"""
    global _governance_service
    if _governance_service is None:
        gov_repo = GovernanceRepositoryImpl(db)
        _governance_service = GovernanceService(governance_repository=gov_repo)
    else:
        if _governance_service._gov_repo:
            _governance_service._gov_repo.db = db
    return _governance_service


def _reset_governance_service():
    """重置模块级单例（仅用于测试）"""
    global _governance_service
    _governance_service = None


# ── 辅助转换 ───────────────────────────────────────────

def _version_to_response(v: StrategyVersion) -> StrategyVersionResponse:
    """StrategyVersion → 响应"""
    return StrategyVersionResponse(
        version_id=v.version_id,
        component_type=v.component_type.value,
        component_name=v.component_name,
        version_number=v.version_number,
        description=v.description,
        config=v.config,
        content_hash=v.content_hash,
        parent_version_id=v.parent_version_id,
        is_active=v.is_active,
        created_at=v.created_at.isoformat() if v.created_at else "",
        created_by=v.created_by,
        tags=v.tags,
    )


def _experiment_to_response(e: ExperimentRecord) -> ExperimentResponse:
    """ExperimentRecord → 响应"""
    return ExperimentResponse(
        experiment_id=e.experiment_id,
        name=e.name,
        description=e.description,
        strategy_version_ids=e.strategy_version_ids,
        experiment_type=e.experiment_type,
        entity_id=e.entity_id,
        metrics=e.metrics,
        status=e.status,
        started_at=e.started_at.isoformat() if e.started_at else "",
        completed_at=e.completed_at.isoformat() if e.completed_at else None,
        tags=e.tags,
        metadata=e.metadata,
    )


def _comparison_to_response(c: ExperimentComparison) -> ExperimentComparisonResponse:
    """ExperimentComparison → 响应"""
    return ExperimentComparisonResponse(
        experiment_a_id=c.experiment_a_id,
        experiment_b_id=c.experiment_b_id,
        experiment_a_name=c.experiment_a_name,
        experiment_b_name=c.experiment_b_name,
        common_metrics=[
            ExperimentMetricDiffResponse(
                metric_name=m.metric_name,
                experiment_a_value=m.experiment_a_value,
                experiment_b_value=m.experiment_b_value,
                diff=m.diff,
                pct_change=m.pct_change,
            )
            for m in c.common_metrics
        ],
        strategy_diffs=c.strategy_diffs,
        summary=c.summary,
    )


def _report_to_response(r: GovernanceReport) -> GovernanceReportResponse:
    """GovernanceReport → 响应"""
    return GovernanceReportResponse(
        generated_at=r.generated_at.isoformat(),
        strategy_summaries=[
            StrategyVersionSummaryResponse(
                component_type=s.component_type.value,
                component_name=s.component_name,
                active_version_id=s.active_version_id,
                active_version_number=s.active_version_number,
                total_versions=s.total_versions,
            )
            for s in r.strategy_summaries
        ],
        total_experiments=r.total_experiments,
        recent_experiment_ids=r.recent_experiment_ids,
        active_strategy_count=r.active_strategy_count,
        rollback_candidates=r.rollback_candidates,
    )


# ── 策略版本路由 ───────────────────────────────────────

@router.post(
    "/versions",
    response_model=StrategyVersionResponse,
)
async def register_strategy_version(
    body: StrategyVersionCreateBody,
    service: GovernanceService = Depends(get_governance_service),
):
    """注册新策略版本"""
    try:
        request = StrategyVersionCreateRequest(
            component_type=body.component_type,
            component_name=body.component_name,
            description=body.description,
            config=body.config,
            parent_version_id=body.parent_version_id,
            created_by=body.created_by,
            tags=body.tags,
        )
        version = service.register_version(request)
        return _version_to_response(version)
    except Exception as e:
        logger.error(f"Register strategy version failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/versions",
    response_model=List[StrategyVersionResponse],
)
async def list_strategy_versions(
    component_type: Optional[StrategyComponentType] = Query(None),
    component_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: GovernanceService = Depends(get_governance_service),
):
    """列出策略版本"""
    try:
        versions = service.list_versions(
            component_type=component_type,
            component_name=component_name,
            limit=limit,
        )
        return [_version_to_response(v) for v in versions]
    except Exception as e:
        logger.error(f"List strategy versions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/versions/{version_id}",
    response_model=StrategyVersionResponse,
)
async def get_strategy_version(
    version_id: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """获取策略版本详情"""
    try:
        version = service.get_version(version_id)
        if version is None:
            raise HTTPException(status_code=404, detail=f"Strategy version {version_id} not found")
        return _version_to_response(version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get strategy version failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 回滚路由 ───────────────────────────────────────────

@router.post(
    "/rollback",
    response_model=RollbackResponse,
)
async def rollback_version(
    body: RollbackBody,
    service: GovernanceService = Depends(get_governance_service),
):
    """回滚到指定策略版本"""
    try:
        request = RollbackRequest(
            component_type=body.component_type,
            component_name=body.component_name,
            target_version_id=body.target_version_id,
        )
        result = service.rollback_version(request)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return RollbackResponse(
            component_type=result.component_type.value,
            component_name=result.component_name,
            previous_active_version_id=result.previous_active_version_id,
            new_active_version_id=result.new_active_version_id,
            success=result.success,
            message=result.message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 实验路由 ───────────────────────────────────────────

@router.post(
    "/experiments",
    response_model=ExperimentResponse,
)
async def record_experiment(
    body: ExperimentCreateBody,
    service: GovernanceService = Depends(get_governance_service),
):
    """记录新实验"""
    try:
        request = ExperimentCreateRequest(
            name=body.name,
            description=body.description,
            strategy_version_ids=body.strategy_version_ids,
            experiment_type=body.experiment_type,
            entity_id=body.entity_id,
            tags=body.tags,
            metadata=body.metadata,
        )
        experiment = service.record_experiment(request)
        return _experiment_to_response(experiment)
    except Exception as e:
        logger.error(f"Record experiment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/experiments",
    response_model=List[ExperimentResponse],
)
async def list_experiments(
    experiment_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: GovernanceService = Depends(get_governance_service),
):
    """列出实验记录"""
    try:
        experiments = service.list_experiments(
            experiment_type=experiment_type,
            status=status,
            limit=limit,
        )
        return [_experiment_to_response(e) for e in experiments]
    except Exception as e:
        logger.error(f"List experiments failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentResponse,
)
async def get_experiment(
    experiment_id: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """获取实验详情"""
    try:
        experiment = service.get_experiment(experiment_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
        return _experiment_to_response(experiment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get experiment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/experiments/{experiment_id}/complete",
    response_model=ExperimentResponse,
)
async def complete_experiment(
    experiment_id: str,
    body: ExperimentCompleteBody,
    service: GovernanceService = Depends(get_governance_service),
):
    """完成实验"""
    try:
        experiment = service.complete_experiment(
            experiment_id=experiment_id,
            metrics=body.metrics,
        )
        if experiment is None:
            raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
        return _experiment_to_response(experiment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete experiment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/experiments/compare",
    response_model=ExperimentComparisonResponse,
)
async def compare_experiments(
    body: ExperimentCompareBody,
    service: GovernanceService = Depends(get_governance_service),
):
    """对比两个实验"""
    try:
        from core.contracts.governance import ExperimentCompareRequest

        request = ExperimentCompareRequest(
            experiment_a_id=body.experiment_a_id,
            experiment_b_id=body.experiment_b_id,
        )
        comparison = service.compare_experiments(request)
        return _comparison_to_response(comparison)
    except Exception as e:
        logger.error(f"Compare experiments failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 治理报告路由 ───────────────────────────────────────

@router.get(
    "/report",
    response_model=GovernanceReportResponse,
)
async def generate_governance_report(
    service: GovernanceService = Depends(get_governance_service),
):
    """生成治理报告"""
    try:
        report = service.generate_report()
        return _report_to_response(report)
    except Exception as e:
        logger.error(f"Generate governance report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
