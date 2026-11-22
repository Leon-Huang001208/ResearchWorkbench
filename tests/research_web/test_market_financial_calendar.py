"""Offline ASGI and fixed-source financial-calendar contract checks."""

from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from app.research_web.market_routes import router
from tests.research_web.test_event_api import event_api as _shared_event_api

event_api = _shared_event_api

PATH = "/api/research/market/financial-calendar"
DAY = {"start": "2026-01-13", "end": "2026-01-13"}


def client(service=None):
    app = FastAPI()
    app.state.research = SimpleNamespace(market_financial_calendar=service)
    app.include_router(router)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_calendar_http_rejects_invalid_inputs_before_any_access():
    async with client() as http:
        invalid = (
            {"view": "summary", **DAY, "end": "2026-02-13"},
            {"view": "summary", **DAY, "end": "2026-01-12"},
            {"view": "summary", **DAY, "start": "2026-1-13"},
            {"view": "events", **DAY},
            {"view": "events", **DAY, "category": "economic", "source": "custom"},
            {"view": "events", **DAY, "category": "economic", "page": 1},
            {"view": "events", **DAY, "category": "economic", "page": "0.0"},
            {"view": "events", **DAY, "category": "ipo", "subtype": "notify_divide"},
            {"view": "events", **DAY, "category": "inst", "holding_type": "bogus"},
            [*DAY.items(), ("view", "summary"), ("view", "events")],
        )
        for params in invalid:
            response = await http.get(PATH, params=params)
            assert response.status_code == 422, response.text


async def test_disconnected_views_are_explicit_and_do_not_collect():
    from app.research_web.market_financial_calendar import MarketFinancialCalendar

    async def unexpected(_source):
        raise AssertionError("disconnected views must never collect")

    service = MarketFinancialCalendar(fetcher=unexpected)
    async with client(service) as http:
        for category in ("ipo", "notify", "report", "inst"):
            response = await http.get(PATH, params={"view": "events", "category": category, **DAY})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.json() == {
                "snapshot_id": None,
                "days": [
                    {
                        "date": DAY["start"],
                        "items": [],
                        "total": None,
                        "has_more": False,
                        "status": "not_connected",
                    }
                ],
                "sources": [],
            }
    await service.close()


async def test_official_sources_project_date_precision_and_observed_counts(monkeypatch):
    from app.research_web.event_timeline import sources
    from app.research_web.market_financial_calendar import MarketFinancialCalendar
    from tests.research_web.test_event_timeline import BLS_HTML, FED_ACTUAL_ROW

    seen = []

    async def fetch(source):
        seen.append(source)
        return sources.endpoint(source), FED_ACTUAL_ROW if source == "fed_fomc" else BLS_HTML

    monkeypatch.setattr(sources, "fetch", fetch)
    service = MarketFinancialCalendar()
    async with client(service) as http:
        summary = await http.get(
            PATH, params={"view": "summary", "start": "2026-01-13", "end": "2026-01-28"}
        )
        assert summary.status_code == 200, summary.text
        days = {row["date"]: row for row in summary.json()["days"]}
        assert days["2026-01-13"]["counts"] == {
            "economic": 2,
            "ipo": None,
            "notify": None,
            "report": None,
        }
        assert days["2026-01-14"]["status"] == "partial"
        assert days["2026-01-14"]["counts"]["economic"] is None
        assert days["2026-01-27"]["counts"]["economic"] == 1
        assert days["2026-01-28"]["counts"]["economic"] is None

        detail = await http.get(
            PATH,
            params={
                "view": "events",
                "category": "economic",
                "market": "hk",
                "start": "2026-01-27",
                "end": "2026-01-27",
            },
        )
        payload = detail.json()
        item = payload["days"][0]["items"][0]
        assert item["title"] == "FOMC meeting"
        assert item["date"] == "2026-01-27"
        assert item["end_date"] == "2026-01-28"
        assert item["date_precision"] == "day"
        assert item["source_id"] == "fed_fomc"
        assert item["source_url"] == sources.endpoint("fed_fomc")
        assert item["observed_at"]
        assert not ({"time", "actual", "forecast", "previous", "evidence_refs"} & set(item))
        assert sorted(seen) == ["bls_cpi", "bls_jobs", "fed_fomc"]
    await service.close()


async def test_failed_sources_are_unavailable_or_stale_without_losing_prior_capture(monkeypatch):
    from app.research_web.event_timeline import sources
    from app.research_web.market_financial_calendar import MarketFinancialCalendar
    from app.research_web.store import StoreError
    from tests.research_web.test_event_timeline import BLS_HTML

    state = {"clock": 0, "fail_all": False}

    async def fetch(source):
        if source != "bls_cpi" or state["fail_all"]:
            raise StoreError("private /opt/vendor/path", "event_source_unavailable")
        return sources.endpoint(source), BLS_HTML

    monkeypatch.setattr(sources, "fetch", fetch)
    service = MarketFinancialCalendar(clock=lambda: state["clock"])
    args = {"view": "events", "category": "economic", **DAY}
    async with client(service) as http:
        first = await http.get(PATH, params=args)
        assert first.json()["days"][0]["status"] == "partial"
        assert first.json()["days"][0]["total"] == 1
        status = {row["id"]: row["status"] for row in first.json()["sources"]}
        assert status == {
            "fed_fomc": "unavailable",
            "bls_cpi": "partial",
            "bls_jobs": "unavailable",
        }

        state.update(clock=10_000, fail_all=True)
        stale = await http.get(PATH, params=args)
        assert stale.status_code == 200
        assert stale.json()["days"][0]["status"] == "stale"
        assert stale.json()["days"][0]["items"] == first.json()["days"][0]["items"]
        assert "/opt/vendor/path" not in stale.text
    async with client(MarketFinancialCalendar()) as other:
        unavailable = await other.get(PATH, params=args)
        assert unavailable.json()["days"][0]["status"] == "unavailable"
        assert unavailable.json()["days"][0]["total"] is None
        assert unavailable.json()["snapshot_id"] is None
    await service.close()


async def test_event_pagination_uses_immutable_same_scope_same_account_capture():
    from app.research_web.datahub.providers_market_calendar import (
        CalendarCapture,
        CalendarEvent,
    )
    from app.research_web.market_financial_calendar import MarketFinancialCalendar

    state = {"clock": 0, "label": "initial"}

    async def fetch(source):
        rows = (
            tuple(
                CalendarEvent(f"{state['label']}-{i:02d}", DAY["start"], f"Release {i:02d}", None)
                for i in range(21)
            )
            if source == "bls_cpi"
            else ()
        )
        return CalendarCapture(source, "2026-01-13T01:00:00+00:00", rows)

    service = MarketFinancialCalendar(fetcher=fetch, clock=lambda: state["clock"])
    other = MarketFinancialCalendar(fetcher=fetch, clock=lambda: state["clock"])
    args = {"view": "events", "category": "economic", **DAY}
    async with client(service) as http, client(other) as foreign:
        assert (await http.get(PATH, params={"view": "summary", **DAY})).status_code == 200
        state["clock"] = 300
        first = await http.get(PATH, params=args)
        assert first.status_code == 200, first.text
        body = first.json()
        day = body["days"][0]
        assert day["total"] == 21
        assert len(day["items"]) == 20 and day["has_more"]
        frozen = {**args, "page": 1, "snapshot_id": body["snapshot_id"]}
        assert (await foreign.get(PATH, params=frozen)).status_code == 409
        assert (await http.get(PATH, params={**frozen, "market": "hk"})).status_code == 409
        state.update(clock=1000, label="later")
        refreshed = await http.get(PATH, params=args)
        assert refreshed.json()["days"][0]["items"][0]["id"] == "later-00"
        page = await http.get(PATH, params=frozen)
        assert page.json()["days"][0]["items"][0]["id"] == "initial-20"
        assert not page.json()["days"][0]["has_more"]
        state["clock"] = 10_000
        assert (await http.get(PATH, params=frozen)).status_code == 409
    await service.close()
    await other.close()


async def test_close_drains_shared_fetch_and_rejects_reuse():
    import asyncio

    from app.research_web.market_financial_calendar import MarketFinancialCalendar

    entered = asyncio.Event()
    cancelled = []

    async def fetch(source):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.append(source)

    service = MarketFinancialCalendar(fetcher=fetch)
    args = {"view": "events", "category": "economic", **DAY}
    async with client(service) as http:
        first = asyncio.create_task(http.get(PATH, params=args))
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = asyncio.create_task(http.get(PATH, params=args))
        await asyncio.sleep(0)
        await service.close()
        assert (await first).status_code == 503
        assert (await second).status_code == 503
        assert (await http.get(PATH, params=args)).status_code == 503
    assert sorted(cancelled) == ["bls_cpi", "bls_jobs", "fed_fomc"]


def test_account_host_does_not_read_or_write_research_events(event_api, monkeypatch):
    from app.research_web.event_timeline import sources
    from tests.research_web.test_event_timeline import BLS_HTML, FED_ACTUAL_ROW

    http, research, native = event_api
    created = http.post(
        "/api/research/events",
        json={
            "title": "私有手工财经事项",
            "category": "macro",
            "occurrence_start": DAY["start"],
            "markets": ["US"],
            "idempotency_key": "manual-private-calendar-1",
        },
        headers={"X-Research-User-Action": "?1"},
    )
    assert created.status_code == 200, created.text
    events_before = research.event_timeline.records.list("event")
    sessions_before = list(research.store.data["sessions"])

    async def fetch(source):
        return sources.endpoint(source), FED_ACTUAL_ROW if source == "fed_fomc" else BLS_HTML

    monkeypatch.setattr(sources, "fetch", fetch)
    response = http.get(PATH, params={"view": "events", "category": "economic", **DAY})
    assert response.status_code == 200, response.text
    assert response.json()["days"][0]["total"] == 2
    assert "私有手工财经事项" not in response.text
    assert research.event_timeline.records.list("event") == events_before
    assert not research.event_timeline.records.list("source_job")["items"]
    assert list(research.store.data["sessions"]) == sessions_before
    assert not any(call[0] == "session.prompt" for call in native.calls)
