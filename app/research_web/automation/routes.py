"""FastAPI surface for Automation runs, migrations, and delivery channels."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from .models import (
    AutomationCreate,
    AutomationError,
    AutomationUpdate,
    DeliveryChannelPut,
    MigrationApply,
)
from .service import automation_feature_enabled

router = APIRouter(prefix="/api/research")


def service(request: Request):
    if not automation_feature_enabled():
        raise AutomationError("Automation 尚未启用", "automation_disabled", 404)
    return request.app.state.research.automations


@router.get("/automations")
def automations(request: Request):
    return service(request).list()


@router.post("/automations", status_code=201)
def create_automation(body: AutomationCreate, request: Request):
    return service(request).create(body)


@router.post("/automations/migrations/report-schedules/preview")
def preview_report_schedule_migrations(request: Request):
    return service(request).preview_report_schedule_migrations()


@router.post("/automations/migrations/report-schedules/apply")
def apply_report_schedule_migrations(body: MigrationApply, request: Request):
    return service(request).apply_report_schedule_migrations(body.workflow_ids)


@router.get("/automations/{automation_id}")
def automation(automation_id: str, request: Request):
    return service(request).get(automation_id)


@router.patch("/automations/{automation_id}")
def update_automation(automation_id: str, body: AutomationUpdate, request: Request):
    return service(request).update(automation_id, body)


@router.delete("/automations/{automation_id}")
def delete_automation(automation_id: str, request: Request):
    return service(request).delete(automation_id)


@router.post("/automations/{automation_id}/enable")
def enable_automation(automation_id: str, request: Request):
    return service(request).enable(automation_id)


@router.post("/automations/{automation_id}/disable")
def disable_automation(automation_id: str, request: Request):
    return service(request).disable(automation_id)


@router.post("/automations/{automation_id}/run", status_code=202)
async def run_automation(automation_id: str, request: Request):
    return await service(request).run(automation_id)


@router.get("/automation-runs")
def automation_runs(
    request: Request,
    automation_id: str | None = Query(default=None, max_length=255),
):
    return service(request).list_runs(automation_id=automation_id)


@router.post("/automation-runs/{run_id}/retry", status_code=202)
async def retry_automation_run(run_id: str, request: Request):
    return await service(request).retry(run_id)


@router.get("/delivery-channels")
def delivery_channels(request: Request):
    return service(request).channels.list()


@router.put("/delivery-channels")
def put_delivery_channel(body: DeliveryChannelPut, request: Request):
    return service(request).channels.put(body)
