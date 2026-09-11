"""Deterministic IANA-timezone schedule calculation for Automation records."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from .models import AutomationSchedule


def _valid_local(local: datetime, zone: ZoneInfo) -> datetime | None:
    """Return the first-fold aware value only when the local wall time exists."""

    aware = local.replace(tzinfo=zone, fold=0)
    roundtrip = aware.astimezone(UTC).astimezone(zone)
    if roundtrip.replace(tzinfo=None) != local or roundtrip.fold != 0:
        return None
    return aware


def _first_valid_local(local: datetime, zone: ZoneInfo) -> datetime:
    candidate = local
    for _ in range(181):
        valid = _valid_local(candidate, zone)
        if valid is not None:
            return valid
        candidate += timedelta(minutes=1)
    raise ValueError("timezone_transition_unresolvable")


def _candidate(schedule: AutomationSchedule, day: date, zone: ZoneInfo) -> datetime:
    # A naive value is deliberate: this is a wall-clock candidate whose IANA
    # offset/fold validity is resolved by ``_first_valid_local``.
    local = datetime(  # noqa: DTZ001
        day.year, day.month, day.day, schedule.hour or 0, schedule.minute or 0
    )
    return _first_valid_local(local, zone)


def next_occurrence(schedule: AutomationSchedule, after: datetime) -> datetime | None:
    """Return the first trigger strictly after ``after`` in UTC."""

    if after.tzinfo is None:
        raise ValueError("after_timezone_required")
    if schedule.kind == "once":
        value = datetime.fromisoformat(schedule.once_at or "").astimezone(UTC)
        return value if value > after.astimezone(UTC) else None
    zone = ZoneInfo(schedule.timezone)
    local_after = after.astimezone(zone)
    start = local_after.date()
    for offset in range(370):
        current = start + timedelta(days=offset)
        if schedule.kind == "weekly" and current.weekday() != schedule.weekday:
            continue
        if schedule.kind == "monthly":
            last = calendar.monthrange(current.year, current.month)[1]
            requested = min(schedule.day or 1, last)
            if current.day != requested:
                continue
        candidate = _candidate(schedule, current, zone).astimezone(UTC)
        if candidate > after.astimezone(UTC):
            return candidate
    raise ValueError("next_occurrence_unresolvable")
