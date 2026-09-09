"""Local product package APIs; runtime mutations share ResearchService.lock."""

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import Response

from .models import (
    ArtifactInput,
    CapabilityError,
    CopyInput,
    CreationInput,
    DraftInput,
    VersionInput,
)
from .packages import MAX_COMPRESSED
from .tools import tool_catalog

router = APIRouter(prefix="/api/research")


@router.get("/capabilities")
async def catalog(request: Request, kind: str | None = None):
    if kind not in (None, "skill", "workflow"):
        raise CapabilityError("未知能力类型")
    return request.app.state.research.capabilities.list(kind)


@router.get("/tools")
def tools(request: Request):
    return tool_catalog(request.app.state.research.store.root)


@router.get("/workflows")
async def workflows(request: Request):
    return request.app.state.research.capabilities.list("workflow")


@router.post("/capabilities", status_code=201)
async def create(body: DraftInput, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.capabilities.create(body.model_dump())


@router.post("/capabilities/import", status_code=201)
async def import_file(file: UploadFile, request: Request):
    try:
        raw = await file.read(MAX_COMPRESSED + 1)
        service = request.app.state.research
        async with service.lock:
            return service.capabilities.import_bytes(file.filename or "", raw)
    finally:
        await file.close()


@router.post("/capabilities/creation-sessions", status_code=201)
async def creation(body: CreationInput, request: Request):
    return await request.app.state.research.create_capability_session(body.kind, body.goal)


@router.post("/capabilities/from-artifact", status_code=201)
async def from_artifact(body: ArtifactInput, request: Request):
    return await request.app.state.research.capability_from_artifact(body.session_id, body.file_id)


@router.get("/capabilities/{cid}")
async def detail(cid: str, request: Request):
    return request.app.state.research.capabilities.detail(cid)


@router.patch("/capabilities/{cid}/draft")
async def edit(cid: str, body: DraftInput, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.capabilities.edit(cid, body.model_dump())


@router.post("/capabilities/{cid}/copy", status_code=201)
async def copy(cid: str, body: CopyInput, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.capabilities.copy(cid, body.name, body.slug)


@router.post("/capabilities/{cid}/check")
async def check(cid: str, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.capabilities.check(cid)


@router.post("/capabilities/{cid}/publish")
async def publish(cid: str, request: Request):
    return await request.app.state.research.change_capability(cid, "publish")


@router.post("/capabilities/{cid}/disable")
async def disable(cid: str, request: Request):
    return await request.app.state.research.change_capability(cid, "disable")


@router.post("/capabilities/{cid}/enable")
async def enable(cid: str, request: Request):
    return await request.app.state.research.change_capability(cid, "enable")


@router.post("/capabilities/{cid}/rollback")
async def rollback(cid: str, body: VersionInput, request: Request):
    return await request.app.state.research.change_capability(cid, "rollback", body.version)


@router.get("/capabilities/{cid}/versions")
async def versions(cid: str, request: Request):
    return request.app.state.research.capabilities.versions(cid)


@router.get("/capabilities/{cid}/versions/{version}/export")
async def export(cid: str, version: int, request: Request):
    raw = request.app.state.research.capabilities.export(cid, version)
    return Response(
        raw,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{cid}-v{version}.zip"'},
    )


@router.get("/capabilities/{cid}/versions/{version}")
async def version_detail(cid: str, version: int, request: Request):
    return request.app.state.research.capabilities.version_detail(cid, version)
