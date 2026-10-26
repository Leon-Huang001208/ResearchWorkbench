"""Current-user discovery reading and explicit research/tracking actions."""

from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from ..store import StoreError
from .models import UUID_PATTERN, Horizon, Prepare
from .tracking import TrackSave

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/discovery", tags=["discovery"])
Identifier = Annotated[str, Path(pattern=UUID_PATTERN)]
TrackIdentifier = Annotated[str, Path(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")]


class Execute(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(pattern=UUID_PATTERN)


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)


def _research(request):
    # The authenticated gateway selects the per-user backend. No owner/upstream
    # identity or filesystem path is ever selected from a request body.
    return request.app.state.research


def _action(request):
    if request.headers.get("X-Research-User-Action") != "?1":
        log.warning("discovery_explicit_action_missing")
        raise StoreError("此操作需要明确用户动作", "discovery_user_action_required", 403)


@router.get("/feed")
async def feed(request: Request, horizon: Horizon = "medium", refresh: bool = Query(False)):
    return await _research(request).discovery.feed(horizon, refresh=refresh)


@router.post("/prepare")
async def prepare(body: Prepare, request: Request):
    _action(request)
    return await _research(request).discovery.prepare(body)


@router.get("/selection")
async def selection(
    request: Request,
    feed_id: Annotated[str, Query(pattern=UUID_PATTERN)],
    theme_id: Annotated[str, Query(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")],
    horizon: Horizon = "medium",
):
    """Review current archived detail before freezing a compact-list selection."""
    return await _research(request).discovery.selection_preview(feed_id, theme_id, horizon)


@router.get("/association")
async def association(
    request: Request,
    feed_id: Annotated[str, Query(pattern=UUID_PATTERN)],
    news_id: Annotated[str, Query(pattern=r"^news-[a-f0-9]{48}$")],
    event_id: Annotated[str, Query(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")],
    horizon: Horizon = "medium",
):
    """Only inspect an event already present in this user's exact feed."""
    return await _research(request).discovery.associate(feed_id, news_id, event_id, horizon)


@router.get("/handoffs")
async def handoffs(request: Request):
    return _research(request).discovery.list_handoffs()


@router.get("/requests/{request_id}")
async def request_state(request_id: Identifier, request: Request):
    # A lost prepare reply remains queryable without another create or send.
    handoff_id = str(uuid5(UUID(request_id), "rwb-discovery-handoff"))
    return await _research(request).discovery.get_handoff(handoff_id)


@router.get("/handoffs/{handoff_id}")
async def handoff(handoff_id: Identifier, request: Request):
    return await _research(request).discovery.get_handoff(handoff_id)


@router.post("/handoffs/{handoff_id}/execute")
async def execute(handoff_id: Identifier, body: Execute, request: Request):
    _action(request)
    return await _research(request).discovery.execute(handoff_id, body.request_id)


@router.get("/tracks")
async def tracks(request: Request):
    research = _research(request)
    result = research.discovery_tracking.list()
    scheduler = research.automations.scheduler
    return {
        **result,
        "available": research.discovery_tracking_allowed(),
        "scheduler_state": "running" if getattr(scheduler, "running", False) else "not_started",
    }


@router.post("/tracks")
async def save_track(body: TrackSave, request: Request):
    _action(request)
    research = _research(request)
    if not research.discovery_tracking_allowed():
        raise StoreError("持续跟踪已由宿主关闭", "discovery_tracking_disabled", 403)
    return await research.discovery_tracking.save(body.model_dump(mode="json"))


@router.post("/tracks/{track_id}/enable")
async def enable_track(track_id: TrackIdentifier, body: Version, request: Request):
    _action(request)
    research = _research(request)
    # Verify ownership/version before starting even the existing scheduler.
    _row, automation = research.discovery_tracking._owned(track_id)
    research.discovery_tracking._version(automation, body.expected_version)
    await research.ensure_discovery_scheduler()
    return research.discovery_tracking.enable(track_id, body.expected_version)


@router.post("/tracks/{track_id}/disable")
async def disable_track(track_id: TrackIdentifier, body: Version, request: Request):
    _action(request)
    return _research(request).discovery_tracking.disable(track_id, body.expected_version)
