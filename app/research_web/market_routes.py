"""Sessionless market reads and explicitly admitted refresh operations."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from core.observability import get_logger

from .market_service import DEFAULT_SECTIONS, MarketError

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/market", tags=["market"])
Section = Literal["quotes", "indices", "industry", "concept", "flows", "calendar", "members"]


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[Section] = Field(
        default_factory=lambda: list(DEFAULT_SECTIONS), min_length=1, max_length=7
    )
    board_id: str | None = Field(default=None, pattern=r"^BK[0-9]{4,6}$")
    kind: Literal["industry", "concept"] = "industry"
    period: Literal["today", "5d", "10d"] = "today"


class QuoteFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exchange: Literal["all", "SH", "SZ", "BJ"] = "all"
    board: Literal["all", "main", "star", "chinext", "beijing"] = "all"
    search: str = Field(default="", max_length=80)
    sort: Literal[
        "asset",
        "code",
        "name",
        "exchange",
        "board",
        "price",
        "change",
        "change_pct",
        "volume",
        "amount",
        "amplitude_pct",
        "turnover_rate_pct",
        "volume_ratio",
        "pe_dynamic",
        "pb",
        "total_market_cap",
        "float_market_cap",
        "change_5m_pct",
        "change_60d_pct",
        "change_ytd_pct",
        "as_of",
    ] = "change_pct"
    direction: Literal["asc", "desc"] = "desc"
    board_id: str | None = Field(default=None, pattern=r"^BK[0-9]{4,6}$")
    snapshot_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")


class QuotePage(QuoteFilters):
    offset: int = Field(default=0, ge=0, le=20000)
    limit: int = Field(default=50, ge=1, le=200)


def _failure(exc: MarketError) -> JSONResponse:
    log.warning("market_request_rejected", code=exc.code)
    return JSONResponse(
        status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}}
    )


@router.get("")
async def overview(request: Request):
    return request.app.state.research.market.overview()


@router.post("/refresh", status_code=202)
async def refresh(
    body: RefreshRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(min_length=8, max_length=128)] = None,
):
    try:
        return await request.app.state.research.market.refresh(
            **body.model_dump(), idempotency_key=idempotency_key
        )
    except MarketError as exc:
        return _failure(exc)


@router.get("/refresh/{request_id}")
async def refresh_status(request_id: str, request: Request):
    try:
        return request.app.state.research.market.request(request_id)
    except MarketError as exc:
        return _failure(exc)


@router.delete("/refresh/{request_id}")
async def cancel(request_id: str, request: Request):
    try:
        return await request.app.state.research.market.cancel(request_id)
    except MarketError as exc:
        return _failure(exc)


@router.get("/quotes/export")
async def export_quotes(request: Request, filters: Annotated[QuoteFilters, Query()]):
    try:
        text, snapshot_id = request.app.state.research.market.export_quotes(**filters.model_dump())
        return Response(
            text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="market-{snapshot_id}.csv"',
                "Cache-Control": "no-store",
            },
        )
    except MarketError as exc:
        return _failure(exc)


@router.get("/quotes")
async def quotes(request: Request, filters: Annotated[QuotePage, Query()]):
    try:
        return request.app.state.research.market.quotes(**filters.model_dump())
    except MarketError as exc:
        return _failure(exc)
