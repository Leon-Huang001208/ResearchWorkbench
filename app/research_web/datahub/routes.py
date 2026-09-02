"""Read-only browser catalog; authenticated native-only query and cancel ingress."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from .contracts import InternalCancel, InternalQuery

router = APIRouter(prefix="/api/research")


@router.get("/data/capabilities")
async def capabilities(request: Request):
    return request.app.state.research.datahub.capabilities()


@router.get("/sessions/{sid}/datasets")
async def datasets(sid: str, request: Request):
    return {"items": request.app.state.research.datahub.summaries(sid)}


@router.get("/sessions/{sid}/datasets/{did}")
async def detail(sid: str, did: str, request: Request):
    return request.app.state.research.datahub.detail(sid, did)


@router.get("/sessions/{sid}/datasets/{did}/rows")
async def rows(
    sid: str,
    did: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    return request.app.state.research.datahub.rows(sid, did, offset, limit)


@router.get("/sessions/{sid}/datasets/{did}/files/{name}")
async def download(
    sid: str, did: str, name: Literal["rows.csv", "rows.json", "manifest.json"], request: Request
):
    content = request.app.state.research.datahub.snapshots.read(sid, did, name)
    return Response(
        content,
        media_type="text/csv" if name.endswith(".csv") else "application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/internal/data/query")
async def query(body: InternalQuery, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    try:
        result = await service.datahub.query(body.session_id, body.call_id, body.query)
        service.notify()
        return result
    except asyncio.CancelledError:
        return JSONResponse({"status": "cancelled"}, status_code=409)


@router.post("/internal/data/cancel")
async def cancel(body: InternalCancel, request: Request):
    return await request.app.state.research.datahub.cancel(body.session_id, body.call_id)
