"""Declarative Skill API with platform-owned execution authorization."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.runtime_providers import get_runtime_provider_service
from core.contracts.research_workspace import SkillManifest
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/research-skills", tags=["research-skills"])


def get_authorized_tool_registry() -> frozenset[str]:
    """Read the administrator-owned registry; requests cannot add capabilities."""

    from services.runtime_provider_service import load_authorized_tool_registry

    return load_authorized_tool_registry()


@router.get("", response_model=list[SkillManifest])
async def list_skills(service=Depends(get_runtime_provider_service)):
    return service.list_skills()


@router.post("", response_model=SkillManifest, status_code=status.HTTP_201_CREATED)
async def save_skill(
    manifest: SkillManifest,
    service=Depends(get_runtime_provider_service),
) -> SkillManifest:
    try:
        return service.save_skill(
            manifest,
            authorized_tool_ids=get_authorized_tool_registry(),
            now=datetime.now(UTC),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Skill tool denied") from exc
    except Exception as exc:
        logger.error("research Skill API failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Research Skill update failed") from exc
