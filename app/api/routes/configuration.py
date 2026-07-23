"""系统配置中心 API 路由。"""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from app.api.configuration_models import (
    SECTION_UPDATE_MODELS,
    ConfigurationSnapshotResponse,
    ConfigurationTestResponse,
    ConfigurationUpdateResponse,
    SectionName,
)
from app.api.configuration_security import (
    CONFIGURATION_CSRF_TOKEN,
    require_configuration_csrf_token,
    require_configuration_origin_only,
)
from core.observability import get_logger
from services.configuration_service import (
    ConfigurationError,
    ConfigurationPersistenceError,
    ConfigurationService,
)

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/config",
    tags=["configuration"],
)


@router.get("/token", dependencies=[Depends(require_configuration_origin_only)])
def get_config_token() -> dict[str, str]:
    """颁发当前进程的配置 CSRF token。

    只校验 Origin/Host，无需预先持有 token。
    前端启动时调用此端点，将 token 存入内存，
    后续所有 /api/config 请求从内存读取，避免后端重启 token 失效。
    """
    return {"token": CONFIGURATION_CSRF_TOKEN}


def get_configuration_service() -> ConfigurationService:
    """提供配置服务，便于测试替换运行时路径。"""
    return ConfigurationService()


def _validate_payload(section: str, payload: Any) -> dict[str, Any]:
    try:
        model = SECTION_UPDATE_MODELS[section].model_validate(payload)
    except ValidationError as exc:
        safe_errors = [
            {
                "loc": list(error.get("loc", ())),
                "type": str(error.get("type", "value_error")),
                "msg": "输入值未通过校验",
            }
            for error in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=safe_errors) from exc
    return model.model_dump(exclude_unset=True)


@router.get(
    "",
    response_model=ConfigurationSnapshotResponse,
    dependencies=[Depends(require_configuration_csrf_token)],
)
def get_configuration(
    service: ConfigurationService = Depends(get_configuration_service),
) -> dict[str, Any]:
    """读取全部配置的脱敏快照。"""
    try:
        return service.get_snapshot()
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail="配置读取失败") from exc


@router.put(
    "/{section}",
    response_model=ConfigurationUpdateResponse,
    dependencies=[Depends(require_configuration_csrf_token)],
)
def update_configuration(
    section: SectionName,
    payload: Any = Body(...),
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


@router.post(
    "/{section}/test",
    response_model=ConfigurationTestResponse,
    dependencies=[Depends(require_configuration_csrf_token)],
)
def test_configuration(
    section: SectionName,
    payload: Any = Body(...),
    service: ConfigurationService = Depends(get_configuration_service),
) -> dict[str, Any]:
    """非破坏性验证尚未保存的分区配置。"""
    validated = _validate_payload(section, payload)
    try:
        return service.test_section(section, validated)
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
