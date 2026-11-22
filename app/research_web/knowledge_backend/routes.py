"""Authenticated settings and explicit evidence writes, separate from read-only MCP."""

from fastapi import APIRouter, Request, Response
from pydantic import TypeAdapter, ValidationError

from ..delivery import FINAL
from ..store import StoreError
from . import models
from .storage import fail

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
        return await service(request).current_query(
            value,
            host=request.app.state.research,
            caller_session_id=request.headers.get("X-Research-Native-Session"),
        )
    if request.url.path.startswith(INTERNAL):
        # Native tools select a session, never a model-supplied approval ID.
        raise StoreError("报告检索需要已批准的范围", "knowledge_scope_required", 403)
    return await service(request).search(value)


@router.post("/api/research/knowledge/read")
@router.post("/api/research/internal/data/knowledge-read")
async def read(request: Request):
    value = await body(request, models.CurrentRead | models.Read)
    if isinstance(value, models.CurrentRead):
        return await service(request).current_read(
            value,
            host=request.app.state.research,
            caller_session_id=request.headers.get("X-Research-Native-Session"),
        )
    if request.url.path.startswith(INTERNAL):
        raise StoreError("报告读取需要已批准的范围", "knowledge_scope_required", 403)
    return await service(request).read(value)


def current_grant(host, sid):
    row = host.store.session(sid)
    receipt = host.store.data["receipts"].get(f"{sid}:{row.get('delivery_key')}", {})
    scope = receipt.get("knowledge_scope_id")
    delivery = receipt.get("delivery", {})
    if (
        row.get("knowledge_single_turn") is not True
        or not scope
        or receipt.get("status") not in {"pending", "accepted"}
        or delivery.get("status") in FINAL
        or delivery.get("cancel_request")
        or host.connected != {"mux", "host"}
    ):
        fail("knowledge_run_not_authorized", 403)
    return scope, delivery.get("task_id")


def grant_snapshot(host, sid):
    scope, request_id = current_grant(host, sid)
    row = host.store.session(sid)
    receipt = host.store.data["receipts"].get(f"{sid}:{row.get('delivery_key')}", {})
    request_digest, payload_digest = (
        receipt.get("knowledge_request_digest"),
        receipt.get("digest"),
    )
    if not request_id or not request_digest or not payload_digest:
        fail("knowledge_run_not_authorized", 403)
    return scope, request_id, request_digest, payload_digest


async def active_scope(host, sid):
    await host.ensure_owned()
    grant = grant_snapshot(host, sid)
    entries = await host.client.history(sid)
    native = await host.client.rpc("session.list", {})
    items = native.get("items")
    parents = (
        [item for item in items if isinstance(item, dict) and item.get("sessionId") == sid]
        if isinstance(items, list)
        else []
    )
    if (
        native.get("diagnostics")
        or len(parents) != 1
        or parents[0].get("running") is not True
        or parents[0].get("parentSessionId")
    ):
        fail("knowledge_run_not_active", 403)
    if grant_snapshot(host, sid) != grant:
        fail("knowledge_run_not_authorized", 403)
    scope, request_id, _, _ = grant
    events = [entry["event"] for entry in entries]
    boundaries = [event for event in events if event["type"] in {"turn/start", "turn/end"}]
    messages = [event for event in events if event["type"] == "user/message"]
    if (
        len(boundaries) != 1
        or boundaries[0]["type"] != "turn/start"
        or boundaries[0]["data"].get("turn") != 1
        or len(messages) != 1
        or not request_id
        or (messages[0]["data"].get("source") or {}).get("rpcId") != request_id
    ):
        fail("knowledge_native_turn_unverified", 403)
    return scope


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
