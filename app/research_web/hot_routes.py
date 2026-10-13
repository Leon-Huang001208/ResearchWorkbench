"""Same-origin Hot projections and explicit controls; credentials remain Host-owned."""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from core.observability import get_logger

from .hot_service import HotWebError
from .store import StoreError

log = get_logger(__name__)

router = APIRouter(prefix="/api/research/hot")
private_router = APIRouter(prefix="/api/research/internal/data")
UUID_PATTERN = r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$"


@private_router.post("/hot-model")
async def private_model(request: Request):
    """Native-only model accounting; browser action headers never authorize this route."""
    research = request.app.state.research
    if not research.datahub.authenticate(request.headers.get("X-Research-Data-Key")):
        log.warning("hot_model_private_denied")
        raise HotWebError("hot_model_private_denied", "仅可信原生模型插件可调用。", 403)
    await research.ensure_owned()
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 1114112:
            raise HotWebError("hot_model_request_limit", "研究回执超出范围。", 413)
        raw.extend(chunk)
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {"operation", "params"} or not isinstance(value["params"], dict):
            raise ValueError()
        operation, params = value["operation"], value["params"]
        if operation not in {"binding", "reserve", "dispatch", "unknown", "cancel", "receipt"}:
            raise ValueError()
        sid = str(UUID(params["sessionId"]))
        row = research.store.session(sid)
        origin = row.get("hot_origin")
        if row.get("purpose") != "hot_research" or not isinstance(origin, dict):
            raise ValueError()
        run_id = origin["runId"]
        if operation == "binding":
            if set(params) != {"sessionId"}:
                raise ValueError()
        elif params.get("runId") != run_id or params["sessionId"] != sid:
            raise ValueError()
    except (ValueError, KeyError, TypeError, StoreError):
        log.warning("hot_model_binding_denied")
        raise HotWebError("hot_model_binding_denied", "研究会话与运行归属不一致。", 403) from None
    hot = request.app.state.hot
    run = await hot.call("research_run", run_id)
    if run["sessionId"] != sid or run["instanceId"] != origin.get("instanceId") or run["evidenceManifestHash"] != origin.get("manifestHash"):
        raise HotWebError("hot_model_binding_denied", "研究运行归属不一致。", 403)
    if operation == "binding":
        log.info("hot_model_binding_confirmed")
        return {"runId": run_id, "sessionId": sid}
    return await hot.call("research_model", operation, params)


class ChannelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channelId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    expectedVersion: int = Field(ge=0, le=1000000, strict=True)
    config: dict
    requestId: str = Field(pattern=UUID_PATTERN)


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)
    change: dict
    requestId: str = Field(pattern=UUID_PATTERN)


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "stop", "restart"]


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    expectedRevision: str = Field(pattern=r"^\d{1,18}$")
    enabled: bool | None = Field(default=None, strict=True)
    frequencySeconds: int | None = Field(default=None, ge=0, le=86400, strict=True)
    requestId: str = Field(pattern=UUID_PATTERN)


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    briefId: str = Field(pattern=UUID_PATTERN)
    expectedVersion: int = Field(ge=0, lt=1000000, strict=True)
    eventIds: list[Annotated[str, Field(pattern=UUID_PATTERN, strict=True)]] = Field(min_length=1, max_length=20)
    channelId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    cutoff: str = Field(min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    from_: str | None = Field(default=None, alias="from", min_length=1, max_length=100)
    to: str | None = Field(default=None, min_length=1, max_length=100)
    requestId: str = Field(pattern=UUID_PATTERN)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runId: str = Field(pattern=UUID_PATTERN)
    briefId: str = Field(pattern=UUID_PATTERN)
    version: int = Field(ge=1, le=1000000, strict=True)
    materialIds: list[Annotated[str, Field(pattern=UUID_PATTERN, strict=True)]] = Field(min_length=1, max_length=20)
    targetMode: Literal["fingpt", "claw"]
    requestId: str = Field(pattern=UUID_PATTERN)


class ResearchExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=6000, strict=True)
    formats: list[Literal["md", "docx"]] = Field(default_factory=lambda: ["md"], min_length=1, max_length=2)


@router.post("/research-runs/{run_id}/execute")
async def execute_research(run_id: str, request: Request):
    from .hot_handoff import execute_hot_handoff
    value = await body(request, ResearchExecutionRequest)
    if not re.fullmatch(UUID_PATTERN, run_id):
        raise HotWebError("hot_research_run_invalid", "运行标识不正确。", 400)
    return await execute_hot_handoff(request.app.state.research, request.app.state.hot, run_id, value.question, value.formats)


async def body(request: Request, model=None):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise HotWebError("hot_user_action_required", "请通过明确的用户操作提交。", 403)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HotWebError("hot_json_required", "请求需要 JSON。", 415)
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > 65536:
            raise HotWebError("hot_request_limit", "请求过大。", 413)
        chunks.extend(chunk)
    try:
        value = json.loads(chunks)
        if not isinstance(value, dict):
            raise ValueError()
        return model.model_validate(value) if model else value
    except (ValueError, ValidationError):
        raise HotWebError("hot_request_invalid", "请求格式不正确。", 400) from None


def query(request: Request, allowed: set[str], integer_fields: set[str] = frozenset()):
    values = dict(request.query_params)
    if set(values) - allowed or any(len(value) > 200 for value in values.values()):
        raise HotWebError("hot_query_invalid", "查询参数不正确。", 400)
    for field in integer_fields & values.keys():
        if not values[field].isascii() or not values[field].isdigit():
            raise HotWebError("hot_query_invalid", "查询范围不正确。", 400)
        values[field] = int(values[field])
    return values


@router.get("/status")
async def status(request: Request):
    return await request.app.state.hot.call("status")


@router.get("/configuration")
async def configuration(request: Request):
    return await request.app.state.hot.call("configuration")


@router.put("/configuration")
async def configure(request: Request):
    return await request.app.state.hot.call("configure", await body(request))


@router.post("/lifecycle")
async def lifecycle(request: Request):
    value = await body(request, LifecycleRequest)
    return await request.app.state.hot.call(value.action)


@router.get("/channels")
async def channels(request: Request):
    params = query(request, {"cutoff"})
    return await request.app.state.hot.call("channels", params.get("cutoff"))


@router.post("/research/handoffs")
async def research_handoff(request: Request):
    from .hot_handoff import prepare_hot_handoff
    value = await body(request, ResearchRequest)
    return await prepare_hot_handoff(request.app.state.research, request.app.state.hot,
                                     value.model_dump(exclude={"requestId"}), value.requestId)


@router.get("/research/runs/{run_id}")
async def research_run(run_id: str, request: Request):
    if not re.fullmatch(UUID_PATTERN, run_id):
        raise HotWebError("hot_research_run_invalid", "研究运行标识不正确。", 400)
    query(request, set())
    return await request.app.state.hot.call("research_run", str(UUID(run_id)))


@router.get("/events")
async def events(request: Request):
    params = query(request, {"cutoff", "channelId", "q", "topic", "institution", "asset", "from", "to", "sort", "limit", "offset", "minRelevance"}, {"limit", "offset", "minRelevance"})
    return await request.app.state.hot.call("events", params)


@router.get("/events/{event_id}")
async def detail(event_id: str, request: Request):
    params = query(request, {"cutoff", "reportOffset", "reportLimit"}, {"reportOffset", "reportLimit"})
    return await request.app.state.hot.call("event_detail", event_id, params.get("cutoff"), params.get("reportOffset", 0), params.get("reportLimit", 20))


@router.get("/sources")
async def sources(request: Request):
    query(request, set())
    return {"items": await request.app.state.hot.call("sources")}


@router.get("/briefs")
async def briefs(request: Request):
    return await request.app.state.hot.call("briefs", query(request, {"cutoff", "limit", "offset"}, {"limit", "offset"}))


@router.post("/briefs")
async def create_brief(request: Request):
    value = await body(request, BriefRequest)
    request_id = str(UUID(value.requestId))
    params = value.model_dump(by_alias=True, exclude_none=True, exclude={"requestId"})
    return await request.app.state.hot.call("create_brief", params, request_id, request_id=request_id)


@router.get("/briefs/{brief_id}")
async def brief_detail(brief_id: str, request: Request):
    params = query(request, {"version"}, {"version"})
    return await request.app.state.hot.call("brief_detail", brief_id, params.get("version"))


@router.get("/briefs/{brief_id}/markdown")
async def brief_markdown(brief_id: str, request: Request):
    params = query(request, {"version"}, {"version"})
    result = await request.app.state.hot.call("brief_export", brief_id, params.get("version"))
    return Response(result["text"], media_type="text/markdown", headers={
        "Content-Disposition": f'attachment; filename="hot-brief-{result["briefId"]}-v{result["version"]}.md"',
        "Cache-Control": "no-store", "X-Hot-Content-Hash": result["contentHash"],
    })


@router.get("/briefs/{brief_id}/docx")
async def brief_docx(brief_id: str, request: Request):
    params = query(request, {"version"}, {"version"})
    result = await request.app.state.hot.call("brief_docx", brief_id, params.get("version"))
    return Response(result["data"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={
        "Content-Disposition": f'attachment; filename="hot-brief-{result["briefId"]}-v{result["version"]}.docx"',
        "Cache-Control": "no-store", "X-Hot-Content-Hash": result["contentHash"], "X-Hot-Artifact-Hash": result["artifactHash"],
    })


@router.post("/channels/configure")
async def configure_channel(request: Request):
    value = await body(request, ChannelRequest)
    request_id = str(UUID(value.requestId))
    return await request.app.state.hot.call("configure_channel", value.channelId, value.expectedVersion, value.config, request_id, request_id=request_id)


@router.post("/events/correct")
async def correct(request: Request):
    value = await body(request, CorrectionRequest)
    request_id = str(UUID(value.requestId))
    return await request.app.state.hot.call("correct_event", value.change, value.reason, request_id, request_id=request_id)


@router.post("/sources/configure")
async def configure_source(request: Request):
    value = await body(request, SourceRequest)
    request_id = str(UUID(value.requestId))
    return await request.app.state.hot.call("configure_source", value.sourceId, value.expectedRevision, value.enabled, value.frequencySeconds, request_id, request_id=request_id)
