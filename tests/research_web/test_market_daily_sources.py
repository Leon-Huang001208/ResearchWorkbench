"""Official calendar contracts use fixtures; live source probes are separate."""

import asyncio
import json
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

import pdfplumber
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web.event_timeline import TimelineService, initial_batch, router, sources
from app.research_web.store import Store, StoreError

SSE = """
<div class="sse_colContent"><strong>2026年休市安排</strong>
<div class="table-responsive"><table>
<tr><td>国庆节：</td><td>10月1日（星期四）至10月7日（星期三）休市，10月8日（星期四）起照常开市。</td></tr>
</table></div></div>
""".encode()
NYSE = b"""
<table><tr><th>Holiday</th><th>2026</th><th>2027</th></tr>
<tr><td>Thanksgiving Day</td><td>Thursday, November 26***</td><td>Thursday, November 25***</td></tr>
</table>
<span>*** Each market will close early at 1:00 p.m. (1:15 p.m. for eligible options) on
Friday, November 27, 2026 and Friday, November 26, 2027. All times are Eastern Time.</span>
"""
HKEX = b"""
Hong Kong Securities Market Holiday Schedule for Year 2026
CT/075/25
02/06/2025
Securities Market is closed on Saturdays, Sundays and Public Holidays
25 December 2026 Friday Christmas Day
The following trading days are half-day trading day and non-settlement day:
24 December 2026 (Thursday) - Eve of Christmas Day
"""
FED = b"""
<h4>2026 FOMC Meetings</h4><div class="fomc-meeting">
<div class="fomc-meeting__month">December</div><div class="fomc-meeting__date">8-9</div></div>
"""
BLS = b"""
<table class="regular-data"><tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>
<tr><td>December 2025</td><td>Jan. 13, 2026</td><td>08:30 AM</td></tr></table>
"""


def hkhtml():
    def row(day, label, description="", holiday="", activity=""):
        return {
            "name": label,
            "description": description,
            "holidayIcon": holiday,
            "activityIcon": activity,
            "startdate": day,
            "enddate": day,
        }

    data = {
        "monthly": [
            row(
                "2026-12-25",
                "Covered by 2026 PDF",
                "Hong Kong Market is closed",
                "HongKongPublicHolidays",
            ),
            row("2027-02-08", "Holiday", "Hong Kong Market is closed", "HongKongPublicHolidays"),
            row(
                "2027-02-05",
                "Half-Day Trading Day - Afternoon Session is Closed on Lunar New Year's Eve",
                activity="SecuritiesandDerivatives",
            ),
            row(
                "2027-02-06",
                "Half-Day Trading Day - Afternoon Session is Closed on another session",
                activity="StockConnect",
            ),
            row("2027-03-06", "Settlement only", "Hong Kong Market is closed", "StockConnect"),
        ]
    }
    return ("var calendarDataSource = '" + json.dumps(data).replace("'", r"\u0027") + "';").encode()


def mock_pdf(monkeypatch, text=HKEX):
    monkeypatch.setattr(
        pdfplumber,
        "open",
        lambda _source: nullcontext(
            SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text.decode())])
        ),
    )


def test_exchange_parsers_only_accept_quoted_announced_market_exceptions(monkeypatch):
    mock_pdf(monkeypatch)
    calendars = {
        "sse_trading_calendar": SSE,
        "nyse_trading_calendar": NYSE,
        "hkex_securities_2026": b"pdf input fixture",
        "hkex_securities_calendar": hkhtml(),
    }
    results = {}
    for name, raw in calendars.items():
        results[name] = sources.parse(name, raw)["events"]
        assert all(
            item["lifecycle"] == "announced"
            and item["occurrence_evidence"] == "schedule_only"
            and item["formal_backtest_eligible"] is False
            and item["source_url"] == sources.endpoint(name)
            for item in results[name]
        )
    closed, reopen = results["sse_trading_calendar"]
    assert (closed["calendar_status"], closed["occurrence_start"], closed["occurrence_end"]) == (
        "closed",
        "2026-10-01",
        "2026-10-07",
    )
    assert (reopen["calendar_status"], reopen["occurrence_start"]) == ("reopen", "2026-10-08")
    early = next(
        item for item in results["nyse_trading_calendar"] if item["calendar_status"] == "half_day"
    )
    assert (
        early["occurrence_start"],
        early["calendar_close_local"],
        early["calendar_timezone"],
    ) == ("2026-11-27", "13:00", "America/New_York")
    assert {item["occurrence_start"] for item in results["hkex_securities_2026"]} == {
        "2026-12-24",
        "2026-12-25",
    }
    assert {item["occurrence_start"] for item in results["hkex_securities_calendar"]} == {
        "2027-02-05",
        "2027-02-08",
    }


def test_unexpected_schedule_structure_fails_without_guessing(monkeypatch):
    malformed = NYSE.replace(b"Thursday, November 26", b"Monday, November 26")
    with pytest.raises(StoreError) as error:
        sources.parse("nyse_trading_calendar", malformed)
    assert error.value.code == "event_source_parse_failed"
    mock_pdf(
        monkeypatch,
        HKEX.replace(b"Securities Market Holiday Schedule", b"Derivatives Market Holiday Schedule"),
    )
    with pytest.raises(StoreError) as error:
        sources.parse("hkex_securities_2026", b"unknown PDF")
    assert error.value.code == "event_source_parse_failed"


def test_preview_and_partial_batch_are_account_local_and_idempotent(tmp_path, monkeypatch):
    mock_pdf(monkeypatch)
    monkeypatch.setattr(initial_batch, "date_window", lambda: ("2026-01-01", "2027-11-08"))
    content = {
        "sse_trading_calendar": SSE,
        "nyse_trading_calendar": NYSE,
        "hkex_securities_2026": b"immutable PDF fixture",
        "hkex_securities_calendar": hkhtml(),
        "fed_fomc": FED,
        "bls_cpi": BLS,
    }
    calls = []

    async def fetcher(source, year, page):
        calls.append((source, year, page))
        if source == "bls_jobs":
            raise StoreError("source unavailable", "event_source_unavailable", 502)
        return sources.endpoint(source, year, page), content[source]

    service = TimelineService(SimpleNamespace(store=Store(tmp_path / "own")), fetcher=fetcher)
    other = TimelineService(SimpleNamespace(store=Store(tmp_path / "other")), fetcher=fetcher)
    before = set(tmp_path.rglob("*"))
    result = asyncio.run(initial_batch.preview(service))
    assert result["status"] == "preview" and len(result["items"]) == 7
    assert set(tmp_path.rglob("*")) == before
    assert result["items"][-1]["records"] is None

    async def import_and_replay():
        first = await initial_batch.execute(service, "initial-batch-test-0001")
        count = len(calls)
        assert await initial_batch.execute(service, "initial-batch-test-0001") == first
        assert len(calls) == count
        return first

    first = asyncio.run(import_and_replay())
    assert first["status"] == "partial" and first["schedules_enabled"] is False
    assert service.records.get("source_job", first["batch_id"])["payload"]["drain_receipt"] == {
        "format": "initial-import-drain-v1",
        "state": "partial",
    }
    assert service.records.list("source_schedule")["items"] == []
    ref = first["items"][0]["raw_ref"]
    assert service.read_evidence(ref)["bytes"] == SSE
    assert other.timeline()["items"] == []
    with pytest.raises(StoreError):
        other.read_evidence(ref)
    rows = service.timeline(start="2026-10-07", end="2026-10-07", category="calendar", market="CN")[
        "items"
    ]
    assert len(rows) == 1 and rows[0]["payload"]["occurrence_start"] == "2026-10-01"
    assert rows[0]["payload"]["admission"] == "candidate"
    assert any(
        x["payload"]["state"] == "source_failed" and x["payload"]["source"] == "bls_jobs"
        for x in service.coverage()["items"]
    )
    range_args = {"start": first["start"], "end": first["end"]}
    ids = {row["id"] for row in service.timeline(**range_args)["items"]}
    assert ids
    assert (
        asyncio.run(initial_batch.execute(service, "initial-batch-test-0002"))["status"]
        == "partial"
    )
    assert {row["id"] for row in service.timeline(**range_args)["items"]} == ids
    revised = service.revise(
        rows[0]["id"],
        {
            "title": "人工备注",
            "category": "calendar",
            "occurrence_start": "2026-10-09",
            "markets": ["CN"],
            "reason": "人工修订不得继承官方日期状态",
            "expected_revision": rows[0]["revision"],
            "idempotency_key": "revise-exchange-event-01",
        },
    )
    assert "calendar_status" not in revised["payload"]
    assert (
        service.detail(rows[0]["id"], revision=rows[0]["revision"])["payload"]["calendar_status"]
        == "closed"
    )


def test_batch_cannot_start_with_collection_enabled_and_key_payload_closed(tmp_path):
    assert initial_batch.date_window(date(2024, 2, 29)) == ("2024-01-01", "2025-02-28")
    service = TimelineService(SimpleNamespace(store=Store(tmp_path / "own")))
    service.records.create(
        "source_schedule", {"source": "fed_fomc", "enabled": True}, "fixture-schedule"
    )
    with pytest.raises(StoreError) as error:
        asyncio.run(initial_batch.execute(service, "initial-batch-test-0003"))
    assert error.value.code == "event_initial_batch_requires_disabled_schedules"
    assert not service.records.list("source_job")["items"]
    app = FastAPI()
    app.include_router(router)
    app.state.research = SimpleNamespace(event_timeline=service)
    client = TestClient(app)
    with pytest.raises(StoreError) as error:
        client.post(
            "/api/research/events/initial-batch", json={"idempotency_key": "valid-test-key"}
        )
    assert error.value.code == "event_user_action_required"
    response = client.post(
        "/api/research/events/initial-batch",
        json={"idempotency_key": "valid-test-key", "source": "arbitrary"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert response.status_code == 422


def test_source_timeout_drains_before_gap_and_batch_budget_does_not_fetch_later_sources(
    tmp_path, monkeypatch
):
    seen = []
    elapsed = [0]
    monkeypatch.setattr(initial_batch, "INITIAL_SOURCES", ("fed_fomc", "bls_cpi", "bls_jobs"))
    monkeypatch.setattr(initial_batch, "SOURCE_BUDGET_SECONDS", 0.35)
    monkeypatch.setattr(initial_batch, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(initial_batch, "date_window", lambda: ("2026-01-01", "2027-11-08"))

    async def fetcher(source, year, page):
        seen.append(source)
        if source == "fed_fomc":
            return sources.endpoint(source, year, page), FED
        if source == "bls_cpi":
            try:
                await asyncio.Event().wait()
            finally:
                seen.append("cpi-cancelled")
                elapsed[0] = initial_batch.BATCH_BUDGET_SECONDS + 1
        raise AssertionError("remaining source must not be fetched")

    service = TimelineService(SimpleNamespace(store=Store(tmp_path / "own")), fetcher=fetcher)
    outcome = asyncio.run(initial_batch.execute(service, "initial-budget-test-0001"))
    assert seen == ["fed_fomc", "bls_cpi", "cpi-cancelled"]
    assert outcome["status"] == "partial"
    assert [row["status"] for row in outcome["items"]] == ["completed", "failed", "not_attempted"]
    source_job = next(
        row
        for row in service.records.list("source_job")["items"]
        if row["payload"]["source"] == "bls_cpi"
    )
    assert source_job["payload"]["state"] == "interrupted"
    assert source_job["payload"]["drain_receipt"] == {
        "format": "initial-import-drain-v1",
        "state": "interrupted",
    }
    states = {
        row["payload"]["source"]: row["payload"]["state"] for row in service.coverage()["items"]
    }
    assert states == {
        "fed_fomc": "source_scoped_partial",
        "bls_cpi": "source_failed",
        "bls_jobs": "source_not_attempted",
    }
