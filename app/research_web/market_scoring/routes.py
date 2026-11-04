"""Read profiles and explicitly run research scores using immutable record IDs."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from core.observability import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/market-scores", tags=["market-scores"])
Index = Literal["SSE", "CSI300", "CHINEXT", "SP500", "NASDAQ", "DJI", "HSI", "HSCEI", "HSTECH"]
Reference = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


async def tracked(request, operation):
    def execute():
        with request.app.state.research.event_inputs.activity():
            return operation()

    return await run_in_threadpool(execute)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_id: Index
    as_of: str = Field(min_length=20, max_length=50)
    inputs_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    validation_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    overlay_ids: list[Reference] = Field(default_factory=list, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=128)


@router.get("")
async def overview(
    request: Request,
    index_id: Index = "SSE",
    as_of: str | None = Query(default=None, max_length=50),
):
    return await tracked(
        request, lambda: request.app.state.research.market_scores.preview(index_id, as_of)
    )


@router.get("/profiles")
async def profiles(request: Request):
    return request.app.state.research.market_scores.profiles()


@router.get("/runs")
async def runs(
    request: Request, limit: int = Query(default=50, ge=1, le=100), cursor: str | None = None
):
    return await tracked(
        request, lambda: request.app.state.research.market_scores.list(limit=limit, cursor=cursor)
    )


@router.post("/runs", status_code=201)
async def create_run(body: RunRequest, request: Request):
    log.info("market_score_run_requested", index_id=body.index_id)
    return await tracked(
        request,
        lambda: request.app.state.research.market_scores.create(body.model_dump(mode="json")),
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    return await tracked(request, lambda: request.app.state.research.market_scores.get(run_id))
