"""SSE realtime stream — 推送新文档/断言/事件/信号/队列状态"""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


async def event_stream(request: Request):
    """SSE 事件流，每 2 秒推送一次系统事件

    支持 Last-Event-ID 重连：客户端断线重连时自动重放丢失的事件。
    """
    last_event_id = request.headers.get("Last-Event-ID")

    # replay missed events after reconnect
    if last_event_id:
        missed = await event_bus.get_events_after(last_event_id)
        for event in missed:
            data = json.dumps(event.to_sse_dict(), ensure_ascii=False)
            yield f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data}\n\n"

    queue = await event_bus.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                data = json.dumps(event.to_sse_dict(), ensure_ascii=False)
                yield f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        await event_bus.unsubscribe(queue)


@router.get("/stream")
async def stream(request: Request):
    """GET /api/realtime/stream — Server-Sent Events 端点"""
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
