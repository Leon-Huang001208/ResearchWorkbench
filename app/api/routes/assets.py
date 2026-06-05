"""资产分析路由"""
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.models import AnalyzeRequest, AnalyzeResponse, ErrorResponse
from cognitive_agents import AgentWorkflowResult
from core.contracts import AssetAnalysisCard, AssetAnalysisSnapshot
from core.interfaces.repository import AssetSnapshotRepository
from core.observability import get_logger
from data_layer.coordinator.multi_source_coordinator import get_coordinator
from data_layer.repositories.base import get_db
from data_layer.repositories.documents_v1 import DocumentV1Repository
from data_layer.repositories.event_repository import EventRepositoryImpl
from ingestion import KnowledgePipeline
from services.asset_agent_committee_service import AssetAgentCommitteeService
from services.asset_analysis_service import AssetAnalysisService
from services.official_evidence_backfill_service import OfficialEvidenceBackfillService
from services.official_evidence_service import OfficialEvidenceService

router = APIRouter(prefix="/api/assets", tags=["assets"])
logger = get_logger(__name__)


VALID_TIME_RANGES = {"1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "ALL"}


class AnalysisCardRequest(BaseModel):
    """资产分析卡请求"""

    canonical_id: str = Field(..., description="资产唯一标识")
    as_of: datetime | None = Field(None, description="指定分析时间")
    time_range: str | None = Field(None, description="时间范围: 1M/3M/6M/1Y/2Y/3Y/5Y/ALL，默认1Y")

    @field_validator("time_range")
    @classmethod
    def _validate_time_range(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in VALID_TIME_RANGES:
            raise ValueError(
                f"Invalid time_range '{v}'. Must be one of: {', '.join(sorted(VALID_TIME_RANGES))}"
            )
        return v.upper() if v else v


class AnalysisCardResponse(AssetAnalysisCard):
    """资产分析卡响应"""

    pass


class AgentCommitteeRequest(BaseModel):
    """资产多 Agent 委员会请求"""

    canonical_id: str = Field(..., description="资产唯一标识")
    question: str = Field("这个标的是否值得进入研究池？", description="委员会分析问题")
    event_id: str | None = Field(None, description="关联事件ID")
    as_of: datetime | None = Field(None, description="指定分析时间")
    time_range: str | None = Field(None, description="时间范围: 1M/3M/6M/1Y/2Y/3Y/5Y/ALL，默认1Y")

    @field_validator("time_range")
    @classmethod
    def _validate_time_range(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in VALID_TIME_RANGES:
            raise ValueError(
                f"Invalid time_range '{v}'. Must be one of: {', '.join(sorted(VALID_TIME_RANGES))}"
            )
        return v.upper() if v else v


class OfficialEvidenceBackfillRequest(BaseModel):
    """巨潮官方证据回补请求"""

    limit: int = Field(20, ge=1, le=100, description="本次最多处理的巨潮公告数")
    offset: int = Field(0, ge=0, description="分页偏移量")


class OfficialEvidenceBackfillResponse(BaseModel):
    """巨潮官方证据回补响应"""

    processed: int
    events: int
    failed: int


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

    repo = PostgresAssetSnapshotRepository(db_session=db)
    coordinator = get_coordinator()
    return AssetAnalysisService(
        asset_snapshot_repo=cast(AssetSnapshotRepository, repo),
        coordinator=coordinator,
        market_repo=MarketDataRepository(db),
    )


def get_asset_committee_service(
    service: AssetAnalysisService = Depends(get_asset_service),
    db: Session = Depends(get_db),
) -> AssetAgentCommitteeService:
    """获取资产多 Agent 委员会服务实例"""
    official_evidence = OfficialEvidenceService(DocumentV1Repository(db))
    return AssetAgentCommitteeService(service, official_evidence_provider=official_evidence)


def get_official_evidence_backfill_service(
    db: Session = Depends(get_db),
) -> OfficialEvidenceBackfillService:
    """获取巨潮官方证据回补服务实例"""
    document_repo = DocumentV1Repository(db)
    event_repo = EventRepositoryImpl(db)
    pipeline = KnowledgePipeline(event_repo=event_repo)
    return OfficialEvidenceBackfillService(document_repo, pipeline)


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
            time_range=request.time_range,
        )
        return card
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/agent-committee",
    response_model=AgentWorkflowResult,
    responses={500: {"model": ErrorResponse}},
)
async def run_asset_agent_committee(
    request: AgentCommitteeRequest,
    service: AssetAgentCommitteeService = Depends(get_asset_committee_service),
):
    """运行资产多 Agent 委员会分析，不替换原资产分析卡。"""
    try:
        return await service.analyze(
            canonical_id=request.canonical_id,
            question=request.question,
            event_id=request.event_id,
            as_of=request.as_of,
            time_range=request.time_range,
        )
    except Exception as e:
        logger.error(
            "asset_agent_committee_failed",
            extra={"canonical_id": request.canonical_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/official-evidence/backfill-cninfo",
    response_model=OfficialEvidenceBackfillResponse,
    responses={500: {"model": ErrorResponse}},
)
async def backfill_cninfo_official_evidence(
    request: OfficialEvidenceBackfillRequest,
    service: OfficialEvidenceBackfillService = Depends(get_official_evidence_backfill_service),
):
    """将已入库的巨潮公告回补进 KnowledgePipeline，生成官方事件证据。"""
    try:
        return await service.backfill_cninfo(limit=request.limit, offset=request.offset)
    except Exception as e:
        logger.error(
            "cninfo_official_evidence_backfill_failed",
            extra={"limit": request.limit, "offset": request.offset, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
