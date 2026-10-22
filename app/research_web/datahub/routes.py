"""Read-only browser catalog; authenticated native-only query and cancel ingress."""

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from ..market_store import MarketStoreError
from ..store import StoreError
from .connections import (
    CredentialStoreError,
    MySQLConfiguration,
    canonical_source_id,
)
from .contracts import InternalBusinessQuery, InternalCancel

router = APIRouter(prefix="/api/research")


class MySQLConfigurationUpdate(MySQLConfiguration):
    model_config = ConfigDict(extra="forbid", strict=True)

    password: SecretStr | None = None


class WarehouseControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation: Literal["save", "initialize", "disable"]
    configuration: dict[str, Any] | None = None
    profile_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    database_confirmation: str | None = Field(default=None, max_length=64)


@router.get("/data/warehouse")
async def research_warehouse_status(request: Request):
    hub = request.app.state.research.datahub
    if not callable(getattr(hub.warehouse, "status", None)):
        raise StoreError("当前宿主未接入可管理研究仓", "warehouse_management_unavailable", 409)
    try:
        return await hub.storage_runner.run(hub.warehouse.status)
    except MarketStoreError:
        raise StoreError("研究仓状态不可读取", "warehouse_status_unavailable", 503) from None


@router.post("/data/warehouse")
async def research_warehouse_control(body: WarehouseControl, request: Request):
    hub = request.app.state.research.datahub
    if not callable(getattr(hub.warehouse, "status", None)):
        raise StoreError("当前宿主未接入可管理研究仓", "warehouse_management_unavailable", 409)
    try:
        if body.operation == "save":
            if body.configuration is None:
                raise ValueError("configuration_required")
            return await hub.storage_runner.run(hub.warehouse.save, body.configuration)
        if body.operation == "initialize":
            return await hub.storage_runner.run(
                hub.warehouse.initialize, body.profile_id, body.database_confirmation
            )
        return await hub.storage_runner.run(hub.warehouse.disable, body.profile_id)
    except MarketStoreError as exc:
        codes = {
            "warehouse_confirmation_mismatch",
            "warehouse_credentials_unavailable",
            "warehouse_database_unavailable",
            "warehouse_database_operation_failed",
        }
        code = str(exc) if str(exc) in codes else "warehouse_operation_rejected"
        raise StoreError("研究仓操作未完成，请核对配置和明确确认的专用数据库", code, 409) from None
    except ValueError:
        raise StoreError(
            "研究仓配置字段或确认信息非法", "warehouse_configuration_invalid", 422
        ) from None


class MigrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_ids: list[str] = Field(min_length=1, max_length=7)
    confirm: Literal[True]


class SkillAdmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    native_name: str | None = Field(
        default=None, min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9_-]*$"
    )
    loaded: bool = False
    tool_name: str | None = Field(
        default=None, min_length=1, max_length=300, pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$"
    )


class QualityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
    operation: Literal["check"] = "check"


class NativeSearchActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=241)
    title: Literal["web_search", "datahub_search_web", "datahub_search_research"]
    status: Literal["completed"]
    detail: str = Field(max_length=16000)


class SourceReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
    call_id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{1,241}$")
    operation: Literal["list", "read"]
    source_id: str | None = Field(default=None, pattern=r"^web:[a-f0-9]{24}$")
    search_activities: list[NativeSearchActivity] = Field(default_factory=list, max_length=16)


class SourceCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
    call_id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{1,241}$")


def _credential_error(exc: CredentialStoreError):
    code = str(exc)
    if code == "credential_store_unavailable":
        status = 503
    elif code in {
        "configuration_not_supported",
        "migration_selection_invalid",
        "migration_source_invalid",
    }:
        status = 422
    else:
        status = 409
    return JSONResponse(
        {"error": {"code": code, "message": "本机凭据库或连接配置不可用"}},
        status_code=status,
    )


@router.get("/data/catalog")
def catalog(request: Request):
    return request.app.state.research.datahub.catalog()


@router.get("/data/connections")
def connections(request: Request):
    return request.app.state.research.datahub.connection_center()


@router.get("/data/connections/migration-preview")
def migration_preview(request: Request):
    try:
        return request.app.state.research.datahub.connections.migration_preview()
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.post("/data/connections/migrations")
def apply_migration(body: MigrationRequest, request: Request):
    try:
        return request.app.state.research.datahub.connections.apply_migration(body.source_ids)
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.get("/data/sources/{source_id}/configuration")
def source_configuration(source_id: str, request: Request):
    try:
        hub = request.app.state.research.datahub
        result = hub.connections.source_status(source_id)
        check = hub.authorization_checks.get(source_id)
        if check and check["configuration_digest"] == hub.source_configuration_digest(source_id):
            result["authorization_check"] = check["result"]
        return result
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.post("/data/sources/{source_id}/configuration/verify")
async def verify_source_authorization(source_id: str, request: Request):
    import httpx

    from .providers import ProviderError
    from .providers_external import verify_quantapi_authorization

    if source_id != "ext_ths" or request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError(
            "只允许显式验证官方iFinD HTTP授权", "authorization_check_not_admitted", 403
        )
    hub = request.app.state.research.datahub
    before = hub.source_configuration_digest(source_id)
    try:
        result = await verify_quantapi_authorization(hub.connections, transport=hub.transport)
    except (ProviderError, httpx.HTTPError, TimeoutError):
        raise StoreError(
            "HTTP授权未验证，请核对现有refresh_token和账号权限；未更新或轮换token",
            "source_authorization_unverified",
            409,
        ) from None
    if before != hub.source_configuration_digest(source_id):
        raise StoreError("验证期间凭据配置发生变化", "data_source_authorization_changed", 409)
    hub.authorization_checks[source_id] = {"configuration_digest": before, "result": result}
    return result


@router.put("/data/sources/{source_id}/configuration")
def save_source_configuration(body: dict[str, Any], source_id: str, request: Request):
    store = request.app.state.research.datahub.connections
    try:
        if canonical_source_id(source_id) == "mysql":
            update = MySQLConfigurationUpdate.model_validate(body)
            password = update.password.get_secret_value() if update.password is not None else None
            configuration = MySQLConfiguration.model_validate(
                update.model_dump(exclude={"password"})
            )
            return store.save(configuration, password=password)
        return store.save_source(source_id, body)
    except ValidationError:
        return JSONResponse(
            {"error": {"code": "invalid_configuration", "message": "连接配置字段非法"}},
            status_code=422,
        )
    except ValueError:
        return JSONResponse(
            {"error": {"code": "invalid_configuration", "message": "连接配置字段非法"}},
            status_code=422,
        )
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.delete("/data/sources/{source_id}/configuration")
def delete_source_configuration(source_id: str, request: Request):
    try:
        return request.app.state.research.datahub.connections.delete_source(source_id)
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.get("/data/capabilities/{capability_id}")
def capability_detail(capability_id: str, request: Request):
    detail = request.app.state.research.datahub.catalog_capability(capability_id)
    if detail is None:
        raise StoreError("数据能力不存在")
    return detail


@router.get("/data/sources/{source_id}")
def source_detail(source_id: str, request: Request):
    detail = request.app.state.research.datahub.catalog_source(source_id)
    if detail is None:
        raise StoreError("数据来源不存在")
    return detail


@router.post("/data/sources/{source_id}/probes", status_code=202)
async def start_probe(
    source_id: str,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return request.app.state.research.datahub.start_probe(source_id, idempotency_key)


@router.get("/data/probes/{probe_id}")
async def probe(probe_id: str, request: Request):
    return request.app.state.research.datahub.probe(probe_id)


@router.get("/sessions/{sid}/datasets")
async def datasets(sid: str, request: Request):
    return {"items": request.app.state.research.datahub.summaries(sid)}


@router.get("/sessions/{sid}/datasets/{did}")
async def detail(sid: str, did: str, request: Request):
    return request.app.state.research.datahub.detail(sid, did)


@router.get("/sessions/{sid}/datasets/{did}/rows")
async def rows(
    sid: str,
    did: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    return request.app.state.research.datahub.rows(sid, did, offset, limit)


@router.get("/sessions/{sid}/datasets/{did}/files/{name}")
async def download(
    sid: str, did: str, name: Literal["rows.csv", "rows.json", "manifest.json"], request: Request
):
    content = request.app.state.research.datahub.snapshots.read(sid, did, name)
    return Response(
        content,
        media_type="text/csv" if name.endswith(".csv") else "application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/internal/data/business-query")
async def business_query(body: InternalBusinessQuery, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    try:
        result = await service.datahub.query(body.session_id, body.call_id, body.query)
        service.notify()
        return result
    except asyncio.CancelledError:
        return JSONResponse({"status": "cancelled"}, status_code=409)


@router.post("/internal/data/skill-preflight")
async def skill_preflight(body: SkillAdmissionRequest, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    async with service.lock:
        return service.native_admission(
            body.session_id, body.native_name, body.tool_name, loaded=body.loaded
        )


@router.post("/internal/data/research-quality")
async def research_quality(body: QualityCheckRequest, request: Request):
    from ..research_quality_service import check_quality

    service = request.app.state.research
    await service.ensure_owned()
    return await check_quality(service, body.session_id)


@router.post("/internal/data/research-source")
async def research_source(body: SourceReadRequest, request: Request):
    from ..research_web_sources import execute_source

    service = request.app.state.research
    await service.ensure_owned()
    return await execute_source(
        service,
        body.session_id,
        body.call_id,
        body.operation,
        body.source_id,
        [activity.model_dump() for activity in body.search_activities],
    )


@router.post("/internal/data/research-source/cancel")
async def research_source_cancel(body: SourceCancelRequest, request: Request):
    from ..research_web_sources import cancel_source

    return cancel_source(request.app.state.research, body.session_id, body.call_id)


@router.post("/internal/data/cancel")
async def cancel(body: InternalCancel, request: Request):
    return await request.app.state.research.datahub.cancel(body.session_id, body.call_id)


@router.get("/internal/data/model-connection")
async def model_connection(request: Request):
    """Instance-private public facts; credentials never cross this HTTP channel."""
    service = request.app.state.research
    await service.ensure_owned()
    # The detached synchronous projection must not hold the mutation lock:
    # its owner can be waiting for a native metadata callback through this API.
    return {"connection": service.compatible_connection()}
