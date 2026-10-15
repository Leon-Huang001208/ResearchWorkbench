"""Claw project and schedule-draft API over the existing product data root."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .automation.models import AutomationCreate, AutomationUpdate
from .claw_projects import ClawProjects
from .navigation import Navigation
from .store import StoreError

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


class NavigationPin(StrictBody):
    kind: Literal["session", "project"]
    id: str = Field(min_length=1, max_length=64)


class NavigationUpdate(StrictBody):
    revision: int = Field(ge=0)
    pinned: list[NavigationPin] = Field(max_length=10000)
    project_order: list[str] = Field(max_length=10000)


class FileReference(StrictBody):
    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    file_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DraftProposal(StrictBody):
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    body: AutomationCreate


class AutomationAction(StrictBody):
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    operation: str = Field(pattern=r"^(list|prepare_update|run)$")
    automation_id: str | None = Field(default=None, max_length=255)
    body: AutomationUpdate | None = None


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
        result = ClawProjects(service, service.store.session(sid)["mode"]).move(
            sid, body.project_id
        )
    service.notify()
    return result


@router.post("/sessions/{sid}/file-references", status_code=201)
async def reference_file(sid: str, body: FileReference, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = ClawProjects(service, service.store.session(sid)["mode"]).reference(
            sid, body.source_session_id, body.file_id, body.expected_sha256
        )
    service.notify()
    return result


@router.get("/projects")
async def mode_projects(request: Request, mode: Literal["claw", "fingpt"]):
    service = request.app.state.research
    async with service.lock:
        return ClawProjects(service, mode).list()


@router.post("/projects", status_code=201)
async def create_mode_project(
    body: ProjectCreate, request: Request, mode: Literal["claw", "fingpt"]
):
    service = request.app.state.research
    async with service.lock:
        return ClawProjects(service, mode).create(body.name)


@router.get("/projects/{project_id}")
async def mode_project(project_id: str, request: Request, mode: Literal["claw", "fingpt"]):
    service = request.app.state.research
    async with service.lock:
        return ClawProjects(service, mode).detail(project_id)


@router.patch("/projects/{project_id}")
async def update_mode_project(
    project_id: str, body: ProjectUpdate, request: Request, mode: Literal["claw", "fingpt"]
):
    service = request.app.state.research
    async with service.lock:
        return ClawProjects(service, mode).update(project_id, **body.model_dump())


@router.get("/navigation/{mode}")
async def navigation(mode: Literal["claw", "fingpt"], request: Request):
    service = request.app.state.research
    async with service.lock:
        return Navigation(service, mode).get()


@router.patch("/navigation/{mode}")
async def update_navigation(
    mode: Literal["claw", "fingpt"], body: NavigationUpdate, request: Request
):
    service = request.app.state.research
    async with service.lock:
        return Navigation(service, mode).update(**body.model_dump())


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


@router.post("/internal/data/automation-action")
async def automation_action(body: AutomationAction, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    async with service.lock:
        session = service.automation_drafts._session(body.session_id)
        if session.get("purpose") == "automation":
            raise StoreError("研究执行不能管理或递归试跑日程", "automation_control_denied", 409)
        if body.operation == "list":
            result = (
                {"items": [service.automations.get(body.automation_id)]}
                if body.automation_id
                else service.automations.list()
            )
            fields = {
                "id",
                "automation_id",
                "trigger",
                "definition_version",
                "research_status",
                "delivery_status",
                "failure_code",
                "session_id",
                "created_at",
                "summary",
                "artifacts",
            }
            result["runs"] = [
                {key: value for key, value in run.items() if key in fields}
                for run in service.automations.list_runs(automation_id=body.automation_id)["items"][
                    :20
                ]
            ]
        elif body.operation == "prepare_update" and body.automation_id and body.body:
            result = service.automation_drafts.prepare_update(
                body.session_id, body.automation_id, body.body
            )
        elif body.operation == "run" and body.automation_id and body.body is None:
            result = await service.run_automation_from_chat(body.session_id, body.automation_id)
        else:
            raise StoreError("日程操作参数不完整", "automation_action_invalid", 422)
    service.notify()
    return result


@router.post("/sessions/{sid}/automation-drafts/{draft_id}/confirm", status_code=201)
async def confirm_draft(
    sid: str,
    draft_id: str,
    body: AutomationCreate | AutomationUpdate,
    request: Request,
    enable: bool = False,
):
    service = request.app.state.research
    async with service.lock:
        draft = service.automation_drafts._get(sid, draft_id)
        if draft.get("operation") == "update" and isinstance(body, AutomationUpdate):
            result = service.automation_drafts.confirm_update(sid, draft_id, body)
        elif draft.get("operation") != "update" and isinstance(body, AutomationCreate):
            result = service.automation_drafts.confirm(sid, draft_id, body, enable=enable)
        else:
            raise StoreError("确认卡内容类型不符", "invalid_request", 422)
        service.store.session(sid)["automation_trial_context"] = {
            "automation_id": result["id"],
            "definition_version": result.get("definition_version", 1),
        }
        service.store.save()
    service.notify()
    return result


@router.post("/sessions/{sid}/automation-drafts/{draft_id}/dismiss")
async def dismiss_draft(sid: str, draft_id: str, request: Request):
    service = request.app.state.research
    async with service.lock:
        result = service.automation_drafts.dismiss(sid, draft_id)
    service.notify()
    return result
