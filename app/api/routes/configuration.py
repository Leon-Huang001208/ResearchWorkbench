"""系统配置中心 API 路由。"""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.configuration_models import (
    SECTION_UPDATE_MODELS,
    ConfigurationSnapshotResponse,
    ConfigurationTestResponse,
    ConfigurationUpdateResponse,
    SectionName,
)
from core.observability import get_logger
from services.configuration_service import (
    ConfigurationError,
    ConfigurationPersistenceError,
    ConfigurationService,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/config", tags=["configuration"])


def get_configuration_service() -> ConfigurationService:
    """提供配置服务，便于测试替换运行时路径。"""
    return ConfigurationService()


def _validate_payload(section: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        model = SECTION_UPDATE_MODELS[section].model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return model.model_dump(exclude_unset=True)


@router.get("", response_model=ConfigurationSnapshotResponse)
def get_configuration(
    service: ConfigurationService = Depends(get_configuration_service),
) -> dict[str, Any]:
    """读取全部配置的脱敏快照。"""
    try:
        return service.get_snapshot()
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail="配置读取失败") from exc


@router.put("/{section}", response_model=ConfigurationUpdateResponse)
def update_configuration(
    section: SectionName,
    payload: dict[str, Any] = Body(...),
    service: ConfigurationService = Depends(get_configuration_service),
) -> dict[str, Any]:
    """校验、持久化并按分区应用配置。"""
    validated = _validate_payload(section, payload)
    try:
        return service.update_section(section, validated)
    except ConfigurationPersistenceError as exc:
        logger.error("配置 API 持久化失败", extra={"section": section})
        raise HTTPException(status_code=500, detail="配置保存失败") from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{section}/test", response_model=ConfigurationTestResponse)
def test_configuration(
    section: SectionName,
    payload: dict[str, Any] = Body(...),
    service: ConfigurationService = Depends(get_configuration_service),
) -> dict[str, Any]:
    """非破坏性验证尚未保存的分区配置。"""
    validated = _validate_payload(section, payload)
    try:
        return service.test_section(section, validated)
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
