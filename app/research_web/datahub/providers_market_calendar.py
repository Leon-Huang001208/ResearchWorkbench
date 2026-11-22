"""Fixed public economic schedules projected from reviewed official parsers."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from core.observability import get_logger

from ..event_timeline import sources
from ..store import StoreError

log = get_logger(__name__)
OFFICIAL_SOURCES = ("fed_fomc", "bls_cpi", "bls_jobs")
MAX_CAPTURE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    date: str
    title: str
    end_date: str | None


@dataclass(frozen=True)
class CalendarCapture:
    source_id: str
    observed_at: str
    items: tuple[CalendarEvent, ...]
    raw_sha256: str | None = None


async def fetch_official_schedule(source_id: str) -> CalendarCapture:
    if source_id not in OFFICIAL_SOURCES:
        log.warning("market_calendar_source_rejected")
        raise StoreError("未开放该财经日历来源", "market_calendar_source_rejected", 422)

    url, raw = await sources.fetch(source_id)
    observed_at = datetime.now(UTC).isoformat()
    if url != sources.endpoint(source_id) or len(raw) > MAX_CAPTURE_BYTES:
        log.warning("market_calendar_source_contract_mismatch", source=source_id)
        raise StoreError("财经日历来源或响应大小异常", "market_calendar_source_invalid", 502)
    parsed = sources.parse(source_id, raw)
    items = tuple(
        CalendarEvent(
            id=f"{source_id}:{row['external_id']}",
            date=row["occurrence_start"],
            title=row["title"],
            end_date=row["occurrence_end"],
        )
        for row in parsed["events"]
    )
    log.info("market_calendar_schedule_observed", source=source_id, rows=len(items))
    return CalendarCapture(source_id, observed_at, items, sha256(raw).hexdigest())
