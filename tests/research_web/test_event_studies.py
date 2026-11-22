"""Offline event-study contracts; synthetic samples never certify real markets."""

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.research_web.event_studies.backtest import replay
from app.research_web.event_studies.calendars import calendar_windows, event_windows
from app.research_web.event_studies.contracts import Calendar, Proxy, Session, StudyError
from app.research_web.event_studies.registry import INDICES
from app.research_web.event_studies.validation import chronological_split, holm


def calendar(count=80, start=date(2024, 1, 1)):
    days = [start + timedelta(days=i) for i in range(count * 2)]
    days = [day for day in days if day.weekday() < 5][:count]
    tz = ZoneInfo("America/New_York")
    return Calendar(
        exchange="XNYS",
        timezone="America/New_York",
        version="official-1",
        source_ref="calendar-evidence",
        known_at="2020-01-01T00:00:00Z",
        sessions=[
            Session(
                day=day,
                opens=datetime.combine(day, datetime.min.time(), tz).replace(hour=9, minute=30),
                closes=datetime.combine(day, datetime.min.time(), tz).replace(hour=16),
            )
            for day in days
        ],
    )


def test_registry_has_nine_distinct_official_identities():
    assert len(INDICES) == 9
    assert {i["market"] for i in INDICES.values()} == {"CN", "US", "HK"}
    assert INDICES["HSI"]["currency"] == "HKD"


def test_sessions_require_real_timezone_and_order():
    with unittest.TestCase().assertRaises(ValueError):
        Session(
            day=date(2024, 1, 1), opens=datetime(2024, 1, 1, 9), closes=datetime(2024, 1, 1, 16)
        )
    item = calendar()
    with unittest.TestCase().assertRaises(ValueError):
        Calendar(**{**item.model_dump(), "sessions": list(reversed(item.sessions))})


def test_calendar_effect_fixed_rules_and_no_invented_sessions():
    cal = calendar()
    cal = Calendar(
        **{
            **cal.model_dump(),
            "sessions": [
                s for s in cal.sessions if not date(2024, 2, 12) <= s.day <= date(2024, 2, 16)
            ],
        }
    )
    result = calendar_windows(
        cal, holidays=[{"id": "xmas", "start": "2024-02-10", "end": "2024-02-18"}]
    )
    assert {w["rule"] for w in result} >= {
        "holiday_pre_1",
        "holiday_post_10",
        "holiday_episode",
        "reopening_gap",
        "weekday_0_1",
        "weekday_0_5",
    }
    assert all(w["start"] in {s.day.isoformat() for s in cal.sessions} for w in result)
    with unittest.TestCase().assertRaisesRegex(StudyError, "holiday_overlaps_session"):
        calendar_windows(cal, holidays=[{"id": "bad", "start": "2024-02-19", "end": "2024-02-19"}])


def test_event_windows_use_last_session_before_start_and_final_day():
    cal = calendar()
    result = event_windows(cal, [{"id": "cup", "start": "2024-02-10", "end": "2024-02-18"}])
    row = next(r for r in result if r["rule"] == "event_during")
    assert row["start"] == "2024-02-09" and row["end"] == "2024-02-16"
    assert {w["rule"] for w in result} >= {"event_pre_5", "event_post_10"}


def test_chronological_split_purges_cross_boundary_targets():
    cal = calendar(200)
    result = chronological_split([s.day.isoformat() for s in cal.sessions])
    assert len(result["train"]) == 100
    assert len(result["validation"]) == 20
    assert len(result["holdout"]) == 40
    assert not (set(result["train"]) & set(result["holdout"]))
    assert len(result["purged"]) == 40


def test_holm_keeps_all_registered_hypotheses():
    result = holm({"a": 0.001, "b": 0.04, "failed": None})
    assert result["a"]["rejected"] is True
    assert result["b"]["rejected"] is False
    assert result["failed"]["p_adjusted"] == 1


def proxy(cal):
    return Proxy(
        symbol="SPY",
        index_id="SP500",
        market="US",
        currency="USD",
        exchange="XNYS",
        source_ref="proxy-evidence",
        known_at="2020-01-01T00:00:00Z",
        listed_on="1993-01-29",
        exact_tracking=True,
        price_basis="unadjusted",
        rules=[
            {
                "from_date": "1993-01-29",
                "until_date": "2099-12-31",
                "lot": 1,
                "settlement_sessions": 1,
                "tax_buy_bps": "0",
                "tax_sell_bps": "0",
                "source_ref": "rules-evidence",
                "known_at": "2020-01-01T00:00:00Z",
            }
        ],
    )


def bars(cal):
    return [
        {
            "day": s.day.isoformat(),
            "open": "100",
            "close": str(Decimal(100) + i),
            "known_at": s.closes.isoformat(),
            "execution_known_at": s.opens.isoformat(),
            "dividend": "0",
            "split": "1",
            "actions_known_at": s.opens.isoformat(),
            "source_ref": "prices-evidence",
            "historical_eligible": True,
        }
        for i, s in enumerate(cal.sessions)
    ]


def test_next_open_fees_and_cash_conservation():
    cal = calendar(5)
    result = replay(
        cal, proxy(cal), bars(cal), {cal.sessions[0].day.isoformat(): "1"}, initial_cash="10000"
    )
    assert result["fills"][0]["day"] == cal.sessions[1].day.isoformat()
    assert result["fills"][0]["quantity"] == "99"
    assert Decimal(result["fills"][0]["fee"]) > 0
    assert all(Decimal(row["cash"]) >= 0 for row in result["curve"])


def test_future_prices_do_not_change_earlier_orders():
    cal = calendar(6)
    raw = bars(cal)
    signals = {cal.sessions[0].day.isoformat(): ".8"}
    a = replay(cal, proxy(cal), raw, signals)
    raw[-1]["close"] = "9000"
    b = replay(cal, proxy(cal), raw, signals)
    assert a["fills"] == b["fills"]


def test_missing_pit_and_prelisting_refuse():
    cal = calendar(5)
    raw = bars(cal)
    raw[1]["historical_eligible"] = False
    with unittest.TestCase().assertRaisesRegex(StudyError, "prices_not_historically_eligible"):
        replay(cal, proxy(cal), raw, {})
    with unittest.TestCase().assertRaisesRegex(StudyError, "proxy_before_listing"):
        replay(calendar(5, date(1990, 1, 1)), proxy(cal), raw, {})


def test_unknown_actions_and_unverified_rules_refuse():
    cal = calendar(5)
    raw = bars(cal)
    raw[0]["actions_known_at"] = "2099-01-01T00:00:00Z"
    with unittest.TestCase().assertRaisesRegex(StudyError, "corporate_action_not_known"):
        replay(cal, proxy(cal), raw, {})


def test_doubled_costs_are_not_better_with_same_fills():
    cal = calendar(8)
    signals = {s.day.isoformat(): str(i % 2) for i, s in enumerate(cal.sessions)}
    a = replay(cal, proxy(cal), bars(cal), signals)
    b = replay(cal, proxy(cal), bars(cal), signals, cost_multiplier=2)
    assert Decimal(b["costs"]) >= Decimal(a["costs"])


def test_missing_bar_refuses_complete_simulation():
    cal = calendar(5)
    with unittest.TestCase().assertRaisesRegex(StudyError, "price_calendar_mismatch"):
        replay(cal, proxy(cal), bars(cal)[:-1], {})


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        unittest.FunctionTestCase(fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
