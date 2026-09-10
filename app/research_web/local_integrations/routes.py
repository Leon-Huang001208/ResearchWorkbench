"""Dedicated Research Web endpoints for local integration diagnosis."""

from fastapi import APIRouter, Header, Request

router = APIRouter(prefix="/api/research")


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
