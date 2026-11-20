"""Authenticated settings and explicit evidence writes, separate from read-only MCP."""

from fastapi import APIRouter, Request, Response
from pydantic import TypeAdapter, ValidationError

from ..store import StoreError
from . import models

router = APIRouter(tags=["knowledge"])
PUBLIC = "/api/research/knowledge"
INTERNAL = "/api/research/internal/data"


def service(request):
    return request.app.state.research.knowledge


async def body(request, model, *, action=False):
    if action and request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("需要明确用户操作", "knowledge_user_action_required", 403)
    length = request.headers.get("content-length", "")
    if request.headers.get("transfer-encoding") or not length.isdecimal():
        raise StoreError("请求需要明确长度", "knowledge_request_length_required", 411)
    if int(length) > 65536:
        raise StoreError("资料请求超出上限", "knowledge_request_too_large", 413)
    raw = await request.body()
    if len(raw) > 65536:
        raise StoreError("资料请求超出上限", "knowledge_request_too_large", 413)
    try:
        return TypeAdapter(model).validate_json(raw)
    except (ValidationError, ValueError):
        # FastAPI's default validation detail can echo secret input values.
        raise StoreError("资料请求格式无效", "knowledge_request_invalid", 422) from None


@router.get("/api/research/knowledge")
async def status(request: Request):
    return service(request).status()


@router.post("/api/research/knowledge/binding")
async def bind(request: Request):
    value = await body(request, models.Binding, action=True)
    return await service(request).bind(value.token.get_secret_value(), value.workspace_id)


@router.post("/api/research/knowledge/login")
async def login(request: Request):
    value = await body(request, models.Login, action=True)
    result = await service(request).login(value.email, value.password.get_secret_value())
    await request.app.state.research.start_knowledge_sync()
    return result


@router.get("/api/research/knowledge/bases")
async def bases(request: Request):
    return await service(request).bases()


@router.get("/api/research/knowledge/sync")
async def sync_status(request: Request):
    return service(request).sync_status()


@router.post("/api/research/knowledge/sync/config")
async def sync_config(request: Request):
    value = await body(request, models.SyncConfiguration, action=True)
    result = await service(request).configure_sync(value)
    await request.app.state.research.start_knowledge_sync()
    return result


@router.post("/api/research/knowledge/sync/scan")
async def sync_scan(request: Request):
    await body(request, models.Scan, action=True)
    return await service(request).scan_sync()


@router.post("/api/research/knowledge/scopes")
async def scope(request: Request):
    value = await body(request, models.Scope, action=True)
    return await service(request).create_scope(value)


@router.post("/api/research/knowledge/search")
@router.post("/api/research/internal/data/knowledge-query")
async def query(request: Request):
    value = await body(request, models.CurrentQuery | models.Search)
    if isinstance(value, models.CurrentQuery):
        return await service(request).current_query(value)
    if request.url.path.startswith(INTERNAL) and value.scope_id is None:
        raise StoreError("报告检索需要已批准的范围", "knowledge_scope_required", 403)
    return await service(request).search(value)


@router.post("/api/research/knowledge/read")
@router.post("/api/research/internal/data/knowledge-read")
async def read(request: Request):
    value = await body(request, models.CurrentRead | models.Read)
    if isinstance(value, models.CurrentRead):
        return await service(request).current_read(value)
    if request.url.path.startswith(INTERNAL) and value.scope_id is None:
        raise StoreError("报告读取需要已批准的范围", "knowledge_scope_required", 403)
    return await service(request).read(value)


@router.post("/api/research/knowledge/freeze")
async def freeze(request: Request):
    value = await body(request, models.CurrentFreeze | models.Freeze, action=True)
    if isinstance(value, models.CurrentFreeze):
        return await service(request).current_freeze(value)
    return await service(request).freeze(value)


@router.get("/api/research/knowledge/evidence/{identifier}")
async def evidence(identifier: str, request: Request):
    return service(request).store.read("evidence", identifier)


@router.get("/api/research/knowledge/evidence/{identifier}/original/{sha}")
async def original(identifier: str, sha: str, request: Request):
    return Response(
        service(request).store.original(identifier, sha),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=original.bin",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
