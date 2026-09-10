"""Dedicated Research Web endpoints for local integration diagnosis."""

from typing import Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/research")


class LocalVerificationRequest(BaseModel):
    target: Literal["excel", "word", "powerpoint", "wind_excel"]


@router.get("/local-integrations")
def local_integrations(request: Request):
    return request.app.state.research.local_integrations.snapshot()


@router.post("/local-integrations/probes", status_code=202)
async def start_local_integrations_probe(
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return request.app.state.research.local_integrations.start_probe(idempotency_key)


@router.get("/local-integrations/probes/{probe_id}")
async def local_integrations_probe(probe_id: str, request: Request):
    return request.app.state.research.local_integrations.probe(probe_id)


@router.post("/local-integrations/verifications", status_code=202)
async def start_local_integration_verification(
    body: LocalVerificationRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return request.app.state.research.local_integrations.start_verification(
        body.target, idempotency_key
    )


@router.get("/local-integrations/verifications/{verification_id}")
async def local_integration_verification(verification_id: str, request: Request):
    return request.app.state.research.local_integrations.verification(verification_id)
