"""Thin API routes for the facts-only market home."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.contracts.market_home import (
    MarketHomeEnvelope,
    MarketHomeInvalidationEvent,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.market_home_repository import MarketHomeRepository
from services.market_home_service import (
    SnapshotConflictError,
    SnapshotNotClosedError,
    SnapshotNotFoundError,
)

if TYPE_CHECKING:
    from services.market_home_service import MarketHomeService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/market-home", tags=["market-home"])


def get_market_home_service(db: Session = Depends(get_db)) -> MarketHomeService:
    """Inject the request-scoped market-home service without eager heavy imports."""

    from services.market_home_service import MarketHomeService

    return MarketHomeService(MarketHomeRepository(db))


@router.get("/live", response_model=MarketHomeEnvelope)
async def get_live_market_home(
    service: MarketHomeService = Depends(get_market_home_service),
) -> MarketHomeEnvelope:
    try:
        return service.get_live()
    except Exception as exc:
        logger.exception(
            "market home live request failed",
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="无法读取市场首页。") from exc


@router.get("/drill-down/{section_key}", response_model=MarketHomeSection)
async def get_market_home_drill_down(
    section_key: MarketHomeSectionKey,
    service: MarketHomeService = Depends(get_market_home_service),
) -> MarketHomeSection:
    try:
        return service.get_live_section(section_key)
    except Exception as exc:
        logger.exception(
            "market home drill-down failed",
            section_key=section_key.value,
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="无法读取市场首页区块。") from exc


@router.get("/snapshots/{trading_day}", response_model=list[MarketHomeSnapshot])
async def get_market_home_snapshot(
    trading_day: date,
    service: MarketHomeService = Depends(get_market_home_service),
) -> list[MarketHomeSnapshot]:
    try:
        return service.get_snapshot(trading_day)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail="市场首页历史快照不存在。") from exc
    except SnapshotConflictError as exc:
        logger.error("market home snapshot is incomplete", trading_day=trading_day.isoformat())
        raise HTTPException(status_code=409, detail="市场首页收盘快照冲突。") from exc
    except Exception as exc:
        logger.exception(
            "market home snapshot read failed",
            trading_day=trading_day.isoformat(),
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="无法读取市场首页历史快照。") from exc


@router.post("/snapshots/{trading_day}", response_model=list[MarketHomeSnapshot])
async def create_market_home_snapshot(
    trading_day: date,
    service: MarketHomeService = Depends(get_market_home_service),
) -> list[MarketHomeSnapshot]:
    try:
        return service.create_close_snapshot(trading_day)
    except SnapshotNotClosedError as exc:
        raise HTTPException(status_code=400, detail="交易日尚未收盘，不能创建快照。") from exc
    except SnapshotConflictError as exc:
        logger.error("market home snapshot conflict", trading_day=trading_day.isoformat())
        raise HTTPException(status_code=409, detail="市场首页收盘快照冲突。") from exc
    except Exception as exc:
        logger.exception(
            "market home snapshot creation failed",
            trading_day=trading_day.isoformat(),
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="无法创建市场首页收盘快照。") from exc


def _format_market_home_sse_event(event: MarketHomeInvalidationEvent) -> str:
    """Serialize only the durable invalidation reference, never section facts."""

    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.event_id}\n" "event: market_home.section_invalidated\n" f"data: {data}\n\n"


async def _market_home_event_stream(
    request: Request,
    service: MarketHomeService,
    initial_events: list[MarketHomeInvalidationEvent],
    *,
    replay_only: bool = False,
) -> AsyncIterator[str]:
    last_event_id = request.headers.get("Last-Event-ID")
    pending = initial_events
    try:
        while True:
            for event in pending:
                last_event_id = event.event_id
                yield _format_market_home_sse_event(event)
            if replay_only:
                return
            if await request.is_disconnected():
                break
            await asyncio.sleep(2.0)
            pending = service.list_invalidation_events(last_event_id)
            if not pending:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        logger.info("market home SSE client disconnected")
    except Exception as exc:
        logger.exception(
            "market home SSE polling failed",
            error_type=type(exc).__name__,
        )


@router.get("/events")
async def stream_market_home_events(
    request: Request,
    replay_only: bool = False,
    service: MarketHomeService = Depends(get_market_home_service),
) -> StreamingResponse:
    last_event_id = request.headers.get("Last-Event-ID")
    try:
        initial_events = service.list_invalidation_events(last_event_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID 无效。") from exc
    except Exception as exc:
        logger.exception(
            "market home SSE replay failed",
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="无法订阅市场首页事件。") from exc
    return StreamingResponse(
        _market_home_event_stream(request, service, initial_events, replay_only=replay_only),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
