"""Read-only browser catalog; authenticated native-only query and cancel ingress."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ConfigDict, SecretStr

from ..store import StoreError
from .connections import CredentialStoreError, MySQLConfiguration
from .contracts import InternalBusinessQuery, InternalCancel

router = APIRouter(prefix="/api/research")


class MySQLConfigurationUpdate(MySQLConfiguration):
    model_config = ConfigDict(extra="forbid", strict=True)

    password: SecretStr | None = None


def _credential_error(exc: CredentialStoreError):
    code = str(exc)
    status = 503 if code == "credential_store_unavailable" else 409
    return JSONResponse(
        {"error": {"code": code, "message": "本机凭据库或连接配置不可用"}},
        status_code=status,
    )


@router.get("/data/catalog")
async def catalog(request: Request):
    return request.app.state.research.datahub.catalog()


@router.get("/data/sources/mysql/configuration")
async def mysql_configuration(request: Request):
    return request.app.state.research.datahub.connections.status()


@router.put("/data/sources/mysql/configuration")
async def save_mysql_configuration(body: MySQLConfigurationUpdate, request: Request):
    try:
        password = body.password.get_secret_value() if body.password is not None else None
        configuration = MySQLConfiguration.model_validate(body.model_dump(exclude={"password"}))
        return request.app.state.research.datahub.connections.save(configuration, password=password)
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.delete("/data/sources/mysql/configuration")
async def delete_mysql_configuration(request: Request):
    try:
        return request.app.state.research.datahub.connections.delete()
    except CredentialStoreError as exc:
        return _credential_error(exc)


@router.get("/data/capabilities/{capability_id}")
async def capability_detail(capability_id: str, request: Request):
    detail = request.app.state.research.datahub.catalog_capability(capability_id)
    if detail is None:
        raise StoreError("数据能力不存在")
    return detail


@router.get("/data/sources/{source_id}")
async def source_detail(source_id: str, request: Request):
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


@router.post("/internal/data/cancel")
async def cancel(body: InternalCancel, request: Request):
    return await request.app.state.research.datahub.cancel(body.session_id, body.call_id)
