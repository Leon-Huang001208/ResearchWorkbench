"""Account Host calendar reads, short snapshots and bounded source acquisition."""

from __future__ import annotations

import asyncio
import re
import time
from collections import OrderedDict, defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, admission

from .datahub.providers_market_calendar import (
    OFFICIAL_SOURCES,
    CalendarCapture,
    CalendarEvent,
    fetch_official_schedule,
)
from .event_timeline import sources
from .market_service import MarketError

log = get_logger(__name__)
PAGE_SIZE = 20
MAX_DAYS = 31
SNAPSHOT_LIMIT = 32
SNAPSHOT_TTL = 15 * 60
SOURCE_TTL = 15 * 60
SOURCE_BACKOFF = 60
SOURCE_TIMEOUT = 20

Category = Literal["economic", "ipo", "notify", "report", "inst"]
Subtype = Literal[
    "ipo_listed",
    "ipo_subscribe",
    "ipo_lottery",
    "notify_attend",
    "notify_divide",
    "notify_suspend",
    "notify_contract",
]


class FinancialCalendarQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["summary", "events"]
    start: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    category: Category | None = None
    subtype: Subtype | None = None
    market: Literal["all", "ab", "hk", "us"] = "all"
    holding_type: Literal["all", "inc", "dec", "new", "out"] = "all"
    filter_set: Literal["all", "topAum", "topChAumPr"] = "all"
    page: int = Field(default=0, ge=0, le=149)
    snapshot_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")

    @field_validator("page", mode="before")
    @classmethod
    def check_page(cls, value: object) -> object:
        if (
            type(value) is int
            or isinstance(value, str)
            and re.fullmatch(r"0|[1-9][0-9]{0,2}", value)
        ):
            return value
        raise ValueError("页码须为十进制整数")

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        first, last = date.fromisoformat(self.start), date.fromisoformat(self.end)
        if not 0 <= (last - first).days < MAX_DAYS:
            raise ValueError("财经日历查询范围为 1 至 31 个自然日")
        if self.view == "summary":
            if self.category is not None or self.subtype is not None:
                raise ValueError("计数视图不接受事件类别或子类")
            if self.page or self.snapshot_id is not None:
                raise ValueError("计数视图不支持分页")
        elif self.category is None:
            raise ValueError("事件视图需要类别")
        if self.subtype is not None and self.subtype.partition("_")[0] != self.category:
            raise ValueError("子类不属于所选事件类别")
        if self.category != "inst" and (self.holding_type != "all" or self.filter_set != "all"):
            raise ValueError("机构持仓筛选仅用于机构持仓事件")
        if self.page:
            if self.start != self.end or self.snapshot_id is None:
                raise ValueError("后续分页需要单个日期和首次响应的快照标识")
        elif self.snapshot_id is not None:
            raise ValueError("首次分页不接受快照标识")
        return self

    def filters(self) -> tuple[str | None, ...]:
        return self.category, self.subtype, self.market, self.holding_type, self.filter_set


@dataclass(frozen=True)
class SourceState:
    capture: CalendarCapture | None = None
    status: Literal["partial", "stale", "unavailable"] = "unavailable"
    next_due: float = 0.0


@dataclass(frozen=True)
class EventSnapshot:
    start: str
    end: str
    filters: tuple[str | None, ...]
    readings: tuple[SourceState, ...]
    expires_at: float


class MarketFinancialCalendar:
    """Read only fixed public sources; snapshots never cross Host instances."""

    def __init__(
        self,
        *,
        fetcher: Callable[[str], Awaitable[CalendarCapture]] = fetch_official_schedule,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._states = dict.fromkeys(OFFICIAL_SOURCES, SourceState())
        self._snapshots: OrderedDict[str, EventSnapshot] = OrderedDict()
        self._refresh_task: asyncio.Task[None] | None = None
        self._closed = False

    @staticmethod
    def _unavailable() -> MarketError:
        return MarketError("market_calendar_closed", "财经日历服务暂不可用。", 503)

    async def _fetch(self, source_id: str) -> SourceState:
        try:
            async with asyncio.timeout(SOURCE_TIMEOUT):
                capture = await self._fetcher(source_id)
            if capture.source_id != source_id or len(capture.items) > sources.MAX_EVENTS:
                raise ValueError("market_calendar_capture_invalid")
        except Exception as exc:  # noqa: BLE001 - no supplier messages reach the product
            log.warning(
                "market_calendar_schedule_unavailable",
                source=source_id,
                error_type=type(exc).__name__,
            )
            previous = self._states[source_id].capture
            return SourceState(
                previous, "stale" if previous else "unavailable", self._clock() + SOURCE_BACKOFF
            )
        return SourceState(capture, "partial", self._clock() + SOURCE_TTL)

    async def _refresh(self, due: tuple[str, ...]) -> None:
        with admission():
            readings = await asyncio.gather(*(self._fetch(source_id) for source_id in due))
        if not self._closed:
            self._states.update(zip(due, readings, strict=True))

    def _refresh_done(self, task: asyncio.Task[None]) -> None:
        if self._refresh_task is task:
            self._refresh_task = None
        if not task.cancelled():
            error = task.exception()
            if error is not None and not isinstance(error, MaintenanceBusy):
                log.warning("market_calendar_refresh_failed", error_type=type(error).__name__)

    async def _readings(self) -> tuple[SourceState, ...]:
        now = self._clock()
        due = tuple(source for source, state in self._states.items() if now >= state.next_due)
        if due:
            task = self._refresh_task
            if task is None or task.done():
                task = asyncio.create_task(self._refresh(due))
                self._refresh_task = task
                task.add_done_callback(self._refresh_done)
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not self._closed:
                    raise
        if self._closed:
            raise self._unavailable()
        return tuple(self._states.values())

    @staticmethod
    def _event(item: CalendarEvent, capture: CalendarCapture) -> dict:
        result = {
            "id": item.id,
            "date": item.date,
            "title": item.title,
            "date_precision": "day",
            "source_id": capture.source_id,
            "source_url": sources.CATALOG[capture.source_id]["url"],
            "observed_at": capture.observed_at,
        }
        if item.end_date and item.end_date != item.date:
            result["end_date"] = item.end_date
        return result

    @staticmethod
    def _status(readings: tuple[SourceState, ...]) -> str:
        states = {state.status for state in readings}
        if not states:
            return "not_connected"
        if "stale" in states:
            return "stale"
        return "partial" if "partial" in states else "unavailable"

    def _project(
        self, query: FinancialCalendarQuery, readings: tuple[SourceState, ...], token: str | None
    ) -> dict:
        first, last = date.fromisoformat(query.start), date.fromisoformat(query.end)
        status = self._status(readings)
        grouped: dict[str, list[tuple[CalendarEvent, CalendarCapture]]] = defaultdict(list)
        for state in readings:
            if state.capture:
                for item in state.capture.items:
                    if query.start <= item.date <= query.end:
                        grouped[item.date].append((item, state.capture))
        days = []
        for offset in range((last - first).days + 1):
            day = (first + timedelta(days=offset)).isoformat()
            matched = grouped[day]
            row: dict[str, object] = {"date": day, "status": status}
            if query.view == "summary":
                row["counts"] = {
                    "economic": len(matched) or None,
                    "ipo": None,
                    "notify": None,
                    "report": None,
                }
            else:
                matched.sort(key=lambda entry: (entry[0].title, entry[0].id))
                start, end = query.page * PAGE_SIZE, (query.page + 1) * PAGE_SIZE
                row.update(
                    items=[self._event(item, capture) for item, capture in matched[start:end]],
                    total=len(matched) or None,
                    has_more=end < len(matched),
                )
            days.append(row)
        return {
            "snapshot_id": token,
            "days": days,
            "sources": [
                {
                    "id": source_id,
                    "label": sources.CATALOG[source_id]["label"],
                    "url": sources.CATALOG[source_id]["url"],
                    "observed_at": state.capture.observed_at if state.capture else None,
                    "status": state.status,
                }
                for source_id, state in zip(OFFICIAL_SOURCES, readings)
            ],
        }

    async def read(self, query: FinancialCalendarQuery) -> dict:
        if self._closed:
            raise self._unavailable()
        now = self._clock()
        for key in list(self._snapshots):
            if now >= self._snapshots[key].expires_at:
                del self._snapshots[key]
        if query.page:
            token = query.snapshot_id
            snapshot = self._snapshots.get(token) if token else None
            if (
                not snapshot
                or snapshot.filters != query.filters()
                or not snapshot.start <= query.start <= snapshot.end
            ):
                raise MarketError(
                    "market_calendar_snapshot_expired", "财经日历快照已失效，请重新加载。", 409
                )
            return self._project(query, snapshot.readings, token)

        if query.view == "events" and query.category != "economic":
            return self._project(query, (), None)

        readings = await self._readings()
        token = None
        if query.view == "events" and any(state.capture for state in readings):
            token = uuid4().hex
            self._snapshots[token] = EventSnapshot(
                query.start, query.end, query.filters(), readings, self._clock() + SNAPSHOT_TTL
            )
            while len(self._snapshots) > SNAPSHOT_LIMIT:
                self._snapshots.popitem(last=False)
        return self._project(query, readings, token)

    async def close(self) -> None:
        self._closed = True
        task = self._refresh_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._snapshots.clear()
        self._states = dict.fromkeys(OFFICIAL_SOURCES, SourceState())
