"""Report Studio API contracts."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/research")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    project_type: Literal["report", "weekly", "presentation"] = "report"
    draft: dict[str, Any] = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: (
        Literal["draft", "needs_attention", "ready", "enabled", "disabled"] | None
    ) = None
    draft: dict[str, Any] | None = None


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: dict[str, Any] | None = None
    output_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png"]] = Field(
        min_length=1, max_length=6
    )
    sections: list[dict[str, Any]] = Field(default_factory=list, max_length=60)
    data_recipe: list[dict[str, Any]] = Field(default_factory=list, max_length=60)
    instructions: str = Field(default="", max_length=100000)


class ProjectAction(BaseModel):
    version: int | None = Field(default=None, ge=1, strict=True)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["off", "once", "weekly"] = "off"
    enabled: bool = False
    once_at: str | None = None
    weekday: int | None = Field(default=None, ge=0, le=6, strict=True)
    hour: int | None = Field(default=None, ge=0, le=23, strict=True)
    minute: int | None = Field(default=None, ge=0, le=59, strict=True)


@router.get("/report-projects")
async def projects(request: Request):
    return {"items": request.app.state.research.report_studio.list_projects()}


@router.post("/report-projects", status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    return request.app.state.research.report_studio.create_project(body.model_dump())


@router.get("/report-projects/{project_id}")
async def project(project_id: str, request: Request):
    return request.app.state.research.report_studio.project(project_id)


@router.patch("/report-projects/{project_id}")
async def patch_project(project_id: str, body: ProjectPatch, request: Request):
    return request.app.state.research.report_studio.patch_project(
        project_id, body.model_dump(exclude_none=True)
    )


@router.post("/report-projects/{project_id}/versions", status_code=201)
async def create_version(project_id: str, body: VersionCreate, request: Request):
    return request.app.state.research.report_studio.create_version(
        project_id, body.model_dump()
    )


@router.post("/report-projects/{project_id}/files", status_code=201)
async def add_project_file(project_id: str, file: UploadFile, request: Request):
    raw = await file.read(32 * 1024 * 1024 + 1)
    return request.app.state.research.report_studio.add_project_file(
        project_id, file.filename or "", raw
    )


@router.get("/report-projects/{project_id}/versions")
async def versions(project_id: str, request: Request):
    return {"items": request.app.state.research.report_studio.versions(project_id)}


@router.post("/report-projects/{project_id}/rollback")
async def rollback(project_id: str, body: ProjectAction, request: Request):
    return request.app.state.research.report_studio.rollback(
        project_id, body.version or 1
    )


@router.post("/report-projects/{project_id}/runs", status_code=202)
async def run_project(project_id: str, request: Request):
    return await request.app.state.research.report_studio.start_run(project_id)


@router.get("/report-projects/{project_id}/runs")
async def runs(project_id: str, request: Request):
    return {"items": request.app.state.research.report_studio.runs(project_id)}


@router.get("/report-runs/{run_id}")
async def run(run_id: str, request: Request):
    return request.app.state.research.report_studio.public_run(
        request.app.state.research.report_studio._run(run_id)
    )


@router.post("/report-runs/{run_id}/cancel")
async def cancel(run_id: str, request: Request):
    return await request.app.state.research.report_studio.cancel(run_id)


@router.get("/report-projects/{project_id}/schedule")
async def schedule(project_id: str, request: Request):
    return request.app.state.research.report_studio.schedule(project_id)


@router.put("/report-projects/{project_id}/schedule")
async def put_schedule(project_id: str, body: ScheduleInput, request: Request):
    return request.app.state.research.report_studio.put_schedule(
        project_id, body.model_dump()
    )


@router.get("/report-projects/{project_id}/artifacts")
async def artifacts(
    project_id: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    rows = request.app.state.research.report_studio.artifacts(project_id)
    return {
        "items": rows[offset : offset + limit],
        "total": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/report-projects/{project_id}/artifacts/{artifact_id}")
async def artifact(
    project_id: str, artifact_id: str, request: Request, preview: bool = False
):
    path = request.app.state.research.report_studio.artifact_path(
        project_id, artifact_id
    )
    disposition = (
        "inline"
        if preview and path.suffix.lower() in {".html", ".png"}
        else "attachment"
    )
    return FileResponse(path, filename=path.name, content_disposition_type=disposition)
