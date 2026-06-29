"""Fund Intelligence API routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.funds import FundDetail, PortfolioFundExposure
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.etl_run_repository import ETLRunRepository
from data_layer.repositories.fund_repository import FundRepository
from services.fund_data_ingestion_service import FundDataIngestionService
from services.fund_intelligence_service import FundIntelligenceService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/funds", tags=["funds"])


class PortfolioExposureRequest(BaseModel):
    """基金组合穿透请求。"""

    positions: Dict[str, float] = Field(description="Fund symbol to portfolio weight")


class FundIngestRowsRequest(BaseModel):
    """基金结构化 rows 导入请求。"""

    dataset: str = Field(description="Dataset key: master, nav, holdings, managers")
    rows: List[Dict[str, Any]] = Field(description="Rows to normalize and ingest")
    source: str = Field(default="api", description="Source label for ETL tracking")


def get_fund_service(db: Session = Depends(get_db)) -> FundIntelligenceService:
    """Build a request-scoped fund intelligence service."""
    repository = FundRepository(db)
    repository.ensure_schema()
    return FundIntelligenceService(repository)


def get_fund_ingestion_service(db: Session = Depends(get_db)) -> FundDataIngestionService:
    """Build a request-scoped fund data ingestion service."""
    return FundDataIngestionService(
        fund_repository=FundRepository(db),
        etl_repository=ETLRunRepository(db),
    )


@router.post("/ingest")
async def ingest_fund_rows(
    request: FundIngestRowsRequest,
    service: FundDataIngestionService = Depends(get_fund_ingestion_service),
) -> dict[str, Any]:
    """Ingest local structured fund rows through the Fund Intelligence repository."""
    try:
        return service.ingest_rows(
            dataset=request.dataset,
            rows=request.rows,
            source=request.source,
        )
    except ValueError as exc:
        logger.warning("fund ingest request rejected", dataset=request.dataset, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("fund ingest API failed", dataset=request.dataset, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to ingest fund rows") from exc


@router.get("/{symbol}", response_model=FundDetail)
async def get_fund_detail(
    symbol: str,
    service: FundIntelligenceService = Depends(get_fund_service),
) -> FundDetail:
    """Return a fund detail view."""
    try:
        detail = service.get_fund_detail(symbol)
        if detail is None:
            raise HTTPException(status_code=404, detail="Fund not found")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("fund detail API failed", symbol=symbol, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to load fund detail") from exc


@router.get("/{symbol}/exposure", response_model=PortfolioFundExposure)
async def get_fund_exposure(
    symbol: str,
    service: FundIntelligenceService = Depends(get_fund_service),
) -> PortfolioFundExposure:
    """Return the latest disclosed exposure for one fund."""
    try:
        return service.get_fund_exposure(symbol)
    except Exception as exc:
        logger.error("fund exposure API failed", symbol=symbol, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to load fund exposure") from exc


@router.post("/portfolio/exposure", response_model=PortfolioFundExposure)
async def calculate_portfolio_exposure(
    request: PortfolioExposureRequest,
    service: FundIntelligenceService = Depends(get_fund_service),
) -> PortfolioFundExposure:
    """Return weighted exposure across a fund portfolio."""
    try:
        return service.calculate_portfolio_exposure(request.positions)
    except Exception as exc:
        logger.error("portfolio fund exposure API failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail="Failed to calculate portfolio exposure"
        ) from exc
