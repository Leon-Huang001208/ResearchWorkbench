"""Dossier HTTP surface delegates ownership to the request's selected ResearchService."""

from fastapi import APIRouter, Query, Request

from . import models

router = APIRouter(prefix="/api/research/dossiers")


@router.get("")
@router.get("/", include_in_schema=False)
async def list_dossiers(
    request: Request,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, pattern=r"^[0-9]{1,6}$"),
):
    return request.app.state.research.dossiers.list(
        include_archived=include_archived, limit=limit, cursor=cursor
    )


@router.post("", status_code=201)
@router.post("/", status_code=201, include_in_schema=False)
async def create_dossier(body: models.Create, request: Request):
    return request.app.state.research.dossiers.create(body.model_dump(mode="json"))


@router.get("/{did}")
async def get_dossier(did: str, request: Request):
    return request.app.state.research.dossiers.get(did)


@router.patch("/{did}")
async def patch_dossier(did: str, body: models.Patch, request: Request):
    return request.app.state.research.dossiers.patch(
        did, body.model_dump(mode="json", exclude_none=True)
    )


@router.post("/{did}/records")
async def add_record(did: str, body: models.Record, request: Request):
    return request.app.state.research.dossiers.add_record(
        did, body.model_dump(mode="json", exclude_none=True)
    )


@router.get("/{did}/timeline")
async def timeline(
    did: str,
    request: Request,
    kind: str | None = Query(default=None, pattern=r"^[a-z_]{1,20}$"),
    state: str | None = Query(default=None, pattern=r"^[a-z_]{1,20}$"),
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, pattern=r"^[0-9]{1,6}$"),
):
    return request.app.state.research.dossiers.timeline(
        did, kind=kind, state=state, limit=limit, cursor=cursor
    )


@router.post("/{did}/evidence")
async def add_evidence(did: str, body: models.Evidence, request: Request):
    return request.app.state.research.dossiers.add_evidence(
        did, body.model_dump(mode="json", exclude_none=True)
    )


@router.get("/{did}/evidence/{eid}")
async def read_evidence(did: str, eid: str, request: Request):
    return request.app.state.research.dossiers.read_evidence(did, eid)


@router.post("/{did}/links")
async def link(did: str, body: models.Link, request: Request):
    return await request.app.state.research.dossiers.add_link(
        did, body.model_dump(mode="json", exclude_none=True)
    )


@router.post("/{did}/handoff")
async def handoff(did: str, body: models.Handoff, request: Request):
    return request.app.state.research.dossiers.handoff(did, body.model_dump(mode="json"))
