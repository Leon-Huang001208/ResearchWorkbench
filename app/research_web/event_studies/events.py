"""Shared temporal projection from server-owned event versions, without I/O."""

from datetime import UTC, date
from zoneinfo import ZoneInfo

from .contracts import stamp
from .registry import INDICES

FORECAST_PROTOCOL = "known_by_window_start_price_v1"


def availability_floor(recorded_at, archive_observed=()):
    """An exact revision's recording time is mandatory; payload dates are not receipts."""
    if recorded_at is None:
        return None
    try:
        floor = stamp(recorded_at)
    except (ValueError, TypeError):
        return None
    for observed in archive_observed:
        if observed is None:
            continue
        try:
            floor = max(floor, stamp(observed))
        except (ValueError, TypeError):
            continue
    return floor.astimezone(UTC).isoformat()


def project_event(value, index_id, *, identifier=None, revision=None, known_floor=None):
    """Project exact day/minute evidence; never manufacture historical availability.

    ``known_floor`` must come from the caller's private revision/archive receipts.
    Neither ``first_observed`` nor an old publication date in the payload grants
    a historical known-at timestamp on its own.
    """
    if not isinstance(value, dict) or index_id not in INDICES:
        return None
    precision = value.get("date_precision")
    if precision not in {"day", "minute"} or value.get("event_time_eligible") is False:
        return None
    if value.get("lifecycle") in {"cancelled", "scenario"}:
        return None
    zone = {"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}[
        INDICES[index_id]["market"]
    ]
    original_start = value.get("occurrence_start")
    original_end = value.get("occurrence_end")
    end_known = value.get("end_known") is not False and not (
        value.get("lifecycle") == "ongoing" and not original_end
    )
    effective_end = original_end or original_start
    start_utc, end_utc = None, None
    try:
        if precision == "minute":
            first, last = stamp(original_start), stamp(effective_end)
            if last < first:
                return None
            start, end = (
                first.astimezone(ZoneInfo(zone)).date().isoformat(),
                last.astimezone(ZoneInfo(zone)).date().isoformat(),
            )
            start_utc, end_utc = first.astimezone(UTC).isoformat(), last.astimezone(UTC).isoformat()
        else:
            first, last = date.fromisoformat(original_start), date.fromisoformat(effective_end)
            if (
                first.isoformat() != original_start
                or last.isoformat() != effective_end
                or last < first
            ):
                return None
            start, end = original_start, effective_end
    except (ValueError, TypeError):
        return None
    if not end_known:
        end, end_utc = None, None
    elif not original_end:
        end_utc = None
    published = None
    if value.get("source_published_at") is not None:
        try:
            published = stamp(value["source_published_at"])
        except (ValueError, TypeError):
            published = None
    known = None
    floor = availability_floor(known_floor)
    if floor is not None:
        known = stamp(floor)
        if published is not None:
            known = max(known, published)
    return {
        "id": identifier,
        "revision": revision,
        "start": start,
        "end": end,
        "end_known": end_known,
        "known_at": known.astimezone(UTC).isoformat() if known is not None else None,
        "knowledge_floor": floor,
        "date_precision": precision,
        "category": value.get("category"),
        "lifecycle": value.get("lifecycle"),
        "source_occurrence_start": original_start,
        "source_occurrence_end": original_end,
        "source_start_utc": start_utc,
        "source_end_utc": end_utc,
        "source_published_at": value.get("source_published_at"),
        "market_timezone": zone,
        "publication_time_status": (
            "valid_timestamp" if published is not None else "missing_or_imprecise"
        ),
    }


def forecast_window_gaps(calendar, window, *, events=(), deterministic_calendar=False):
    """A retrospective return is predictive only if its context was known at its start price."""
    from .calendars import calendar_knowledge_gaps
    from .contracts import Calendar

    if not isinstance(calendar, Calendar):
        return ["prediction_start_calendar_unknown"]
    session = next(
        (item for item in calendar.sessions if item.day.isoformat() == window.get("start")), None
    )
    if session is None or window.get("start_price") not in {"open", "close"}:
        return ["prediction_start_price_timestamp_unknown"]
    cutoff = session.opens if window["start_price"] == "open" else session.closes
    if deterministic_calendar:
        if calendar_knowledge_gaps(calendar, window, cutoff):
            return ["calendar_schedule_not_known_at_prediction_start"]
        return []
    matching = [event for event in events if event.get("id") == window.get("episode")]
    if len(matching) != 1 or matching[0].get("known_at") is None:
        return ["event_knowledge_unknown_at_prediction_start"]
    try:
        known = stamp(matching[0]["known_at"])
    except (ValueError, TypeError):
        return ["event_knowledge_unknown_at_prediction_start"]
    return ["event_first_known_after_prediction_start"] if known > cutoff else []
