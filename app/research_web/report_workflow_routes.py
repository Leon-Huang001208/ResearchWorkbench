"""Versioned Report Workflow management and native Claw run APIs."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Form, Header, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .report_workflows.models import (
    ReportWorkflowManifest,
    WorkflowError,
    WorkflowSchedule,
)

router = APIRouter(prefix="/api/research")


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


class WorkflowCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    version: int | None = Field(default=None, ge=1)


@router.get("/report-workflows")
async def report_workflows(request: Request):
    return {"items": request.app.state.research.report_workflows.list()}


@router.post("/report-workflows", status_code=201)
async def create_report_workflow(body: ReportWorkflowManifest, request: Request):
    return request.app.state.research.report_workflows.create_draft(body.model_dump())


@router.get("/report-workflows/providers")
async def excel_providers(request: Request):
    return {"items": request.app.state.research.report_workflows.provider_status()}


@router.post("/report-workflows/providers/{provider_id}/probe")
async def probe_excel_provider(
    provider_id: str,
    request: Request,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=1, max_length=160
    ),
):
    return await asyncio.to_thread(
        request.app.state.research.report_workflows.probe,
        provider_id,
        idempotency_key,
    )


@router.post("/report-workflows/migrations")
async def migrate_report_workflows(request: Request, dry_run: bool = True):
    return request.app.state.research.report_workflows.migrate_legacy(dry_run=dry_run)


@router.get("/report-workflows/{workflow_id}")
async def report_workflow(workflow_id: str, request: Request):
    return request.app.state.research.report_workflows.detail(workflow_id)


@router.patch("/report-workflows/{workflow_id}/draft")
async def update_report_workflow_draft(
    workflow_id: str, body: DraftUpdate, request: Request
):
    return request.app.state.research.report_workflows.update_draft(
        workflow_id, **body.model_dump()
    )


@router.post("/report-workflows/{workflow_id}/copy", status_code=201)
async def copy_report_workflow(workflow_id: str, body: WorkflowCopy, request: Request):
    return request.app.state.research.report_workflows.copy(
        workflow_id, body.id, body.name, body.version
    )


@router.post("/report-workflows/{workflow_id}/resources", status_code=201)
async def upload_report_resource(
    workflow_id: str,
    request: Request,
    file: UploadFile,
    path: Annotated[str, Form(min_length=1, max_length=240)],
):
    try:
        raw = await file.read(32 * 1024 * 1024 + 1)
        return request.app.state.research.report_workflows.upload_resource(
            workflow_id,
            path,
            raw,
        )
    finally:
        if file is not None:
            await file.close()


@router.post("/report-workflows/{workflow_id}/versions", status_code=201)
async def create_report_version(workflow_id: str, request: Request):
    return request.app.state.research.report_workflows.create_version(workflow_id)


@router.get("/report-workflows/{workflow_id}/versions")
async def report_versions(workflow_id: str, request: Request):
    return {"items": request.app.state.research.report_workflows.versions(workflow_id)}


@router.post("/report-workflows/{workflow_id}/versions/{version}/publish")
async def publish_report_version(workflow_id: str, version: int, request: Request):
    return request.app.state.research.report_workflows.publish(workflow_id, version)


@router.post("/report-workflows/{workflow_id}/versions/{version}/rollback")
async def rollback_report_version(workflow_id: str, version: int, request: Request):
    return request.app.state.research.report_workflows.rollback(workflow_id, version)


@router.post("/report-workflows/{workflow_id}/disable")
async def disable_report_workflow(workflow_id: str, request: Request):
    return request.app.state.research.report_workflows.disable(workflow_id)


@router.post("/report-workflows/{workflow_id}/versions/{version}/preflight")
async def preflight_report_version(workflow_id: str, version: int, request: Request):
    return request.app.state.research.report_workflows.catalog.preflight(
        workflow_id, version
    )


@router.get("/report-workflows/{workflow_id}/versions/{version}/resources")
async def report_resources(workflow_id: str, version: int, request: Request):
    items = request.app.state.research.report_workflows.catalog.list_resources(
        workflow_id, version
    )
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.get(
    "/report-workflows/{workflow_id}/versions/{version}/resources/{resource_path:path}"
)
async def download_report_resource(
    workflow_id: str, version: int, resource_path: str, request: Request
):
    path = request.app.state.research.report_workflows.resource(
        workflow_id, version, resource_path
    )
    return FileResponse(path, filename=path.name)


@router.post("/report-workflows/{workflow_id}/runs", status_code=202)
async def run_report_workflow(workflow_id: str, request: Request):
    return await request.app.state.research.report_workflows.runtime.start_run(
        workflow_id
    )


@router.get("/report-workflows/{workflow_id}/runs")
async def report_workflow_runs(workflow_id: str, request: Request):
    return {
        "items": request.app.state.research.report_workflows.runtime.runs(workflow_id)
    }


@router.get("/report-workflows/{workflow_id}/schedule")
async def report_workflow_schedule(workflow_id: str, request: Request):
    return request.app.state.research.report_workflows.runtime.schedule(workflow_id)


@router.put("/report-workflows/{workflow_id}/schedule")
async def save_report_workflow_schedule(
    workflow_id: str, body: WorkflowSchedule, request: Request
):
    return request.app.state.research.report_workflows.runtime.put_schedule(
        workflow_id, body.model_dump()
    )


@router.get("/report-runs/{run_id}")
async def report_run(run_id: str, request: Request):
    runtime = request.app.state.research.report_workflows.runtime
    try:
        return runtime.public_run(runtime._run(run_id))
    except WorkflowError as exc:
        if exc.code != "run_not_found":
            raise
        legacy = request.app.state.research.report_studio
        return legacy.public_run(legacy._run(run_id))


@router.post("/report-runs/{run_id}/cancel")
async def cancel_report_run(run_id: str, request: Request):
    runtime = request.app.state.research.report_workflows.runtime
    try:
        return await runtime.cancel(run_id)
    except WorkflowError as exc:
        if exc.code != "run_not_found":
            raise
        return await request.app.state.research.report_studio.cancel(run_id)


@router.post("/report-runs/{run_id}/retry", status_code=202)
async def retry_report_run(run_id: str, request: Request):
    return await request.app.state.research.report_workflows.runtime.retry(run_id)


@router.get("/report-runs/{run_id}/refresh-manifests")
async def report_refresh_manifests(run_id: str, request: Request):
    catalog = request.app.state.research.report_workflows.catalog
    manifest = catalog.read_refresh_manifest(run_id)
    workbooks = manifest.get("workbooks")
    return {"items": workbooks if isinstance(workbooks, list) else [manifest]}


@router.get("/report-runs/{run_id}/delivery")
async def report_delivery(run_id: str, request: Request):
    runtime = request.app.state.research.report_workflows.runtime
    row = runtime._run(run_id)
    return {
        "status": row.get("delivery_status", "pending"),
        "artifacts": row.get("artifacts", []),
        "missing": row.get("missing", []),
    }
