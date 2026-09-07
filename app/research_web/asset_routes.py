"""Asset workspace HTTP contracts."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/research")

AssetType = Literal["stock", "etf", "index", "fund", "theme"]
AssetBlock = Literal[
    "overview", "history", "financials", "activity", "announcements", "news", "research"
]


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    asset: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    asset_type: AssetType
    source: str = Field(default="auto", pattern=r"^[a-z0-9_]+$")
    sections: list[AssetBlock] = Field(
        default_factory=lambda: ["overview", "history", "financials", "activity"],
        min_length=1,
        max_length=7,
    )
    start_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    frequency: Literal["daily", "weekly", "monthly"] = "daily"
    adjustment: Literal["none", "qfq", "hfq"] = "qfq"


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    polling_minutes: Literal[5, 15, 60] | None = None


class WatchlistItem(BaseModel):
    asset: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    asset_type: AssetType
    name: str = Field(min_length=1, max_length=120)


class NoteCreate(BaseModel):
    asset: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    text: str = Field(min_length=1, max_length=10000)


class NotePatch(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class AlertCreate(BaseModel):
    asset: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    field: Literal["price", "change_pct", "volume"]
    operator: Literal["gt", "gte", "lt", "lte"]
    threshold: float
    cooldown_minutes: int = Field(default=60, ge=5, le=10080, strict=True)


class AlertPatch(BaseModel):
    enabled: bool | None = None
    threshold: float | None = None
    cooldown_minutes: int | None = Field(default=None, ge=5, le=10080, strict=True)


@router.post("/assets/observations", status_code=202)
async def create_observation(
    body: ObservationRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return await request.app.state.research.asset_workspace.create_observation(
        body, idempotency_key
    )


@router.get("/assets/observations")
async def list_observations(request: Request):
    return {"items": request.app.state.research.asset_workspace.list_observations()}


@router.get("/assets/observations/{observation_id}")
async def observation(observation_id: str, request: Request):
    return request.app.state.research.asset_workspace.observation(observation_id)


@router.get("/watchlists")
async def watchlists(request: Request):
    rows = list(request.app.state.research.store.data["watchlists"].values())
    rows.sort(key=lambda row: row["updated_at"], reverse=True)
    return {"items": rows}


@router.post("/watchlists", status_code=201)
async def create_watchlist(body: WatchlistCreate, request: Request):
    return request.app.state.research.asset_workspace.create_watchlist(
        body.name, body.polling_minutes
    )


@router.post("/watchlists/{watchlist_id}/items", status_code=201)
async def add_watchlist_item(watchlist_id: str, body: WatchlistItem, request: Request):
    return request.app.state.research.asset_workspace.add_watchlist_item(
        watchlist_id, body.model_dump()
    )


@router.get("/asset-notes")
async def notes(request: Request):
    rows = list(request.app.state.research.store.data["asset_notes"].values())
    rows.sort(key=lambda row: row["updated_at"], reverse=True)
    return {"items": rows}


@router.post("/asset-notes", status_code=201)
async def create_note(body: NoteCreate, request: Request):
    return request.app.state.research.asset_workspace.create_note(body.asset, body.text)


@router.patch("/asset-notes/{note_id}")
async def patch_note(note_id: str, body: NotePatch, request: Request):
    return request.app.state.research.asset_workspace.patch_note(note_id, body.text)


@router.get("/asset-alerts")
async def alerts(request: Request):
    rows = list(request.app.state.research.store.data["asset_alerts"].values())
    rows.sort(key=lambda row: row["updated_at"], reverse=True)
    return {"items": rows}


@router.post("/asset-alerts", status_code=201)
async def create_alert(body: AlertCreate, request: Request):
    return request.app.state.research.asset_workspace.create_alert(body.model_dump())


@router.patch("/asset-alerts/{alert_id}")
async def patch_alert(alert_id: str, body: AlertPatch, request: Request):
    return request.app.state.research.asset_workspace.patch_alert(
        alert_id, body.model_dump(exclude_unset=True)
    )


@router.get("/asset-notifications")
async def notifications(request: Request):
    rows = list(request.app.state.research.store.data["asset_notifications"].values())
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return {"items": rows}
