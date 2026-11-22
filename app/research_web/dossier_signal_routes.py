"""Personal frozen-evidence scans; no provider or model execution."""

from datetime import date

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .automation.models import AutomationSchedule
from .dossiers.scans import DossierSignals

router = APIRouter(prefix="/api/research/dossiers")


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    as_of: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @field_validator("as_of")
    @classmethod
    def valid_day(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value


class TrackingRequest(ScanRequest):
    enabled: bool
    schedule: AutomationSchedule | None = None


def service(request):
    return DossierSignals(request.app.state.research)


@router.get("/signals")
def list_signals(
    request: Request,
    dossier_id: str | None = None,
    state: str | None = None,
    kind: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    return service(request).list(
        dossier_id=dossier_id, state=state, kind=kind, cursor=cursor, limit=limit
    )


@router.post("/{dossier_id}/scan")
async def scan(dossier_id: str, body: ScanRequest, request: Request):
    return await service(request).scan(dossier_id, body.model_dump(exclude_none=True))


@router.patch("/{dossier_id}/tracking")
def tracking(dossier_id: str, body: TrackingRequest, request: Request):
    return service(request).tracking(dossier_id, body.model_dump(exclude_none=True))
