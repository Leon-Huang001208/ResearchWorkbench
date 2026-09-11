from datetime import UTC, datetime

from app.research_web.automation.models import AutomationSchedule
from app.research_web.automation.schedule import next_occurrence


def test_monthly_schedule_uses_last_day_when_requested_day_is_missing():
    schedule = AutomationSchedule(
        kind="monthly",
        timezone="Asia/Shanghai",
        day=31,
        hour=9,
        minute=30,
    )

    assert next_occurrence(schedule, datetime(2028, 2, 1, tzinfo=UTC)) == datetime(
        2028, 2, 29, 1, 30, tzinfo=UTC
    )


def test_nonexistent_dst_time_moves_to_first_valid_minute():
    schedule = AutomationSchedule(
        kind="daily",
        timezone="America/New_York",
        hour=2,
        minute=30,
    )

    assert next_occurrence(schedule, datetime(2026, 3, 8, 5, tzinfo=UTC)) == datetime(
        2026, 3, 8, 7, tzinfo=UTC
    )


def test_repeated_dst_time_uses_first_occurrence_only():
    schedule = AutomationSchedule(
        kind="daily",
        timezone="America/New_York",
        hour=1,
        minute=30,
    )

    assert next_occurrence(schedule, datetime(2026, 11, 1, 4, tzinfo=UTC)) == datetime(
        2026, 11, 1, 5, 30, tzinfo=UTC
    )
    assert next_occurrence(schedule, datetime(2026, 11, 1, 5, 31, tzinfo=UTC)) == datetime(
        2026, 11, 2, 6, 30, tzinfo=UTC
    )


def test_once_schedule_rejects_naive_timestamp():
    try:
        AutomationSchedule(kind="once", timezone="Asia/Shanghai", once_at="2026-09-11T09:00:00")
    except ValueError as exc:
        assert "once_at" in str(exc)
    else:
        raise AssertionError("naive once_at must be rejected")
