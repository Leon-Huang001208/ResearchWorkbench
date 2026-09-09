"""Runtime provider declarations and health API."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routes.research_runs import get_research_run_service
from core.contracts.research_workspace import ProviderExecutionResult, RuntimeProvider
from core.observability import get_logger
from data_layer.repositories.base import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/runtime-providers", tags=["runtime-providers"])


class ProviderResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_hash: str = Field(min_length=1)
    result: ProviderExecutionResult


def get_runtime_provider_service(db: Session = Depends(get_db)):
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.runtime_provider_service import RuntimeProviderService

    return RuntimeProviderService(repository=ResearchWorkspaceRepository(db))


@router.get("", response_model=list[RuntimeProvider])
async def list_runtime_providers(service=Depends(get_runtime_provider_service)):
    return service.list_providers()


@router.put("/{provider_id}", response_model=RuntimeProvider, status_code=status.HTTP_200_OK)
async def upsert_runtime_provider(
    provider_id: str,
    provider: RuntimeProvider,
    service=Depends(get_runtime_provider_service),
) -> RuntimeProvider:
    if provider.provider_id != provider_id:
        raise HTTPException(status_code=422, detail="Provider ID mismatch")
    try:
        return service.save_provider(provider)
    except Exception as exc:
        logger.error("runtime provider API failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Runtime provider update failed") from exc


@router.post(
    "/{provider_id}/results",
    response_model=ProviderExecutionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def accept_provider_result(
    provider_id: str,
    request: ProviderResultRequest,
    service=Depends(get_runtime_provider_service),
    run_service=Depends(get_research_run_service),
) -> ProviderExecutionResult:
    """Accept one typed, idempotent DSH terminal callback."""

    if request.result.provider_id != provider_id:
        raise HTTPException(status_code=422, detail="Provider result ID mismatch")
    if request.result.request_hash != request.request_hash:
        raise HTTPException(status_code=422, detail="Provider result hash mismatch")
    try:
        run_service.accept_provider_result(request.result, request_hash=request.request_hash)
        return request.result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Provider result conflict") from exc
    except Exception as exc:
        logger.error("provider result persistence failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Provider result persistence failed") from exc
