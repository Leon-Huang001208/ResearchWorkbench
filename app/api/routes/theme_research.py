"""Thin FastAPI routes for declarative Theme Research Packs."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.theme_research import (
    PackHealth,
    ThemeAssetProjection,
    ThemeEventProjection,
    ThemeKPIProjection,
    ThemePackManifest,
    ThemeSnapshot,
    ThemeValueChainProjection,
    WorkspacePrefillRequest,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.theme_research_service import (
    ThemeDataUnavailableError,
    ThemePackNotFoundError,
    ThemeResearchService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/themes", tags=["theme-research"])


class WorkspacePrefillCreateRequest(BaseModel):
    """User-selected title for a theme-scoped research workspace command."""

    title: str | None = Field(default=None, min_length=1, max_length=240)


DBSession = Annotated[Session, Depends(get_db)]
AsOfQuery = Annotated[AwareDatetime | None, Query()]


def get_theme_research_service(db: DBSession) -> ThemeResearchService:
    """Build request-scoped dependencies without eager service imports in app startup."""

    from data_layer.repositories.theme_research_repository import (
        ThemeResearchRepository,
    )
    from services.theme_pack_registry import ThemePackRegistry

    pack_root = Path(__file__).parents[3] / "resources" / "research_packs"
    return ThemeResearchService(
        ThemeResearchRepository(db),
        ThemePackRegistry(pack_root),
    )


ThemeResearchServiceDependency = Annotated[
    ThemeResearchService,
    Depends(get_theme_research_service),
]


def _raise_safe_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, ThemePackNotFoundError):
        raise HTTPException(status_code=404, detail="Theme pack not found") from exc
    if isinstance(exc, ThemeDataUnavailableError):
        raise HTTPException(status_code=404, detail="Theme data unavailable") from exc
    if isinstance(exc, (ValueError, TypeError)):
        raise HTTPException(status_code=400, detail="Invalid theme research request") from exc
    logger.error("theme research API failed", error_type=type(exc).__name__)
    raise HTTPException(status_code=500, detail="Theme research request failed") from exc


@router.get("", response_model=list[ThemePackManifest])
async def list_theme_catalog(
    service: ThemeResearchServiceDependency,
) -> list[ThemePackManifest]:
    try:
        return service.list_catalog()
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/snapshot", response_model=ThemeSnapshot)
async def get_theme_snapshot(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> ThemeSnapshot:
    try:
        return service.get_snapshot(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/kpis", response_model=ThemeKPIProjection)
async def get_theme_kpis(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> ThemeKPIProjection:
    try:
        return service.get_kpis(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/value-chain", response_model=ThemeValueChainProjection)
async def get_theme_value_chain(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> ThemeValueChainProjection:
    try:
        return service.get_value_chain(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/events", response_model=ThemeEventProjection)
async def get_theme_events(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> ThemeEventProjection:
    try:
        return service.get_events(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/assets", response_model=ThemeAssetProjection)
async def get_theme_assets(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> ThemeAssetProjection:
    try:
        return service.get_assets(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.get("/{pack_key}/health", response_model=PackHealth)
async def get_theme_health(
    pack_key: str,
    service: ThemeResearchServiceDependency,
    as_of: AsOfQuery = None,
) -> PackHealth:
    try:
        return service.get_health(pack_key, as_of)
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)


@router.post(
    "/{pack_key}/research-workspaces",
    response_model=WorkspacePrefillRequest,
    status_code=status.HTTP_201_CREATED,
)
async def create_theme_research_workspace_request(
    pack_key: str,
    request: WorkspacePrefillCreateRequest,
    service: ThemeResearchServiceDependency,
) -> WorkspacePrefillRequest:
    try:
        result = service.create_research_workspace_request(pack_key, request.title)
        logger.info(
            "theme research workspace entry accepted",
            pack_key=pack_key,
            template_key=result.template_key,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate to a safe API response
        _raise_safe_http_error(exc)
