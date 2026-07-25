"""动态多因子 API 端点

提供因子定义管理、因子值存取、因子评估查询和动态权重快照。
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.contracts.factors import (
    DynamicFactorWeights,
    FactorCategory,
    FactorDefinition,
    FactorEvaluation,
    FactorValue,
)
from core.observability import get_logger
from services.factor_store_service import FactorStore

logger = get_logger(__name__)

router = APIRouter(prefix="/api/factors", tags=["factors"])

_store: FactorStore | None = None


def _get_store() -> FactorStore:
    global _store
    if _store is None:
        _store = FactorStore()
    return _store


# ─── Request / Response models ────────────────────────────


class FactorDefinitionRequest(BaseModel):
    """因子定义创建/更新请求"""

    factor_id: str = Field(..., description="Stable machine-readable factor id")
    name: str = Field(..., description="Human-readable factor name")
    category: str = Field(..., description="Factor taxonomy bucket")
    direction: str = Field(default="positive", description="positive / negative / neutral")
    description: str = Field(default="")
    version: str = Field(default="v1")
    horizon_days: Optional[int] = Field(default=None, ge=1)
    refresh_frequency: str = Field(default="1d")
    metadata: dict = Field(default_factory=dict)


class FactorValueRequest(BaseModel):
    """因子值批量提交请求"""

    values: list[dict] = Field(
        ...,
        description="List of {factor_id, subject_id, as_of_date, value}",
    )


class FactorEvaluationRequest(BaseModel):
    """因子评估批量提交请求"""

    evaluations: list[dict] = Field(
        ...,
        description="List of evaluation records",
    )


class WeightsSnapshotRequest(BaseModel):
    """动态权重快照请求"""

    as_of_date: Optional[str] = Field(default=None, description="ISO date")
    lookback_periods: int = Field(default=12, ge=1)
    metric: str = Field(default="rank_ic")
    weights: dict[str, float] = Field(default_factory=dict)
    raw_scores: dict[str, float] = Field(default_factory=dict)


# ─── Factor Definitions ───────────────────────────────────


@router.get("/definitions")
async def list_definitions(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    factor_ids: Optional[str] = Query(default=None, description="Comma-separated factor IDs"),
):
    """列出已注册的因子定义"""
    store = _get_store()
    ids = [fid.strip() for fid in factor_ids.split(",") if fid.strip()] if factor_ids else None
    try:
        definitions = store.get_definitions(factor_ids=ids, category=category)
        return {
            "success": True,
            "data": [d.model_dump() for d in definitions],
            "count": len(definitions),
        }
    except Exception as e:
        logger.error("Failed to list definitions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/definitions")
async def register_definitions(definitions: list[FactorDefinitionRequest]):
    """注册或更新因子定义"""
    store = _get_store()
    try:
        parsed = [
            FactorDefinition(
                factor_id=d.factor_id,
                name=d.name,
                category=FactorCategory(d.category),
                direction=d.direction,
                description=d.description,
                version=d.version,
                horizon_days=d.horizon_days,
                refresh_frequency=d.refresh_frequency,
                metadata=d.metadata,
            )
            for d in definitions
        ]
        count = store.register_definitions(parsed)
        logger.info("Registered %d factor definitions", count)
        return {"success": True, "data": {"registered": count}}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Failed to register definitions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Factor Values ────────────────────────────────────────


@router.get("/values")
async def query_values(
    as_of_date: Optional[str] = Query(
        default=None, description="ISO date for point-in-time snapshot"
    ),
    factor_ids: Optional[str] = Query(default=None, description="Comma-separated factor IDs"),
    subject_ids: Optional[str] = Query(default=None, description="Comma-separated subject IDs"),
    start_date: Optional[str] = Query(default=None, description="ISO start date"),
    end_date: Optional[str] = Query(default=None, description="ISO end date"),
    limit: int = Query(default=10000, ge=1, le=100000),
):
    """查询因子值"""
    store = _get_store()
    try:
        if as_of_date:
            dt = date.fromisoformat(as_of_date)
            fids = [f.strip() for f in factor_ids.split(",") if f.strip()] if factor_ids else None
            values = store.load_values(as_of_date=dt, factor_ids=fids)
        else:
            fids = [f.strip() for f in factor_ids.split(",") if f.strip()] if factor_ids else None
            sids = [s.strip() for s in subject_ids.split(",") if s.strip()] if subject_ids else None
            sd = date.fromisoformat(start_date) if start_date else None
            ed = date.fromisoformat(end_date) if end_date else None
            values = store.load_values_range(
                factor_ids=fids,
                subject_ids=sids,
                start_date=sd,
                end_date=ed,
                limit=limit,
            )
        return {
            "success": True,
            "data": [v.model_dump(mode="json") for v in values],
            "count": len(values),
        }
    except Exception as e:
        logger.error("Failed to query values: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/values")
async def store_values(request: FactorValueRequest):
    """批量存储因子值"""
    store = _get_store()
    try:
        parsed = []
        for item in request.values:
            parsed.append(
                FactorValue(
                    factor_id=item["factor_id"],
                    subject_id=item["subject_id"],
                    as_of_date=date.fromisoformat(item["as_of_date"])
                    if isinstance(item["as_of_date"], str)
                    else item["as_of_date"],
                    value=item.get("value"),
                    available_at=datetime.fromisoformat(item["available_at"])
                    if item.get("available_at")
                    else None,
                    source=item.get("source"),
                    metadata=item.get("metadata", {}),
                )
            )
        count = store.store_values(parsed)
        logger.info("Stored %d factor values", count)
        return {"success": True, "data": {"stored": count}}
    except Exception as e:
        logger.error("Failed to store values: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Factor Evaluations ───────────────────────────────────


@router.get("/evaluations")
async def query_evaluations(
    factor_ids: Optional[str] = Query(default=None, description="Comma-separated factor IDs"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """查询因子评估记录"""
    store = _get_store()
    try:
        fids = [f.strip() for f in factor_ids.split(",") if f.strip()] if factor_ids else None
        sd = date.fromisoformat(start_date) if start_date else None
        ed = date.fromisoformat(end_date) if end_date else None
        evaluations = store.load_evaluations(
            factor_ids=fids,
            start_date=sd,
            end_date=ed,
            limit=limit,
        )
        return {
            "success": True,
            "data": [e.model_dump(mode="json") for e in evaluations],
            "count": len(evaluations),
        }
    except Exception as e:
        logger.error("Failed to query evaluations: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluations")
async def store_evaluations(request: FactorEvaluationRequest):
    """批量存储因子评估指标"""
    store = _get_store()
    try:
        parsed = []
        for item in request.evaluations:
            parsed.append(
                FactorEvaluation(
                    factor_id=item["factor_id"],
                    as_of_date=date.fromisoformat(item["as_of_date"])
                    if isinstance(item.get("as_of_date"), str) and item.get("as_of_date")
                    else None,
                    horizon_days=item.get("horizon_days", 20),
                    sample_size=item.get("sample_size", 0),
                    coverage=item.get("coverage", 0.0),
                    ic=item.get("ic", 0.0),
                    rank_ic=item.get("rank_ic", 0.0),
                    decile_spread=item.get("decile_spread", 0.0),
                    metadata=item.get("metadata", {}),
                )
            )
        count = store.store_evaluations(parsed)
        logger.info("Stored %d factor evaluations", count)
        return {"success": True, "data": {"stored": count}}
    except Exception as e:
        logger.error("Failed to store evaluations: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Dynamic Weights ──────────────────────────────────────


@router.get("/weights/latest")
async def get_latest_weights(
    metric: str = Query(default="rank_ic", description="ic or rank_ic"),
):
    """获取最新的动态因子权重"""
    store = _get_store()
    try:
        weights = store.load_latest_weights(metric=metric)
        if weights is None:
            return {"success": True, "data": None, "message": "No weights snapshot found"}
        return {"success": True, "data": weights.model_dump(mode="json")}
    except Exception as e:
        logger.error("Failed to get latest weights: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weights")
async def save_weights(request: WeightsSnapshotRequest):
    """保存动态因子权重快照"""
    store = _get_store()
    try:
        weights = DynamicFactorWeights(
            as_of_date=date.fromisoformat(request.as_of_date)
            if request.as_of_date
            else date.today(),
            lookback_periods=request.lookback_periods,
            metric=request.metric,
            weights=request.weights,
            raw_scores=request.raw_scores,
        )
        count = store.store_weights(weights)
        return {"success": True, "data": {"saved": count}}
    except Exception as e:
        logger.error("Failed to save weights: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weights/history")
async def get_weights_history(
    metric: str = Query(default="rank_ic"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """查询动态权重历史"""
    store = _get_store()
    try:
        history = store.load_weights_history(metric=metric, limit=limit)
        return {
            "success": True,
            "data": [w.model_dump(mode="json") for w in history],
            "count": len(history),
        }
    except Exception as e:
        logger.error("Failed to get weights history: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Utility ──────────────────────────────────────────────


@router.get("/available-dates")
async def get_available_dates(
    factor_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """获取有因子数据的日期列表"""
    store = _get_store()
    try:
        dates = store.get_available_dates(factor_id=factor_id, limit=limit)
        return {
            "success": True,
            "data": [d.isoformat() for d in dates],
            "count": len(dates),
        }
    except Exception as e:
        logger.error("Failed to get available dates: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories():
    """获取所有已注册的因子类别"""
    store = _get_store()
    try:
        categories = store.get_all_categories()
        return {"success": True, "data": categories, "count": len(categories)}
    except Exception as e:
        logger.error("Failed to get categories: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
