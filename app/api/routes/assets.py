"""资产分析路由"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.models import AnalyzeRequest, AnalyzeResponse, ErrorResponse
from core.contracts import AssetAnalysisSnapshot
from core.services.asset_analysis_service import AssetAnalysisService

router = APIRouter(prefix="/api/assets", tags=["assets"])


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
    """获取资产分析服务实例（生产级真实数据源）"""
    from data_layer.repositories.postgres_asset_snapshot_repo import PostgresAssetSnapshotRepository
    from data_layer.adapters.IFinDAdapter import IFinDAdapter

    repo = PostgresAssetSnapshotRepository(db_session=db)
    ifind_adapter = IFinDAdapter()
    return AssetAnalysisService(asset_snapshot_repo=repo, ifind_adapter=ifind_adapter, use_mock=False)


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
        snapshot = service.generate_snapshot(
            canonical_id=request.canonical_id,
            as_of=request.as_of,
            use_mock=request.use_mock,
            source=request.source,
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
