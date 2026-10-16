"""Same-origin FinGPT browser ingress; no provider credential in responses."""

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..store import StoreError
from .service import ENGINE

router = APIRouter(prefix="/api/research/fingpt", tags=["fingpt"])


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="新研究", min_length=1, max_length=120)
    project_id: str = "default"
    source_session_id: str | None = None
    source_attachment_ids: list[str] = Field(default_factory=list, max_length=20)


class Ask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    msg: str = Field(min_length=1, max_length=4000)
    mode: Literal["quick", "deep", "agent"] = "quick"
    tier: Literal["lite", "ultra", "frontier", "kimi"] = "lite"
    attachment_ids: list[str] = Field(default_factory=list, max_length=20)


def engine(request):
    return request.app.state.research.fingpt


@router.get("/tiers")
async def tiers(request: Request):
    return await engine(request).tiers()


@router.post("/sessions", status_code=201)
async def create(body: Create, request: Request):
    history = []
    if body.source_session_id:
        source = request.app.state.research.store.session(body.source_session_id)
        if source.get("project_id", "default") != body.project_id:
            raise StoreError("继续研究必须保留原项目", "reference_project_mismatch", 409)
        for fid in body.source_attachment_ids:
            request.app.state.research.store.file_path(body.source_session_id, fid)
        if source["mode"] != "fingpt":
            raise StoreError("仅支持继续当前 FinGPT 会话")
        detail = await request.app.state.research.detail(body.source_session_id)
        history = [{"role": m["role"], "content": m["text"]} for m in detail["messages"][-6:]]
    result = engine(request).create(body.title, body.project_id, body.source_session_id, history)
    request.app.state.research.store.session(result["id"])[
        "context_source_file_ids"
    ] = body.source_attachment_ids
    request.app.state.research.store.save()
    return result


@router.post("/sessions/{sid}/ask", status_code=202)
async def ask(
    sid: str,
    body: Ask,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if not body.msg.strip():
        raise StoreError("问题不能为空")
    rid = await engine(request).submit(sid, body, idempotency_key)
    return {"session_id": sid, "round_id": rid, "engine": ENGINE}


@router.get("/sessions/{sid}/rounds/{rid}/events")
async def events(sid: str, rid: str, request: Request, after: int = 0):
    qa = engine(request)
    if not qa.owns(sid):
        raise StoreError("不是新版 FinGPT 会话")
    if not any(r["id"] == rid for r in qa._read(sid)["rounds"]):
        raise StoreError("回答不存在", "round_not_found", 404)

    async def stream():
        changed = asyncio.Event()
        qa.queues.setdefault(sid, set()).add(changed)
        last = max(0, after)
        try:
            while not await request.is_disconnected():
                changed.clear()
                state = qa._read(sid)
                item = next(r for r in state["rounds"] if r["id"] == rid)
                for event in item["events"]:
                    if event["seq"] <= last:
                        continue
                    last = event["seq"]
                    yield f"id: {last}\nevent: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                if item["status"] != "running":
                    yield f"event: round_end\ndata: {json.dumps({'status': item['status']})}\n\n"
                    return
                try:
                    await asyncio.wait_for(changed.wait(), 15)
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            qa.queues[sid].discard(changed)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
