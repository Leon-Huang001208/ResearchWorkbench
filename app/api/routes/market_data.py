"""Market Data API 路由

提供股票列表同步、日行情同步、日行情查询、ETL 运行记录查询。
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.services.market_data_ingestion_service import MarketDataIngestionService
from data_layer.repositories.base import get_db
from data_layer.repositories.etl_run_repository import ETLRunRepository
from data_layer.repositories.market_data_repository import MarketDataRepository

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


class DailyBarSyncRequest(BaseModel):
    """日行情同步请求"""

    symbols: list[str] = Field(..., description="股票代码列表，如 600519.SH")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")


class SyncResponse(BaseModel):
    """同步操作响应"""

    run_id: str
    fetched: int
    saved: int


def _get_market_repo(db: Session = Depends(get_db)) -> MarketDataRepository:
    return MarketDataRepository(db)


def _get_etl_repo(db: Session = Depends(get_db)) -> ETLRunRepository:
    return ETLRunRepository(db)


def _get_ingestion_service(
    market_repo: MarketDataRepository = Depends(_get_market_repo),
    etl_repo: ETLRunRepository = Depends(_get_etl_repo),
) -> MarketDataIngestionService:
    return MarketDataIngestionService(market_repo=market_repo, etl_repo=etl_repo)


@router.post("/stocks/sync", response_model=SyncResponse)
async def sync_stock_master(
    limit: int | None = Query(None, description="限制数量"),
    service: MarketDataIngestionService = Depends(_get_ingestion_service),
):
    """同步股票列表到 stock_master 表"""
    try:
        result = service.ingest_stock_master(limit=limit)
        return SyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily-bars/sync", response_model=SyncResponse)
async def sync_daily_bars(
    request: DailyBarSyncRequest,
    service: MarketDataIngestionService = Depends(_get_ingestion_service),
):
    """同步日行情到 stock_daily_bar 表"""
    try:
        result = service.ingest_daily_bars(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return SyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/daily-bars")
async def get_daily_bars(
    symbol: str,
    start_date: str | None = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(500, description="最大返回条数"),
    repo: MarketDataRepository = Depends(_get_market_repo),
):
    """查询某只股票的日行情数据"""
    from datetime import datetime

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    bars = repo.get_daily_bars(symbol, start_date=start, end_date=end, limit=limit)
    return {
        "symbol": symbol,
        "count": len(bars),
        "bars": [
            {
                "trade_date": b.trade_date.isoformat() if b.trade_date else None,
                "open": float(b.open) if b.open else None,
                "high": float(b.high) if b.high else None,
                "low": float(b.low) if b.low else None,
                "close": float(b.close) if b.close else None,
                "volume": float(b.volume) if b.volume else None,
                "amount": float(b.amount) if b.amount else None,
                "turnover": float(b.turnover) if b.turnover else None,
            }
            for b in bars
        ],
    }


@router.get("/etl-runs")
async def list_etl_runs(
    limit: int = Query(50, description="最大返回条数"),
    repo: ETLRunRepository = Depends(_get_etl_repo),
):
    """查询最近的 ETL 运行记录"""
    runs = repo.get_recent_runs(limit=limit)
    return {
        "count": len(runs),
        "runs": [
            {
                "run_id": r.run_id,
                "job_name": r.job_name,
                "source": r.source,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "items_fetched": r.items_fetched,
                "items_normalized": r.items_normalized,
                "items_saved": r.items_saved,
                "error_message": r.error_message,
            }
            for r in runs
        ],
    }
