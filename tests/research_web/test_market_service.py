"""Sessionless market cache, reader ownership and HTTP regression coverage."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.research_web.market_routes import router
from app.research_web.market_service import MarketError, MarketService


def payload(rows=None, *, complete=True, summary=None):
    return {
        "rows": rows or [],
        "summary": summary or {},
        "provider": "eastmoney",
        "source_url": "https://quote.eastmoney.com/",
        "as_of": "2026-10-22T10:00:00+08:00",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "started_at": datetime.now(UTC).isoformat(),
        "provider_total": len(rows or []),
        "pages_fetched": 1,
        "pagination_complete": complete,
        "complete": complete,
        "missing": {},
        "limitations": [],
    }


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.value = payload(
            [
                {
                    "asset": "000001.SZ",
                    "code": "000001",
                    "name": "深圳",
                    "exchange": "SZ",
                    "board": "main",
                    "change_pct": 0,
                    "price": 10,
                },
                {
                    "asset": "810011.BJ",
                    "code": "810011",
                    "name": "北京",
                    "exchange": "BJ",
                    "board": "beijing",
                    "change_pct": None,
                    "price": None,
                },
                {
                    "asset": "600001.SH",
                    "code": "600001",
                    "name": "=SUM(A1)",
                    "exchange": "SH",
                    "board": "main",
                    "change_pct": -2,
                    "price": 8,
                },
            ]
        )
        self.wait = None
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.cleanup = None
        self.closed = False

    async def fetch(self, section, **kwargs):
        self.calls.append((section, kwargs))
        self.started.set()
        try:
            if self.wait is not None:
                await self.wait.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            if self.cleanup is not None:
                await self.cleanup.wait()
            raise
        if isinstance(self.value, Exception):
            raise self.value
        return deepcopy(self.value)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_activity_witness_tracks_real_collection_and_cancel_drain(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    provider.cleanup = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    request = await service.refresh(["quotes"])
    await provider.started.wait()
    cancelling = None
    try:
        assert service.activity_witness()["active"] is True
        cancelling = asyncio.create_task(service.cancel(request["request_id"]))
        await provider.cancelled.wait()
        assert service.request(request["request_id"])["status"] == "cancelled"
        assert service.activity_witness()["active"] is True
        provider.cleanup.set()
        await cancelling
        assert service.activity_witness()["active"] is False
    finally:
        provider.wait.set()
        provider.cleanup.set()
        if cancelling is not None:
            await cancelling
        await service.close()


@pytest.mark.asyncio
async def test_activity_witness_covers_provider_close_and_close_failure(tmp_path):
    class ClosingProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.close_started = asyncio.Event()
            self.close_release = asyncio.Event()

        async def close(self):
            self.close_started.set()
            await self.close_release.wait()
            self.closed = True

    provider = ClosingProvider()
    service = MarketService(tmp_path, provider=provider)
    closing = asyncio.create_task(service.close())
    await provider.close_started.wait()
    try:
        assert not service._collectors
        assert service.activity_witness()["active"] is True
    finally:
        provider.close_release.set()
        await closing
    assert service.activity_witness()["active"] is False

    class FailingProvider(FakeProvider):
        async def close(self):
            raise RuntimeError("vendor-close-detail-must-stay-private")

    failed = MarketService(tmp_path / "failed", provider=FailingProvider())
    await failed.close()
    assert failed.activity_witness()["active"] is None


@pytest.mark.asyncio
async def test_close_does_not_interrupt_an_already_draining_collector(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    provider.cleanup = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    request = await service.refresh(["quotes"])
    await provider.started.wait()
    cancelling = asyncio.create_task(service.cancel(request["request_id"]))
    await provider.cancelled.wait()
    closing = asyncio.create_task(service.close())
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not closing.done()
        assert service.activity_witness()["active"] is True
    finally:
        provider.cleanup.set()
        await asyncio.gather(cancelling, closing)
    assert service.activity_witness()["active"] is False


def test_activity_witness_rejects_invalid_or_unbounded_state(tmp_path):
    service = MarketService(tmp_path, provider=FakeProvider())
    assert service.activity_witness()["active"] is False
    service._collectors = {str(index): {} for index in range(17)}
    assert service.activity_witness()["active"] is None
    service._collectors = {"quotes": {"task": None, "readers": set(), "draining": False}}
    assert service.activity_witness()["active"] is None
    service._collectors = {}
    service._closing = -1
    assert service.activity_witness()["active"] is None


async def settled(service, request):
    for _ in range(100):
        state = service.request(request["request_id"])
        if state["status"] not in {"pending", "running"}:
            return state
        await asyncio.sleep(0.005)
    raise AssertionError("market request did not settle")


@pytest.mark.asyncio
async def test_get_is_read_only_and_refresh_never_creates_research_session(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    assert service.overview()["market_state"]["state"] == "unknown"
    assert provider.calls == []
    assert not (tmp_path / "index.json").exists()
    result = await settled(service, await service.refresh(["quotes"]))
    assert result["status"] == "completed"
    assert "rows" not in service.overview()["sections"]["quotes"]
    assert service.quotes()["total"] == 3
    assert not (tmp_path / "index.json").exists()
    await service.close()


@pytest.mark.asyncio
async def test_readers_share_fetch_and_cancel_only_owns_subscription(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    first = await service.refresh(["quotes"])
    second = await service.refresh(["quotes"])
    await provider.started.wait()
    assert len(provider.calls) == 1
    await service.cancel(first["request_id"])
    assert not provider.cancelled.is_set()
    provider.wait.set()
    assert (await settled(service, second))["status"] == "completed"
    assert service.request(first["request_id"])["status"] == "cancelled"
    await service.close()


@pytest.mark.asyncio
async def test_last_reader_cancel_and_close_reap_collection(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    request = await service.refresh(["quotes"])
    await provider.started.wait()
    await service.cancel(request["request_id"])
    assert provider.cancelled.is_set()
    assert not service.overview()["inflight"]
    await service.close()
    assert provider.closed


@pytest.mark.asyncio
async def test_new_reader_waits_for_cancelling_collector_cleanup(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    provider.cleanup = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    first = await service.refresh(["quotes"])
    await provider.started.wait()
    cancelling = asyncio.create_task(service.cancel(first["request_id"]))
    await provider.cancelled.wait()
    second_call = asyncio.create_task(service.refresh(["quotes"]))
    await asyncio.sleep(0)
    assert not second_call.done()
    provider.cleanup.set()
    await cancelling
    second = await second_call
    provider.wait.set()
    result = await settled(service, second)
    assert result["status"] == "completed"
    assert len(provider.calls) == 2
    assert result["sections"]["quotes"]["snapshot_id"] is not None
    await service.close()


@pytest.mark.asyncio
async def test_immediate_cancel_releases_not_yet_started_collector(tmp_path):
    service = MarketService(tmp_path, provider=FakeProvider())
    request = await service.refresh(["quotes"])
    await service.cancel(request["request_id"])
    assert not service._collectors
    assert (await settled(service, await service.refresh(["quotes"])))["status"] == "completed"
    await service.close()


@pytest.mark.asyncio
async def test_cooldown_idempotency_and_partial_not_exported_as_complete(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    request = await service.refresh(["quotes"], idempotency_key="request-1234")
    await settled(service, request)
    same = await service.refresh(["quotes"], idempotency_key="request-1234")
    assert same["request_id"] == request["request_id"]
    await settled(service, await service.refresh(["quotes"]))
    assert len(provider.calls) == 1
    with pytest.raises(MarketError):
        await service.refresh(["indices"], idempotency_key="request-1234")
    await service.close()


@pytest.mark.asyncio
async def test_first_partial_cannot_be_exported_as_full_market(tmp_path):
    provider = FakeProvider()
    provider.value["complete"] = False
    provider.value["pagination_complete"] = False
    service = MarketService(tmp_path, provider=provider)
    await settled(service, await service.refresh(["quotes"]))
    assert not service.quotes()["meta"]["complete"]
    with pytest.raises(MarketError):
        service.export_quotes()
    assert not list((tmp_path / "market-cache").glob("*.json"))
    await service.close()


@pytest.mark.asyncio
async def test_close_marks_owned_active_jobs_cancelled(tmp_path):
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    request = await service.refresh(["quotes"])
    await provider.started.wait()
    await service.close()
    assert service.request(request["request_id"])["status"] == "cancelled"
    assert provider.cancelled.is_set() and not service._collectors


@pytest.mark.asyncio
async def test_previous_complete_survives_partial_failure_and_restart(tmp_path):
    provider = FakeProvider()
    ticks = [0.0]
    service = MarketService(tmp_path, provider=provider, clock=lambda: ticks[0])
    await settled(service, await service.refresh(["quotes"]))
    original = service.quotes()["snapshot_id"]
    ticks[0] += 31
    provider.value = payload([{"asset": "600001.SH", "code": "600001"}], complete=False)
    assert (await settled(service, await service.refresh(["quotes"])))["status"] == "failed"
    section = service.overview()["sections"]["quotes"]
    assert section["snapshot_id"] == original and section["stale"]
    assert section["error"]["code"] == "market_partial"
    ticks[0] += 31
    provider.value = RuntimeError("private upstream details must not leak")
    await settled(service, await service.refresh(["quotes"]))
    assert "private upstream" not in str(service.overview())
    await service.close()
    restored = MarketService(tmp_path, provider=FakeProvider())
    assert restored.quotes()["snapshot_id"] == original
    assert restored.quotes()["total"] == 3
    other = MarketService(tmp_path / "other", provider=FakeProvider())
    with pytest.raises(MarketError):
        other.quotes(snapshot_id=original)
    await restored.close()
    await other.close()


@pytest.mark.asyncio
async def test_filter_sort_missing_last_and_export_same_snapshot(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    await settled(service, await service.refresh(["quotes"]))
    rows = service.quotes(sort="change_pct", direction="asc")
    assert [row["asset"] for row in rows["items"]] == ["600001.SH", "000001.SZ", "810011.BJ"]
    assert service.quotes(exchange="BJ")["items"][0]["asset"] == "810011.BJ"
    assert service.quotes(search="深圳")["total"] == 1
    text, snapshot = service.export_quotes(snapshot_id=rows["snapshot_id"])
    assert "'=SUM(A1)" in text
    assert snapshot == rows["snapshot_id"]
    with pytest.raises(MarketError):
        service.quotes(sort="arbitrary_sql")
    await service.close()


@pytest.mark.asyncio
async def test_more_than_5000_rows_and_current_previous_snapshots(tmp_path):
    provider = FakeProvider()
    provider.value = payload(
        [
            {"asset": f"{i:06d}.SZ", "code": f"{i:06d}", "exchange": "SZ", "change_pct": i}
            for i in range(6001)
        ]
    )
    ticks = [0.0]
    service = MarketService(tmp_path, provider=provider, clock=lambda: ticks[0])
    await settled(service, await service.refresh(["quotes"]))
    first = service.quotes()["snapshot_id"]
    assert service.quotes(offset=6000)["total"] == 6001
    ticks[0] += 31
    provider.value = payload([{"asset": "000001.SZ", "code": "000001"}])
    await settled(service, await service.refresh(["quotes"]))
    assert service.quotes(snapshot_id=first)["total"] == 6001
    await service.close()


def test_market_state_uses_calendar_not_weekdays(tmp_path):
    now = datetime.fromisoformat("2026-10-22T10:00:00+08:00")
    service = MarketService(tmp_path, provider=FakeProvider(), now=lambda: now)
    assert service.overview()["market_state"]["state"] == "unknown"
    service._snapshots["calendar"] = {
        **payload(
            summary={
                "trading_dates": ["2026-10-21", "2026-10-22", "2026-10-23"],
                "valid_until": "2026-10-23",
            }
        ),
        "snapshot_id": "calendar-test",
    }
    assert service.overview()["market_state"]["state"] == "open"
    service._snapshots["calendar"]["summary"]["trading_dates"] = ["2026-10-21", "2026-10-23"]
    assert service.overview()["market_state"]["state"] == "non_trading"


@pytest.mark.asyncio
async def test_recent_fetch_does_not_make_previous_trading_day_fresh(tmp_path):
    provider = FakeProvider()
    provider.value["as_of"] = "2026-10-21T15:00:00+08:00"
    provider.value["retrieved_at"] = "2026-10-22T10:00:00+08:00"
    now = datetime.fromisoformat("2026-10-22T10:00:00+08:00")
    service = MarketService(tmp_path, provider=provider, now=lambda: now)
    await settled(service, await service.refresh(["quotes"]))
    provider.value = payload(summary={"trading_dates": ["2026-10-21", "2026-10-22", "2026-10-23"]})
    await settled(service, await service.refresh(["calendar"]))
    assert service.overview()["sections"]["quotes"]["stale"]
    await service.close()


@pytest.mark.asyncio
async def test_members_use_existing_board_and_quote_identity(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    with pytest.raises(MarketError):
        await service.refresh(["members"], board_id="BK1234")
    await settled(service, await service.refresh(["quotes"]))
    provider.value = payload([{"board_id": "BK1234", "name": "样例"}])
    await settled(service, await service.refresh(["industry"]))
    provider.value = payload([{"code": "810011", "market": 0}, {"code": "000001", "market": 0}])
    await settled(service, await service.refresh(["members"], board_id="BK1234"))
    members = service.quotes(board_id="BK1234")
    assert {row["asset"] for row in members["items"]} == {"810011.BJ", "000001.SZ"}
    await service.close()


@pytest.mark.asyncio
async def test_concept_members_infers_catalog_kind_and_reports_row_count(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    await settled(service, await service.refresh(["quotes"]))
    assert service.overview()["sections"]["quotes"]["row_count"] == 3
    provider.value = payload([{"board_id": "BK5678", "name": "概念"}])
    await settled(service, await service.refresh(["concept"]))
    provider.value = payload([{"code": "810011", "market": 0}])
    await settled(service, await service.refresh(["members"], board_id="BK5678"))
    assert provider.calls[-1][1]["kind"] == "concept"
    assert service.quotes(board_id="BK5678")["total"] == 1
    await service.close()


@pytest.mark.asyncio
async def test_members_rebind_raw_identity_to_requested_quote_snapshot(tmp_path):
    provider = FakeProvider()
    ticks = [0.0]
    service = MarketService(tmp_path, provider=provider, clock=lambda: ticks[0])
    await settled(service, await service.refresh(["quotes"]))
    first = service.quotes()["snapshot_id"]
    provider.value = payload([{"board_id": "BK1234", "name": "样例"}])
    await settled(service, await service.refresh(["industry"]))
    provider.value = payload([{"code": "810011", "market": 0}])
    await settled(service, await service.refresh(["members"], board_id="BK1234"))
    assert service.quotes(board_id="BK1234")["total"] == 1
    ticks[0] += 31
    provider.value = payload([{"asset": "000001.SZ", "code": "000001", "exchange": "SZ"}])
    await settled(service, await service.refresh(["quotes"]))
    second = service.quotes()["snapshot_id"]
    fresh = service.quotes(board_id="BK1234", snapshot_id=second)
    assert fresh["total"] == 0
    assert fresh["meta"]["membership"]["summary"]["quotes_snapshot_id"] == second
    assert fresh["meta"]["membership"]["summary"]["unmatched"] == 1
    assert not fresh["meta"]["membership"]["complete"]
    previous = service.quotes(board_id="BK1234", snapshot_id=first)
    assert previous["total"] == 1
    assert previous["meta"]["membership"]["summary"]["quotes_snapshot_id"] == first
    assert "raw_members" not in previous["meta"]["membership"]
    await service.close()


@pytest.mark.asyncio
async def test_legacy_members_without_raw_evidence_reject_snapshot_change(tmp_path):
    provider = FakeProvider()
    ticks = [0.0]
    service = MarketService(tmp_path, provider=provider, clock=lambda: ticks[0])
    await settled(service, await service.refresh(["quotes"]))
    provider.value = payload([{"board_id": "BK1234", "name": "样例"}])
    await settled(service, await service.refresh(["industry"]))
    provider.value = payload([{"code": "810011", "market": 0}])
    await settled(service, await service.refresh(["members"], board_id="BK1234"))
    service._snapshots["members:BK1234"].pop("raw_members", None)
    ticks[0] += 31
    provider.value = FakeProvider().value
    await settled(service, await service.refresh(["quotes"]))
    with pytest.raises(MarketError) as exc:
        service.quotes(board_id="BK1234")
    assert exc.value.code == "market_members_snapshot_changed"
    await service.close()


@pytest.mark.asyncio
async def test_symlink_cache_is_not_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "user"
    root.mkdir()
    (root / "market-cache").symlink_to(outside, target_is_directory=True)
    service = MarketService(root, provider=FakeProvider())
    state = await settled(service, await service.refresh(["quotes"]))
    assert state["status"] == "failed"
    assert not list(outside.iterdir())
    await service.close()


@pytest.mark.asyncio
async def test_corrupt_other_cache_does_not_hide_durable_quotes(tmp_path):
    service = MarketService(tmp_path, provider=FakeProvider())
    await settled(service, await service.refresh(["quotes"]))
    snapshot_id = service.quotes()["snapshot_id"]
    await service.close()
    (tmp_path / "market-cache" / ("0" * 64 + ".json")).write_text("{bad json", encoding="utf-8")
    restored = MarketService(tmp_path, provider=FakeProvider())
    assert restored.quotes()["snapshot_id"] == snapshot_id
    await restored.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["schema", "partial", "nonfinite"])
async def test_corrupt_current_restores_previous_complete_snapshot(tmp_path, corruption):
    ticks = [0.0]
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider, clock=lambda: ticks[0])
    await settled(service, await service.refresh(["quotes"]))
    previous = service.quotes()["snapshot_id"]
    ticks[0] += 31
    provider.value = payload([{"asset": "000002.SZ", "code": "000002", "exchange": "SZ"}])
    await settled(service, await service.refresh(["quotes"]))
    path = service._path("quotes")
    await service.close()
    record = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "schema":
        record["current"]["rows"] = "broken"
    elif corruption == "partial":
        record["current"]["pagination_complete"] = False
    else:
        record["current"]["rows"][0]["price"] = float("nan")
    path.write_text(json.dumps(record), encoding="utf-8")
    restored = MarketService(tmp_path, provider=FakeProvider())
    assert restored.quotes()["snapshot_id"] == previous
    restored_section = restored.overview()["sections"]["quotes"]
    assert restored_section["stale"] and restored_section["status"] == "stale"
    assert restored_section["error"]["code"] == "market_cache_recovered"
    assert restored_section["complete"] and restored_section["pagination_complete"]
    await restored.close()


@pytest.mark.asyncio
async def test_timeout_is_safe_failure_and_reaps_job(tmp_path, monkeypatch):
    monkeypatch.setattr("app.research_web.market_service.COLLECTION_TIMEOUT", 0.01)
    provider = FakeProvider()
    provider.wait = asyncio.Event()
    service = MarketService(tmp_path, provider=provider)
    state = await settled(service, await service.refresh(["quotes"]))
    assert state["status"] == "failed"
    assert state["errors"]["quotes"]["code"] == "market_timeout"
    assert not service._collectors
    await service.close()


@pytest.mark.asyncio
async def test_http_contract_bounds_and_read_only_routes(tmp_path):
    provider = FakeProvider()
    service = MarketService(tmp_path, provider=provider)
    app = FastAPI()
    app.state.research = SimpleNamespace(market=service)
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/research/market")).status_code == 200
        assert provider.calls == []
        assert (
            await client.post(
                "/api/research/market/refresh", json={"sections": ["quotes"], "source": "secret"}
            )
        ).status_code == 422
        response = await client.post("/api/research/market/refresh", json={"sections": ["quotes"]})
        assert response.status_code == 202
        await settled(service, response.json())
        assert (await client.get("/api/research/market/quotes?limit=201")).status_code == 422
        assert (await client.get("/api/research/market/quotes?unknown=true")).status_code == 422
        missing = await client.get("/api/research/market/refresh/not-found")
        assert (
            missing.status_code == 404
            and missing.json()["error"]["code"] == "market_request_missing"
        )
        assert (await client.get("/api/research/market/quotes?exchange=BJ")).json()["total"] == 1
        assert (
            (await client.get("/api/research/market/quotes/export"))
            .headers["content-type"]
            .startswith("text/csv")
        )
    await service.close()
