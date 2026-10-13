"""Claw project and schedule-draft API over the existing product data root."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .automation.models import AutomationCreate

router = APIRouter(prefix="/api/research")


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProjectCreate(StrictBody):
    name: str = Field(min_length=1, max_length=120)


class ProjectUpdate(StrictBody):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None


class ProjectMove(StrictBody):
    project_id: str = Field(min_length=1, max_length=64)


class FileReference(StrictBody):
    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    file_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DraftProposal(StrictBody):
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    body: AutomationCreate


@router.get("/claw/projects")
async def projects(request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.claw_projects.list()


@router.post("/claw/projects", status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.claw_projects.create(body.name)


@router.get("/claw/projects/{project_id}")
async def project(project_id: str, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.claw_projects.detail(project_id)


@router.patch("/claw/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, request: Request):
    service = request.app.state.research
    async with service.lock:
        return service.claw_projects.update(project_id, **body.model_dump())


@router.put("/sessions/{sid}/project")
async def move_session(sid: str, body: ProjectMove, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = service.claw_projects.move(sid, body.project_id)
    service.notify()
    return result


@router.post("/sessions/{sid}/file-references", status_code=201)
async def reference_file(sid: str, body: FileReference, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = service.claw_projects.reference(
            sid, body.source_session_id, body.file_id, body.expected_sha256
        )
    service.notify()
    return result


@router.get("/sessions/{sid}/automation-drafts")
async def drafts(sid: str, request: Request):
    return request.app.state.research.automation_drafts.list(sid)


@router.post("/internal/data/automation-draft", status_code=201)
async def propose_draft(body: DraftProposal, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    async with service.lock:
        result = service.automation_drafts.prepare(body.session_id, body.body)
    service.notify()
    return result


@router.post("/sessions/{sid}/automation-drafts/{draft_id}/confirm", status_code=201)
async def confirm_draft(sid: str, draft_id: str, body: AutomationCreate, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = service.automation_drafts.confirm(sid, draft_id, body)
    service.notify()
    return result


@router.post("/sessions/{sid}/automation-drafts/{draft_id}/dismiss")
async def dismiss_draft(sid: str, draft_id: str, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = service.automation_drafts.dismiss(sid, draft_id)
    service.notify()
    return result
