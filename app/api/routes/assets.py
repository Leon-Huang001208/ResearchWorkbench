"""资产分析路由"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.models import AnalyzeRequest, AnalyzeResponse, ErrorResponse
from core.contracts import AssetAnalysisCard, AssetAnalysisSnapshot
from data_layer.coordinator.multi_source_coordinator import get_coordinator
from data_layer.repositories.base import get_db
from services.asset_analysis_service import AssetAnalysisService

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AnalysisCardRequest(BaseModel):
    """资产分析卡请求"""

    canonical_id: str = Field(..., description="资产唯一标识")
    as_of: datetime | None = Field(None, description="指定分析时间")


class AnalysisCardResponse(AssetAnalysisCard):
    """资产分析卡响应"""

    pass


def _snapshot_to_response(snapshot: AssetAnalysisSnapshot) -> AnalyzeResponse:
    """将核心契约转换为 API 响应模型"""
    return AnalyzeResponse(
        canonical_id=snapshot.canonical_id,
        as_of=snapshot.as_of,
        financial=snapshot.financial,
        fund_flow=snapshot.fund_flow,
        price_volume=snapshot.price_volume,
        valuation=snapshot.valuation,
        shareholder=snapshot.shareholder,
        industry=snapshot.industry,
        event_impact=snapshot.event_impact,
        macro_exposure=snapshot.macro_exposure,
        evidence_refs=snapshot.evidence_refs,
    )


def get_asset_service(db: Session = Depends(get_db)) -> AssetAnalysisService:
    """获取资产分析服务实例"""
    from data_layer.repositories.market_data_repository import MarketDataRepository
    from data_layer.repositories.postgres_asset_snapshot_repo import PostgresAssetSnapshotRepository
    from services.wind_analysis_service import WindAnalysisService

    repo = PostgresAssetSnapshotRepository(db_session=db)
    coordinator = get_coordinator()

    # 尝试创建 Wind 分析服务（如果 Wind 不可用则跳过，自动降级）
    wind_service = None
    try:
        wind_service = WindAnalysisService()
    except Exception:
        pass

    return AssetAnalysisService(
        asset_snapshot_repo=repo,
        coordinator=coordinator,
        market_repo=MarketDataRepository(db),
        wind_service=wind_service,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={500: {"model": ErrorResponse}},
)
async def analyze_asset(
    request: AnalyzeRequest,
    service: AssetAnalysisService = Depends(get_asset_service),
):
    """生成资产分析快照"""
    try:
        snapshot = await service.generate_snapshot(
            canonical_id=request.canonical_id,
            as_of=request.as_of,
        )
        return _snapshot_to_response(snapshot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{canonical_id}",
    response_model=AnalyzeResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_asset_snapshot(
    canonical_id: str,
    service: AssetAnalysisService = Depends(get_asset_service),
):
    """查询资产最新快照"""
    snapshot = service.get_latest_snapshot(canonical_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Snapshot not found for {canonical_id}")
    return _snapshot_to_response(snapshot)


@router.post(
    "/analysis-card",
    response_model=AnalysisCardResponse,
    responses={500: {"model": ErrorResponse}},
)
async def get_analysis_card(
    request: AnalysisCardRequest,
    service: AssetAnalysisService = Depends(get_asset_service),
):
    """生成资产分析卡片（包含K线、资金流向、股东、财务、行业、事件、宏观等完整信息）"""
    try:
        card = await service.generate_analysis_card(
            canonical_id=request.canonical_id,
            as_of=request.as_of,
        )
        return card
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
