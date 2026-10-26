"""Asset workspace HTTP contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

router = APIRouter(prefix="/api/research")

AssetType = Literal["stock", "etf", "index", "fund", "theme"]
AssetBlock = Literal[
    "overview",
    "history",
    "valuation",
    "financials",
    "activity",
    "margin",
    "holders",
    "announcements",
    "news",
    "research",
    "industry",
    "holder_details",
    "events",
]
SourceId = Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
RangeBlock = Literal["history", "activity", "margin"]


class SectionRange(BaseModel):
    """An explicit, complete calendar interval; provider limits still apply."""

    model_config = ConfigDict(extra="forbid")

    start_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @model_validator(mode="after")
    def validate_interval(self) -> SectionRange:
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        if start > end:
            raise ValueError("start_date must not follow end_date")
        return self


def _default_sections() -> list[AssetBlock]:
    return ["overview", "history", "financials", "activity"]


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    asset: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    asset_type: AssetType
    source: SourceId = "auto"
    section_sources: dict[AssetBlock, SourceId] = Field(default_factory=dict)
    section_ranges: dict[RangeBlock, SectionRange] = Field(default_factory=dict)
    sections: list[AssetBlock] = Field(
        default_factory=_default_sections,
        min_length=1,
        max_length=13,
    )
    start_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    frequency: Literal["daily", "weekly", "monthly"] = "daily"
    adjustment: Literal["none", "qfq", "hfq"] = "qfq"


class HistoryJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["recent", "older", "all"]
    adjustment: Literal["none", "qfq", "hfq"]
    source: Literal["auto", "tinysoft", "wind", "akshare", "baostock"] = "tinysoft"
    include_chip_inputs: bool = Field(default=False, strict=True)
    as_of: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    retry_of: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$"
    )

    @model_validator(mode="after")
    def valid_cutoff(self):
        if self.include_chip_inputs and self.source != "tinysoft":
            raise ValueError("verified chip turnover inputs currently require explicit Tinysoft")
        if self.source != "tinysoft" and (self.scope != "recent" or self.adjustment != "none"):
            raise ValueError("non-Tinysoft history requires recent unadjusted daily bars")
        if self.as_of is not None:
            date.fromisoformat(self.as_of)
            if self.scope == "older":
                raise ValueError("older history retains the existing adjustment anchor")
        return self


class BlockLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceId | None = None
    refresh: bool = False
    start_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @model_validator(mode="after")
    def complete_interval(self):
        if self.start_date is not None or self.end_date is not None:
            if self.start_date is None or self.end_date is None:
                raise ValueError("区间必须同时提供开始和结束日期")
            SectionRange(start_date=self.start_date, end_date=self.end_date)
        return self


class ChartPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panels: list[str] = Field(max_length=15)
    chip_settings: dict | None = None
    favorites: list[str] | None = Field(default=None, max_length=15)
    indicator_settings: dict | None = None

    @model_validator(mode="after")
    def unique_panels(self):
        from .asset_indicator_preferences import (
            normalize_indicator_settings,
            validate_indicator_ids,
        )

        self.panels = validate_indicator_ids(self.panels)
        if self.favorites is not None:
            self.favorites = validate_indicator_ids(self.favorites, name="favorites")
        if self.indicator_settings is not None:
            self.indicator_settings = normalize_indicator_settings(self.indicator_settings)
        if self.chip_settings is not None:
            from .asset_chip_inputs import normalize_chip_settings

            self.chip_settings = normalize_chip_settings(self.chip_settings)
        if len(set(self.panels)) != len(self.panels):
            raise ValueError("panels must be unique")
        return self


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


@router.get("/assets/search")
async def search_assets(
    request: Request,
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
):
    return request.app.state.research.asset_workspace.directory.search(q, limit)


@router.get("/assets/observations")
async def list_observations(request: Request):
    return {"items": request.app.state.research.asset_workspace.list_observations()}


@router.get("/assets/observations/{observation_id}")
async def observation(observation_id: str, request: Request):
    return request.app.state.research.asset_workspace.observation(observation_id)


class IntradayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh: bool = Field(default=False, strict=True)


class MinuteKRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cycle: Literal["1m", "5m", "15m", "30m", "60m", "120m"]
    adjustment: Literal["none", "qfq", "hfq"] = "none"
    refresh: bool = Field(default=False, strict=True)


@router.post("/assets/observations/{observation_id}/minute-bars")
async def minute_bars(observation_id: str, body: MinuteKRequest, request: Request):
    from .datahub.providers import ProviderError
    from .store import StoreError

    try:
        return await request.app.state.research.asset_workspace.minute_k.load(
            observation_id, body.cycle, body.adjustment, body.refresh
        )
    except (ValueError, ProviderError) as exc:
        code = str(exc)
        if not code.startswith("minute_") or len(code) > 64:
            code = "minute_data_invalid"
        raise StoreError("分钟K数据或复权口径校验未通过，原图与快照已保留。", code, 422) from exc


@router.post("/assets/observations/{observation_id}/intraday")
async def intraday(observation_id: str, body: IntradayRequest, request: Request):
    from .datahub.providers import ProviderError
    from .store import StoreError

    try:
        return await request.app.state.research.asset_workspace.intraday.load(
            observation_id, refresh=body.refresh
        )
    except (ValueError, ProviderError) as exc:
        # Only stable, bounded validation codes are exposed; no provider text.
        code = str(exc)
        if not code.startswith("intraday_") or len(code) > 64:
            code = "intraday_data_invalid"
        message = {
            "intraday_source_incomplete": "分钟来源未完整返回，请重试或检查来源权限。",
            "intraday_units_unverified": "分钟数据单位尚未核实，暂不绘制。",
            "intraday_field_definition_changed": "厂商分钟字段定义已变化，须重新核验。",
            "intraday_vendor_permission_denied": "天软未授权此分钟数据，请检查数据权限。",
            "intraday_vendor_auth_failed": "天软认证失败，请检查现有连接配置。",
            "intraday_vendor_rate_limited": "天软请求频率受限，请稍后重试。",
            "intraday_vendor_unreachable": "天软暂时无法连接，请稍后重试。",
            "intraday_stock_required": "当前分时仅支持已核实的沪深股票。",
            "intraday_data_invalid": "分时数据校验未通过，请查看来源口径后重试。",
        }.get(code, "分时数据校验未通过，已保留原快照。")
        raise StoreError(message, code, 422) from exc


@router.post("/assets/observations/{observation_id}/history-jobs", status_code=202)
async def create_history_job(
    observation_id: str,
    body: HistoryJobRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return await request.app.state.research.asset_workspace.history_jobs.create(
        observation_id, body, idempotency_key
    )


@router.get("/assets/observations/{observation_id}/history-jobs")
async def list_history_jobs(observation_id: str, request: Request):
    return {"items": request.app.state.research.asset_workspace.history_jobs.list(observation_id)}


@router.get("/assets/observations/{observation_id}/history-jobs/{job_id}")
async def get_history_job(observation_id: str, job_id: str, request: Request):
    return request.app.state.research.asset_workspace.history_jobs.get(observation_id, job_id)


@router.post("/assets/observations/{observation_id}/history-jobs/{job_id}/cancel", status_code=202)
async def cancel_history_job(observation_id: str, job_id: str, request: Request):
    return await request.app.state.research.asset_workspace.history_jobs.cancel(
        observation_id, job_id
    )


@router.get("/assets/chart-preferences")
async def get_chart_preferences(request: Request):
    return request.app.state.research.asset_workspace.chart_preferences()


@router.put("/assets/chart-preferences")
async def put_chart_preferences(body: ChartPreferencesRequest, request: Request):
    return request.app.state.research.asset_workspace.set_chart_preferences(
        body.panels,
        body.chip_settings,
        favorites=body.favorites,
        indicator_settings=body.indicator_settings,
    )


@router.post("/assets/observations/{observation_id}/blocks/{block}/refresh", status_code=202)
async def refresh_observation_block(
    observation_id: str,
    block: AssetBlock,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return await request.app.state.research.asset_workspace.refresh_block(
        observation_id, block, idempotency_key
    )


@router.post("/assets/observations/{observation_id}/blocks/{block}/load", status_code=202)
async def load_observation_block(
    observation_id: str,
    block: AssetBlock,
    body: BlockLoadRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return await request.app.state.research.asset_workspace.load_block(
        observation_id, block, body, idempotency_key
    )


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
