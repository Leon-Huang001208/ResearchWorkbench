"""Asset workspace state, personal observations and alert regressions."""

import asyncio
from copy import deepcopy
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.research_web.asset_routes import ObservationRequest
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


@pytest.fixture(autouse=True)
def isolated_host_credentials(monkeypatch):
    """Keep asset fixture startup away from the host credential store."""
    import keyring

    values = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, account: values.get((service, account))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, account, value: values.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, account: values.pop((service, account), None)
    )


def test_tinysoft_canonical_asset_query_translates_cycle_and_adjustment(monkeypatch):
    import sys

    from app.research_web.datahub import providers_cjpy
    from app.research_web.datahub.contracts import BusinessQuery

    calls = []

    def market_data(**kwargs):
        calls.append(kwargs)
        return [{"date": "2026-10-20", "close": 10}]

    monkeypatch.setattr(providers_cjpy, "_client", lambda token: object())
    monkeypatch.setitem(sys.modules, "cjpy", SimpleNamespace(get_market_data=market_data))
    providers_cjpy._sync_query(
        BusinessQuery(
            capability="market_bars",
            source="tinysoft",
            parameters={
                "asset": "603986.SH",
                "asset_type": "stock",
                "frequency": "daily",
                "adjustment": "qfq",
                "start_date": "2026-10-01",
                "end_date": "2026-10-20",
            },
        ),
        "isolated-test-token",
    )
    assert calls[0]["cycle"] == "day"
    assert calls[0]["rate"] == "前复权"


class ObservationWindAdapter:
    """Only replaces the vendor boundary; Broker and snapshots remain real."""

    def __init__(self):
        self.calls = []
        self.fail = False
        self.started = Event()
        self.release = Event()
        self.block = False

    def is_available(self):
        return True

    def close(self):
        return None

    def _frame(self, method, kwargs, values):
        self.calls.append((method, kwargs))
        self.started.set()
        if self.block:
            assert self.release.wait(2), "fixture release timed out"
        if self.fail:
            raise ValueError("private vendor diagnostic must not leak")
        return pd.DataFrame([{"code": "600519.SH", **values}])

    def fetch_market_snapshot(self, **kwargs):
        return self._frame("snapshot", kwargs, {"trade_date": "2026-09-11", "close": 1500})

    def fetch_daily_quotes(self, **kwargs):
        return self._frame("history", kwargs, {"date": "2026-09-11", "close": 1500})

    def fetch_financial_statements(self, **kwargs):
        return self._frame("financials", kwargs, {"trade_date": "2026-09-11", "revenue": 12})

    def fetch_margin_trading(self, **kwargs):
        return self._frame("margin", kwargs, {"date": "2026-09-11", "margin_balance": 10})

    def fetch_holder_data(self, **kwargs):
        return self._frame(
            "holders", kwargs, {"report_date": kwargs["report_date"], "holder_num": 3}
        )


@pytest.fixture
def wind_workspace(tmp_path, monkeypatch):
    from app.research_web.asset_workspace import AssetWorkspace
    from app.research_web.datahub import DataHub, catalog, providers_wind

    monkeypatch.setattr(
        catalog, "_dependency_ready", lambda source_id, dependencies: source_id == "wind"
    )
    service = SimpleNamespace(store=Store(tmp_path), notify=lambda: None)
    service.datahub = DataHub(service.store)
    service.asset_workspace = AssetWorkspace(service)
    monkeypatch.setattr(
        service.datahub.connections,
        "statuses",
        lambda: {
            "wind": {
                "configured": True,
                "credential_store_available": True,
                "preferred_adapter": "excel",
            }
        },
    )
    adapter = ObservationWindAdapter()
    monkeypatch.setattr(providers_wind, "_make_adapter", lambda: adapter)
    sid = service.store.create("fingpt", "asset provider contract")["id"]
    return service, sid, adapter


async def _observe_wind(service, sid, section, **changes):
    body = ObservationRequest(
        **{
            "session_id": sid,
            "asset": "600519.SH",
            "asset_type": "stock",
            "source": "wind",
            "sections": [section],
            "start_date": "2026-09-01",
            "end_date": "2026-09-11",
            **changes,
        }
    )
    item = await service.asset_workspace.create_observation(body, f"contract:{section}")
    await asyncio.wait_for(service.asset_workspace.tasks[item["id"]], 2)
    return service.asset_workspace.observation(item["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("section", ["overview", "history", "financials", "margin", "holders"])
async def test_observation_uses_real_broker_wind_and_public_metadata(wind_workspace, section):
    service, sid, adapter = wind_workspace
    item = await _observe_wind(service, sid, section)
    block = item["blocks"][section]
    assert block["status"] == "complete", block
    dataset = block["dataset"]
    assert adapter.calls
    assert dataset["fields"]
    assert dataset["coverage"]
    assert dataset["retrieved_at"]
    assert item["request_parameters"] == {
        "start_date": "2026-09-01",
        "end_date": "2026-09-11",
        "frequency": "daily",
        "adjustment": "qfq",
    }
    assert "request" not in item
    assert "authorization_fingerprint" not in dataset
    if section in {"overview", "history"}:
        assert dataset["query"]["parameters"]["asset_type"] == "stock"
        assert dataset["fields"]["price" if section == "overview" else "close"]["currency"] == "CNY"
    if section == "financials":
        assert dataset["query"]["parameters"] == {
            "asset": "600519.SH",
            "statements": ["indicators"],
            "periods": [],
        }
        assert dataset["provider_query"]["parameters"]["statements"] == ["metrics"]
        assert adapter.calls == [("financials", {"codes": ["600519.SH"], "report_date": None})]
        assert any("最新一期" in limitation for limitation in dataset["limitations"])
    if section == "holders":
        assert dataset["query"]["parameters"] == {
            "asset": "600519.SH",
            "dataset": "holder_data",
            "end_date": "2026-09-11",
        }
        assert adapter.calls == [("holders", {"codes": ["600519.SH"], "report_date": "2026-09-11"})]
    await service.datahub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_type", ["index", "etf"])
async def test_observation_preserves_asset_type_and_wind_rejection(wind_workspace, asset_type):
    service, sid, adapter = wind_workspace
    item = await _observe_wind(service, sid, "history", asset_type=asset_type)
    block = item["blocks"]["history"]
    assert block["status"] == "unavailable"
    assert block["failure_code"] == "data_not_equivalent"
    assert block["dataset"]["query"]["parameters"]["asset_type"] == asset_type
    assert adapter.calls == []
    await service.datahub.close()


@pytest.mark.asyncio
async def test_observation_refresh_is_independent_and_preserves_previous_snapshot(wind_workspace):
    service, sid, adapter = wind_workspace
    item = await _observe_wind(service, sid, "overview", sections=["overview", "history"])
    workspace = service.asset_workspace
    original_id = item["blocks"]["overview"]["dataset"]["dataset_id"]
    history_id = item["blocks"]["history"]["dataset"]["dataset_id"]
    first = await workspace.refresh_block(item["id"], "overview", "refresh-contract-1")
    assert first["session_id"] == sid
    await asyncio.wait_for(asyncio.gather(*list(workspace.tasks.values())), 2)
    refreshed = workspace.observation(item["id"])
    new_id = refreshed["blocks"]["overview"]["dataset"]["dataset_id"]
    assert original_id != new_id
    assert refreshed["blocks"]["history"]["dataset"]["dataset_id"] == history_id
    assert service.datahub.detail(sid, original_id)["dataset_id"] == original_id
    repeated = await workspace.refresh_block(item["id"], "overview", "refresh-contract-1")
    assert repeated["blocks"]["overview"]["dataset"]["dataset_id"] == new_id
    assert len(adapter.calls) == 3
    adapter.fail = True
    await workspace.refresh_block(item["id"], "overview", "refresh-contract-2")
    await asyncio.wait_for(asyncio.gather(*list(workspace.tasks.values())), 2)
    failed = workspace.observation(item["id"])["blocks"]["overview"]
    assert failed["status"] == "unavailable"
    assert failed["failure_code"] == "wind_provider_error"
    assert failed["dataset"]["dataset_id"] == new_id
    assert "private vendor" not in str(failed)
    assert len(adapter.calls) == 4
    await service.datahub.close()


@pytest.mark.asyncio
async def test_observation_refresh_rejects_inflight_duplicate_and_recovers_restart(wind_workspace):
    from app.research_web.asset_workspace import AssetWorkspace
    from app.research_web.store import StoreError

    service, sid, adapter = wind_workspace
    item = await _observe_wind(service, sid, "overview", sections=["overview", "history"])
    adapter.block = True
    adapter.started.clear()
    workspace = service.asset_workspace
    await workspace.refresh_block(item["id"], "overview", "refresh-inflight-1")
    for _ in range(100):
        if adapter.started.is_set():
            break
        await asyncio.sleep(0.001)
    assert adapter.started.is_set()
    replay = await workspace.refresh_block(item["id"], "overview", "refresh-inflight-1")
    assert replay["blocks"]["overview"]["status"] == "loading"
    with pytest.raises(StoreError) as error:
        await workspace.refresh_block(item["id"], "overview", "refresh-inflight-2")
    assert error.value.status == 409
    with pytest.raises(StoreError) as other_block_error:
        await workspace.refresh_block(item["id"], "history", "refresh-inflight-3")
    assert other_block_error.value.status == 409
    adapter.release.set()
    await asyncio.wait_for(asyncio.gather(*list(workspace.tasks.values())), 2)
    row = service.store.data["asset_observations"][item["id"]]
    row["blocks"]["overview"]["status"] = "loading"
    row["status"] = "running"
    recovered = AssetWorkspace(service).observation(item["id"])
    assert recovered["blocks"]["overview"]["status"] == "unavailable"
    assert recovered["blocks"]["overview"]["failure_code"] == "interrupted"
    assert recovered["status"] == "partial"
    await service.datahub.close()


@pytest.mark.asyncio
async def test_wind_observation_does_not_overlap_its_own_blocks(wind_workspace):
    service, sid, adapter = wind_workspace
    item = await _observe_wind(
        service,
        sid,
        "overview",
        sections=["overview", "history", "financials", "margin", "holders"],
    )
    assert item["status"] == "complete", item
    assert [method for method, kwargs in adapter.calls] == [
        "snapshot",
        "history",
        "financials",
        "margin",
        "holders",
    ]
    await service.datahub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["tinysoft", "akshare"])
async def test_single_capacity_source_blocks_are_not_started_concurrently(tmp_path, source):
    from app.research_web.asset_workspace import AssetWorkspace

    store = Store(tmp_path)
    sid = store.create("fingpt", "isolated source scheduling")["id"]
    active = 0
    peak = 0

    async def query(*args, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"status": "empty", "row_count": 0, "sample": []}

    service = SimpleNamespace(
        store=store, datahub=SimpleNamespace(query=query), notify=lambda: None
    )
    workspace = AssetWorkspace(service)
    await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            source=source,
            sections=["overview", "history"],
        ),
        "single-capacity-scheduling",
    )
    await asyncio.gather(*list(workspace.tasks.values()))
    assert peak == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["wind", "auto"])
async def test_cancelled_sequential_observation_settles_pending_blocks_and_allows_refresh(
    wind_workspace, source
):
    service, sid, adapter = wind_workspace
    workspace = service.asset_workspace
    adapter.block = True
    item = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="600519.SH",
            asset_type="stock",
            source=source,
            sections=["overview", "history"],
            start_date="2026-09-01",
            end_date="2026-09-11",
        ),
        "cancel-sequential-observation",
    )
    task = workspace.tasks[item["id"]]
    for _ in range(100):
        if adapter.started.is_set():
            break
        await asyncio.sleep(0.001)
    assert adapter.started.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    adapter.release.set()
    await asyncio.gather(*list(service.datahub.tasks.values()))
    cancelled = workspace.observation(item["id"])
    assert cancelled["status"] == "cancelled"
    assert all(
        block["status"] == "unavailable" and block["failure_code"] == "cancelled"
        for block in cancelled["blocks"].values()
    )
    persisted = Store(service.store.root).data["asset_observations"][item["id"]]
    assert persisted["blocks"]["history"]["status"] == "unavailable"
    assert [method for method, _ in adapter.calls] == ["snapshot"]
    await workspace.refresh_block(item["id"], "history", "retry-cancelled-history")
    await asyncio.gather(*list(workspace.tasks.values()))
    assert workspace.observation(item["id"])["blocks"]["history"]["status"] == "complete"
    await service.datahub.close()


@pytest.mark.asyncio
async def test_cancel_before_observation_task_starts_settles_all_blocks(wind_workspace):
    service, sid, adapter = wind_workspace
    workspace = service.asset_workspace
    item = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="600519.SH",
            asset_type="stock",
            source="wind",
            sections=["overview", "history"],
        ),
        "cancel-before-task-starts",
    )
    task = workspace.tasks[item["id"]]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    cancelled = workspace.observation(item["id"])
    assert cancelled["status"] == "cancelled"
    assert all(
        block["status"] == "unavailable" and block["failure_code"] == "cancelled"
        for block in cancelled["blocks"].values()
    )
    assert adapter.calls == []
    await service.datahub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("shared_store", [True, False])
async def test_workspace_construction_preserves_active_observation_owner(
    wind_workspace, shared_store
):
    from app.research_web.asset_workspace import AssetWorkspace

    service, sid, adapter = wind_workspace
    workspace = service.asset_workspace
    adapter.block = True
    item = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="600519.SH",
            asset_type="stock",
            source="wind",
            sections=["overview"],
        ),
        "constructor-active-owner",
    )
    task = workspace.tasks[item["id"]]
    try:
        duplicate = AssetWorkspace(
            SimpleNamespace(store=service.store if shared_store else Store(service.store.root))
        )
        assert duplicate.observation(item["id"])["blocks"]["overview"]["status"] == "loading"
        assert workspace.observation(item["id"])["blocks"]["overview"]["status"] == "loading"
        assert (
            Store(service.store.root).data["asset_observations"][item["id"]]["status"] == "running"
        )
    finally:
        adapter.release.set()
        await task
        await service.datahub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_then_fail", [False, True])
async def test_refresh_save_failure_rolls_back_admission_and_allows_new_key(
    wind_workspace, monkeypatch, write_then_fail
):
    from app.research_web.store import StoreError

    service, sid, adapter = wind_workspace
    workspace = service.asset_workspace
    item = await _observe_wind(service, sid, "overview")
    before = deepcopy(service.store.data["asset_observations"][item["id"]])
    save = service.store.save

    def save_failed():
        if write_then_fail:
            save()
        raise StoreError("fixture persistence failure")

    monkeypatch.setattr(service.store, "save", save_failed)
    with pytest.raises(StoreError):
        await workspace.refresh_block(item["id"], "overview", "refresh-save-failed")
    assert len(adapter.calls) == 1
    assert not any(not task.done() for task in workspace.tasks.values())
    assert service.store.data["asset_observations"][item["id"]] == before
    monkeypatch.setattr(service.store, "save", save)
    await workspace.refresh_block(item["id"], "overview", "refresh-save-recovered")
    await asyncio.gather(*list(workspace.tasks.values()))
    assert workspace.observation(item["id"])["blocks"]["overview"]["status"] == "complete"
    assert len(adapter.calls) == 2
    await service.datahub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["error", "invalid", "unexpected"])
async def test_observation_never_marks_provider_error_or_unknown_status_complete(
    wind_workspace, status
):
    service, sid, _ = wind_workspace

    async def invalid_result(*args):
        return {"status": status, "sample": [], "limitations": ["row_limit"]}

    service.datahub.query = invalid_result
    item = await service.asset_workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="600519.SH", asset_type="stock", sections=["overview"]
        ),
        "provider-error-status",
    )
    await service.asset_workspace.tasks[item["id"]]
    result = service.asset_workspace.observation(item["id"])
    assert result["blocks"]["overview"]["status"] == "error"
    assert result["blocks"]["overview"]["failure_code"] == "row_limit"
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_observation_dataset_read_failure_is_error_and_not_complete(
    wind_workspace, monkeypatch
):
    service, sid, _ = wind_workspace

    def unreadable_dataset(*args):
        raise OSError("private filesystem diagnostic")

    monkeypatch.setattr(service.datahub, "rows", unreadable_dataset)
    item = await _observe_wind(service, sid, "overview")
    assert item["status"] == "failed"
    assert item["blocks"]["overview"]["status"] == "error"
    assert item["blocks"]["overview"]["failure_code"] == "query_failed"
    assert "private filesystem" not in str(item)
    await service.datahub.close()


@pytest.mark.asyncio
async def test_observation_does_not_downgrade_or_chunk_wind_calendar_limit(wind_workspace):
    service, sid, adapter = wind_workspace
    item = await _observe_wind(service, sid, "history", start_date="2026-06-01")
    block = item["blocks"]["history"]
    assert block["status"] == "unavailable"
    assert block["failure_code"] == "workload_too_large"
    assert block["dataset"]["requested_range"] == {
        "start_date": "2026-06-01",
        "end_date": "2026-09-11",
    }
    assert adapter.calls == []
    await service.datahub.close()


def test_observation_block_refresh_http_contract(api):
    client, _ = api
    created = client.post(
        "/api/research/assets/observations",
        json={"asset": "600519.SH", "asset_type": "stock", "sections": ["overview", "history"]},
        headers={"Idempotency-Key": "refresh-http-observation"},
    ).json()
    _wait(client, created["id"])
    endpoint = f"/api/research/assets/observations/{created['id']}/blocks"
    response = client.post(
        f"{endpoint}/overview/refresh", headers={"Idempotency-Key": "refresh-http-request"}
    )
    assert response.status_code == 202, response.text
    assert response.json()["id"] == created["id"]
    assert response.json()["session_id"] == created["session_id"]
    _wait(client, created["id"])
    assert (
        client.post(
            f"{endpoint}/overview/refresh", headers={"Idempotency-Key": "refresh-http-request"}
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"{endpoint}/history/refresh", headers={"Idempotency-Key": "refresh-http-request"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{endpoint}/holders/refresh", headers={"Idempotency-Key": "refresh-no-holder"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{endpoint}/unknown/refresh", headers={"Idempotency-Key": "refresh-unknown"}
        ).status_code
        == 422
    )


class NativeFixture:
    async def rpc(self, method, payload):
        if method == "host.describe":
            return {"version": "fixture", "provider": "fixture", "cwd": payload.get("cwd")}
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": True}}}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def api(tmp_path: Path):
    service = ResearchService(NativeFixture(), Store(tmp_path))

    async def query(sid, call_id, request):
        capability = request.capability
        if capability == "market_snapshot":
            return {
                "dataset_id": "11111111-1111-1111-1111-111111111111",
                "name": "贵州茅台快照",
                "capability": capability,
                "source": "akshare",
                "provider": "akshare",
                "status": "snapshot",
                "row_count": 1,
                "as_of": "2026-09-05T07:00:00+00:00",
                "actual_range": {"start_date": None, "end_date": None},
                "missing": [],
                "limitations": [],
                "files": [],
                "sample": [{"asset": "600519", "price": 1500.0, "change_pct": 2.1}],
            }
        if capability == "market_bars":
            return {
                "dataset_id": "22222222-2222-2222-2222-222222222222",
                "name": "贵州茅台历史行情",
                "capability": capability,
                "source": "akshare",
                "provider": "akshare",
                "status": "complete",
                "row_count": 2,
                "as_of": "2026-09-05",
                "actual_range": {"start_date": "2026-09-04", "end_date": "2026-09-05"},
                "missing": [],
                "limitations": [],
                "files": [],
                "sample": [
                    {"date": "2026-09-04", "close": 1490.0, "volume": 10},
                    {"date": "2026-09-05", "close": 1500.0, "volume": 11},
                ],
            }
        raise ValueError("provider unavailable")

    service.datahub.query = query
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service


def _wait(client, observation_id):
    for _ in range(50):
        item = client.get(f"/api/research/assets/observations/{observation_id}").json()
        if item["status"] != "running":
            return item
    return item


def test_asset_observation_tracks_each_block_and_freezes_handoff_context(api):
    client, _ = api
    response = client.post(
        "/api/research/assets/observations",
        json={
            "asset": "600519.SH",
            "asset_type": "stock",
            "sections": ["overview", "history", "financials"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
        headers={"Idempotency-Key": "asset-observation-0001"},
    )
    assert response.status_code == 202, response.text
    repeated = client.post(
        "/api/research/assets/observations",
        json={
            "asset": "600519.SH",
            "asset_type": "stock",
            "sections": ["overview", "history", "financials"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
        headers={"Idempotency-Key": "asset-observation-0001"},
    )
    assert repeated.json()["id"] == response.json()["id"]

    item = _wait(client, response.json()["id"])
    assert item["status"] == "partial"
    assert item["blocks"]["overview"]["status"] == "complete"
    assert item["blocks"]["history"]["status"] == "complete"
    assert item["blocks"]["financials"]["status"] == "error"
    assert item["dataset_ids"] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    assert "sample" not in item["blocks"]["overview"]["dataset"]


def test_watchlist_notes_and_alert_false_to_true_deduplication(api):
    client, service = api
    watchlist = client.post("/api/research/watchlists", json={"name": "核心观察"}).json()
    added = client.post(
        f"/api/research/watchlists/{watchlist['id']}/items",
        json={"asset": "600519.SH", "asset_type": "stock", "name": "贵州茅台"},
    )
    assert added.status_code == 201
    duplicate = client.post(
        f"/api/research/watchlists/{watchlist['id']}/items",
        json={"asset": "600519.SH", "asset_type": "stock", "name": "贵州茅台"},
    )
    assert duplicate.status_code == 409

    note = client.post(
        "/api/research/asset-notes",
        json={"asset": "600519.SH", "text": "关注渠道库存。"},
    ).json()
    patched = client.patch(
        f"/api/research/asset-notes/{note['id']}", json={"text": "关注渠道库存与批价。"}
    ).json()
    assert patched["text"].endswith("批价。")

    alert = client.post(
        "/api/research/asset-alerts",
        json={
            "asset": "600519.SH",
            "field": "price",
            "operator": "gte",
            "threshold": 1499,
            "cooldown_minutes": 60,
        },
    ).json()
    first = service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1500.0, "as_of": "2026-09-05"}
    )
    second = service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1501.0, "as_of": "2026-09-05"}
    )
    assert len(first) == 1
    assert second == []
    assert (
        client.get("/api/research/asset-notifications").json()["items"][0]["alert_id"]
        == alert["id"]
    )

    # stale/unavailable never trigger; a false result resolves the active edge.
    assert (
        service.asset_workspace.evaluate_alerts(
            "600519.SH", {"status": "unavailable", "price": 1600.0}
        )
        == []
    )
    service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1400.0, "as_of": "2026-09-05"}
    )
    assert service.store.data["asset_alerts"][alert["id"]]["condition_active"] is False


def test_personal_asset_resources_reject_unknown_ids_and_bad_polling(api):
    client, _ = api
    assert (
        client.patch(
            "/api/research/asset-notes/00000000-0000-0000-0000-000000000000",
            json={"text": "x"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/research/watchlists", json={"name": "x", "polling_minutes": 10}
        ).status_code
        == 422
    )
