"""Finite AI news admin requests under the existing Host authentication boundary."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .ai_news_service import FeedKind

router = APIRouter(prefix="/api/research/ai-news", tags=["ai-news"])


class ControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1, max_length=64)
    input: dict = Field(default_factory=dict)


@router.get("/status")
async def status(request: Request):
    return await request.app.state.ai_news.status()


@router.post("/control")
async def control(request: Request, body: ControlRequest):
    return await request.app.state.ai_news.control(body.action, body.input)


@router.get("/feeds/{kind}.xml")
async def feed(request: Request, kind: FeedKind):
    content = await request.app.state.ai_news.feed(kind, str(request.base_url).rstrip("/"))
    return Response(
        content,
        media_type="application/rss+xml",
        headers={
            "Content-Disposition": f'attachment; filename="ai-news-{kind}.xml"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )
