"""Account-owned history jobs, immutable evidence and cancellation contracts."""

import asyncio
import json
import sys
import threading
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.research_web.asset_routes import HistoryJobRequest
from app.research_web.asset_workspace import AssetWorkspace
from app.research_web.datahub.adjustment_contract import contract_metadata
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.store import Store, StoreError


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    """Every host fixture uses memory; unexpected OS credential access fails closed."""
    import keyring

    from app.research_web import credential_backend
    from app.research_web.datahub import connections

    class MemoryCredentials:
        def __init__(self):
            self.values = {}

        def get_password(self, service, account):
            return self.values.get((service, account))

        def set_password(self, service, account, value):
            self.values[(service, account)] = value

        def delete_password(self, service, account):
            self.values.pop((service, account), None)

    def deny(*_args, **_kwargs):
        pytest.fail("history tests must not access host credentials")

    monkeypatch.setattr(connections, "default_credential_backend", MemoryCredentials)
    monkeypatch.setattr(credential_backend, "default_credential_backend", MemoryCredentials)
    for backend in (
        credential_backend.SystemKeyringBackend,
        credential_backend.PrivateFileCredentialBackend,
    ):
        monkeypatch.setattr(backend, "__init__", deny)
        for method in ("get_password", "set_password", "delete_password"):
            monkeypatch.setattr(backend, method, deny)
    for method in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, method, deny)


class HistoryHub:
    """Deterministic supplier boundary; snapshot IO remains real."""

    def __init__(self, store):
        self.snapshots = Snapshots(store)
        self.calls = []
        self.block = None
        self.entered = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.market_rows = None

    def source_configuration_digest(self, source):
        return "a" * 64

    def _authorize_query(self, sid, query, **kwargs):
        return None

    async def query(self, sid, call_id, query):
        self.calls.append(query)
        p = query.parameters
        series = p.get("series")
        if series == "adjustment_metadata":
            rows = [contract_metadata()]
        elif series == "listing_date":
            rows = [{"asset": p["assets"][0], "listing_date": "1999-11-10"}]
        elif series == "adjustment_factors":
            rows = [
                {
                    "asset": p["assets"][0],
                    "date": d,
                    "factor": 1 if d == "1999-11-10" else 2,
                    "listing_date": "1999-11-10",
                }
                for d in p["dates"]
            ]
        else:
            if self.block is not None:
                self.entered.set()
                await self.block.wait()
            rows = (
                self.market_rows(p)
                if self.market_rows
                else [
                    {
                        "date": p["end_date"],
                        "asset": p["asset"],
                        "open": 10,
                        "high": 12,
                        "low": 9,
                        "close": 11,
                        "volume": 100,
                    }
                ]
            )
        result = Result(
            rows=rows,
            raw=[json.dumps(rows).encode()],
            status="complete",
            pagination_complete=True,
            provider_id="tinysoft",
        )
        return self.snapshots.publish(
            sid, query, result, request_query=query, authorization_fingerprint="a" * 64
        )

    async def cancel(self, sid, call_id):
        self.cancelled.set()
        if self.block is not None:
            await self.block.wait()

    def detail(self, sid, did):
        return self.snapshots.detail(sid, did)


def workspace(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "history")["id"]
    hub = HistoryHub(store)
    service = SimpleNamespace(store=store, datahub=hub, notify=lambda: None)
    ws = AssetWorkspace(service)
    oid = "11111111-1111-4111-8111-111111111111"
    store.data["asset_observations"][oid] = {
        "id": oid,
        "session_id": sid,
        "asset": "600000.SH",
        "asset_type": "stock",
        "source": "tinysoft",
        "status": "complete",
        "updated_at": 0,
        "request": {"end_date": "2026-10-20"},
        "blocks": {"history": {"status": "complete", "dataset": None}},
    }
    store.save()
    return ws, hub, oid


async def settle(ws):
    await asyncio.gather(*list(ws.history_jobs.tasks.values()))


@pytest.mark.asyncio
async def test_explicit_new_quote_cutoff_builds_new_version_without_rewriting_old_request(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    first = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="all", adjustment="qfq"), "old-cutoff"
    )
    await settle(ws)
    old_dataset = ws.observation(oid)["blocks"]["history"]["dataset"]
    second = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="all", adjustment="qfq", as_of="2026-10-21"), "new-cutoff"
    )
    await settle(ws)
    latest = ws.observation(oid)["blocks"]["history"]["dataset"]
    assert ws.history_jobs.get(oid, first["id"])["state"] == "completed"
    assert ws.history_jobs.get(oid, second["id"])["state"] == "completed"
    assert latest["asset_history"]["requested_as_of"] == "2026-10-21"
    assert old_dataset["asset_history"]["requested_as_of"] == "2026-10-20"
    assert latest["dataset_id"] != old_dataset["dataset_id"]
    assert ws.observation(oid)["blocks"]["history"]["requested_range"]["end_date"] == "2026-10-21"
    assert ws.store.data["asset_observations"][oid]["request"]["end_date"] == "2026-10-20"
    assert hub.detail(ws.observation(oid)["session_id"], old_dataset["dataset_id"])


def test_older_history_cannot_replace_the_anchor_with_a_new_cutoff():
    with pytest.raises(ValueError):
        HistoryJobRequest(scope="older", adjustment="qfq", as_of="2026-10-21")


def test_research_dataset_summary_keeps_history_metadata_without_private_inputs(tmp_path):
    from app.research_web.datahub import DataHub

    store = Store(tmp_path)
    sid = store.create("fingpt", "summary")["id"]
    hub = DataHub(store)
    history = {
        "canonical_version": "history-v1",
        "factor_version": "factors-v1",
        "adjustment": "qfq",
        "anchor_date": "2026-10-21",
        "coverage": {"full_history": True},
        "raw_rows": [{"close": 10}] * 6001,
        "factors": {"2026-10-21": 1},
        "inputs": [{"dataset_id": "private-input"}],
        "configuration_digest": "a" * 64,
    }
    query = BusinessQuery(
        capability="market_bars", source="tinysoft", parameters={"asset": "600000.SH"}
    )
    result = Result(rows=[{"close": 10}], raw=[b"[]"], status="complete")
    manifest = hub.snapshots.publish(sid, query, result, asset_history=history)
    summary = hub.summaries(sid)[0]
    assert summary["asset_history"] == {
        key: value
        for key, value in history.items()
        if key not in {"raw_rows", "factors", "inputs", "configuration_digest"}
    }
    assert len(json.dumps(summary)) < 5000
    assert hub.detail(sid, manifest["dataset_id"])["asset_history"] == history


@pytest.mark.asyncio
async def test_recent_canonical_copy_and_preferences_are_account_scoped(tmp_path):
    ws, hub, oid = workspace(tmp_path / "one")
    body = HistoryJobRequest(scope="recent", adjustment="qfq")
    job = await ws.history_jobs.create(oid, body, "history-key-1")
    assert job["request_key"] == "history-key-1"
    assert (await ws.history_jobs.create(oid, body, "history-key-1"))["id"] == job["id"]
    await settle(ws)
    current = ws.observation(oid)
    assert current["history_job"]["state"] == "completed"
    ds = current["blocks"]["history"]["dataset"]
    assert ds["asset_history"]["adjustment"] == "qfq"
    assert ds["requested_range"] == {"start_date": "2024-10-20", "end_date": "2026-10-20"}
    assert all(
        q.parameters.get("adjustment") == "none" for q in hub.calls if q.capability == "market_bars"
    )
    sid = ws.store.data["asset_observations"][oid]["session_id"]
    target = ws.store.create("fingpt", "copy")["id"]
    copied = hub.snapshots.copy_selected(sid, target, [ds["dataset_id"]])[0]
    assert copied["asset_history"] == hub.detail(sid, ds["dataset_id"])["asset_history"]
    assert [x["sha256"] for x in copied["raw_files"]] == [
        x["sha256"] for x in hub.detail(sid, ds["dataset_id"])["raw_files"]
    ]
    assert ws.chart_preferences() == {"panels": ["volume", "macd"], "revision": 0}
    assert ws.set_chart_preferences(["rsi", "volume"])["revision"] == 1
    other, _, _ = workspace(tmp_path / "two")
    assert other.chart_preferences()["panels"] == ["volume", "macd"]


@pytest.mark.asyncio
async def test_first_history_job_and_preference_write_persist_across_restart(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    before = json.loads(ws.store.index.read_text())
    assert not {"asset_history_jobs", "asset_history_keys", "chart_preferences"} & before.keys()
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="qfq"), "persist-history-1"
    )
    await settle(ws)
    saved = json.loads(ws.store.index.read_text())
    assert saved["asset_history_jobs"][job["id"]]["state"] == "completed"
    assert saved["asset_history_keys"]
    assert "chart_preferences" not in saved
    # Explicitly saving the default panel choice is still a real preference write.
    preference = ws.set_chart_preferences(["volume", "macd"])
    assert preference["revision"] == 1
    await ws.close()
    restored_store = Store(tmp_path)
    restored = AssetWorkspace(
        SimpleNamespace(store=restored_store, datahub=HistoryHub(restored_store))
    )
    assert restored.chart_preferences() == preference
    assert restored.history_jobs.get(oid, job["id"])["state"] == "completed"
    assert (
        restored.observation(oid)["blocks"]["history"]["dataset"]
        == ws.observation(oid)["blocks"]["history"]["dataset"]
    )
    assert hub.calls
    await restored.close()


@pytest.mark.asyncio
async def test_older_requires_canonical_and_rejects_conflicting_idempotency(tmp_path):
    ws, _, oid = workspace(tmp_path)
    with pytest.raises(StoreError, match="规范历史"):
        await ws.history_jobs.create(
            oid, HistoryJobRequest(scope="older", adjustment="none"), "history-key-1"
        )
    await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
    )
    await settle(ws)
    with pytest.raises(StoreError):
        await ws.history_jobs.create(
            oid, HistoryJobRequest(scope="all", adjustment="none"), "history-key-1"
        )
    old = ws.observation(oid)["blocks"]["history"]["dataset"]
    await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="older", adjustment="none"), "history-key-2"
    )
    await settle(ws)
    new = ws.observation(oid)["blocks"]["history"]["dataset"]
    assert new["asset_history"]["requested_as_of"] == "2026-10-20"
    assert new["asset_history"]["scanned_start"] == "2020-10-20"
    assert old["dataset_id"] != new["dataset_id"]


@pytest.mark.asyncio
async def test_cancel_drains_before_terminal_and_refresh_is_exclusive(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    hub.block = asyncio.Event()
    created = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
    )
    await hub.entered.wait()
    with pytest.raises(StoreError):
        await ws.refresh_block(oid, "history", "refresh-key-1")
    result = await ws.history_jobs.cancel(oid, created["id"])
    assert result["state"] in {"cancelling", "draining"}
    await hub.cancelled.wait()
    assert ws.history_jobs.get(oid, created["id"])["state"] == "draining"
    hub.block.set()
    await settle(ws)
    assert ws.history_jobs.get(oid, created["id"])["state"] == "cancelled"
    assert ws.observation(oid)["blocks"]["history"]["dataset"] is None


def test_restart_interrupted_and_invalid_preferences(tmp_path):
    ws, _, oid = workspace(tmp_path)
    ws.store.data["asset_history_jobs"][oid] = {
        "id": oid,
        "observation_id": oid,
        "state": "running",
        "session_id": "none",
    }
    ws.store.save()
    restored = AssetWorkspace(ws.service)
    assert restored.history_jobs.get(oid, oid)["state"] == "interrupted"
    with pytest.raises(StoreError):
        ws.set_chart_preferences(["volume", "volume"])


@pytest.mark.asyncio
async def test_admission_and_pointer_save_failures_restore_old_state(tmp_path, monkeypatch):
    ws, hub, oid = workspace(tmp_path)
    original_save = ws.store.save
    monkeypatch.setattr(ws.store, "save", lambda: (_ for _ in ()).throw(StoreError("save failed")))
    with pytest.raises(StoreError):
        await ws.history_jobs.create(
            oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
        )
    assert not hub.calls and not ws.store.data["asset_history_jobs"]
    monkeypatch.setattr(ws.store, "save", original_save)
    await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
    )
    await settle(ws)
    old = ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"]
    failed_once = False

    def save():
        nonlocal failed_once
        pointer = ws.store.data["asset_observations"][oid]["blocks"]["history"]["dataset"][
            "dataset_id"
        ]
        if pointer != old and not failed_once:
            failed_once = True
            raise StoreError("save failed")
        original_save()

    monkeypatch.setattr(ws.store, "save", save)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="older", adjustment="none"), "history-key-2"
    )
    await settle(ws)
    assert ws.history_jobs.get(oid, job["id"])["state"] == "failed"
    assert ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"] == old
    assert (
        Store(tmp_path).data["asset_observations"][oid]["blocks"]["history"]["dataset"][
            "dataset_id"
        ]
        == old
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["generation", "authorization", "overlap"])
async def test_late_or_conflicting_chunk_cannot_replace_old_canonical(
    tmp_path, monkeypatch, change
):
    ws, hub, oid = workspace(tmp_path)

    def rows(p):
        return [
            {"date": d, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}
            for d in sorted({p["start_date"], p["end_date"]})
        ]

    hub.market_rows = rows
    await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
    )
    await settle(ws)
    old = ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"]
    original_query = hub.query

    async def changed(*args):
        result = await original_query(*args)
        if change == "generation":
            ws.store.data["asset_observations"][oid]["history_generation"] = "another-generation"
        elif change == "authorization":
            monkeypatch.setattr(hub, "source_configuration_digest", lambda _source: "changed")
        return result

    if change == "overlap":

        def conflict(p):
            values = rows(p)
            values[-1]["close"] = 12
            return values

        hub.market_rows = conflict
    else:
        monkeypatch.setattr(hub, "query", changed)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="older", adjustment="none"), "history-key-2"
    )
    await settle(ws)
    assert ws.history_jobs.get(oid, job["id"])["state"] == "failed"
    assert ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"] == old


@pytest.mark.asyncio
async def test_immediate_cancel_and_explicit_retry_reuse_frozen_completed_chunk(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-key-1"
    )
    await ws.history_jobs.cancel(oid, job["id"])
    await settle(ws)
    assert ws.history_jobs.get(oid, job["id"])["state"] == "cancelled"
    assert not hub.calls
    retry = await ws.history_jobs.create(
        oid,
        HistoryJobRequest(scope="recent", adjustment="none", retry_of=job["id"]),
        "history-key-2",
    )
    await settle(ws)
    assert ws.history_jobs.get(oid, retry["id"])["state"] == "completed"


def real_workspace(tmp_path, monkeypatch):
    """Replace only vendor SDK and credentials; execute actual Broker/Provider/IO."""
    from app.research_web.datahub import DataHub, catalog, providers_cjpy
    from app.research_web.datahub.adjustment_contract import FACTOR_DEFINITIONS

    ws, _, oid = workspace(tmp_path)
    hub = DataHub(ws.store)
    monkeypatch.setattr(catalog, "_dependency_status", lambda *_args: (True, None))
    status = {"configured": True, "secret_configured": True}
    monkeypatch.setattr(hub.connections, "statuses", lambda: {"tinysoft": dict(status)})
    monkeypatch.setattr(hub.connections, "source_status", lambda _source: dict(status))
    monkeypatch.setattr(hub.connections, "configuration_revision", lambda _source: "test-v1")
    monkeypatch.setattr(hub.connections, "read_source_secret", lambda _source: "synthetic-token")
    calls = []
    listing = "1999-11-10"

    def bars(**kwargs):
        calls.append(("bars", kwargs))
        start, end = date.fromisoformat(kwargs["start"]), date.fromisoformat(kwargs["end"])
        start = max(start, date.fromisoformat(listing))
        return [
            {
                "时间": (start + timedelta(days=i)).isoformat(),
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "vol": 100,
            }
            for i in range(max(0, (end - start).days + 1))
        ]

    def factors(**kwargs):
        calls.append(("factors", kwargs))
        return [
            {
                "截止日": d.replace("-", ""),
                "代码": "SH600000",
                "名称": "synthetic",
                "上市日期": listing,
                "复权因子": 1 if d == listing else 2,
            }
            for d in kwargs["date"]
        ]

    sdk = SimpleNamespace(
        get_market_data=bars,
        get_factor_data=factors,
        list_factors=lambda **_kwargs: [
            {"因子名称": k, "公式": v} for k, v in FACTOR_DEFINITIONS.items()
        ],
    )
    monkeypatch.setitem(sys.modules, "cjpy", sdk)
    monkeypatch.setattr(providers_cjpy, "_client", lambda _token: object())
    ws.service.datahub = hub
    return ws, hub, oid, calls, sdk, providers_cjpy


@pytest.mark.asyncio
async def test_real_broker_provider_all_over_5000_rows_fixed_anchor_and_copy(tmp_path, monkeypatch):
    ws, hub, oid, calls, _, _ = real_workspace(tmp_path, monkeypatch)
    try:
        job = await ws.history_jobs.create(
            oid, HistoryJobRequest(scope="all", adjustment="qfq"), "history-real-all"
        )
        await settle(ws)
        completed = ws.history_jobs.get(oid, job["id"])
        assert completed["state"] == "completed", completed
        current = ws.observation(oid)["blocks"]["history"]["dataset"]
        assert current["row_count"] > 5000
        assert current["asset_history"]["anchor_date"] == "2026-10-20"
        assert current["asset_history"]["coverage"]["listing_date"] == "1999-11-10"
        assert all(c[1]["rate"] == "不复权" for c in calls if c[0] == "bars")
        assert all(len(c[1]["date"]) <= 500 for c in calls if c[0] == "factors")
        sid = ws.store.data["asset_observations"][oid]["session_id"]
        records = json.loads(hub.snapshots.read(sid, current["dataset_id"], "rows.json"))
        assert records[0]["date"] == "1999-11-10" and records[0]["close"] == 5.5
        assert records[-1]["close"] == 11
        old = hub.list(sid)
        first = next(d for d in reversed(old) if d.get("snapshot_kind") == "asset_history")
        assert first["row_count"] < current["row_count"]
        assert hub.detail(sid, first["dataset_id"])["manifest_sha256"] == first["manifest_sha256"]
        copied_sid = ws.store.create("fingpt", "copy")["id"]
        copied = hub.copy_selected(sid, copied_sid, [current["dataset_id"]])[0]
        assert copied["asset_history"] == hub.detail(sid, current["dataset_id"])["asset_history"]
        assert hub.snapshots.read(
            copied_sid, copied["dataset_id"], "asset-history.json"
        ) == hub.snapshots.read(sid, current["dataset_id"], "asset-history.json")
        ws.store.data["sessions"][sid].update(deleted_at=1, native_deleted_at=1)
        ws.store.purge(sid)
        assert (
            json.loads(hub.snapshots.read(copied_sid, copied["dataset_id"], "rows.json")) == records
        )
        from app.research_web.datahub.security import directory, read_file
        from app.research_web.datahub.snapshots import sha

        with directory(
            ws.store.root, (".control", "snapshots", copied_sid, copied["dataset_id"]), private=True
        ) as fd:
            assert all(
                sha(read_file(fd, item["name"], private=True)) == item["sha256"]
                for item in copied["raw_files"]
            )
    finally:
        await ws.close()
        await hub.close()


@pytest.mark.asyncio
async def test_real_provider_cancel_waits_for_thread_and_close_stops_admission(
    tmp_path, monkeypatch
):
    ws, hub, oid, _, sdk, provider = real_workspace(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()
    original = sdk.get_market_data

    def blocked(**kwargs):
        started.set()
        release.wait(timeout=3)
        return original(**kwargs)

    sdk.get_market_data = blocked
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-real-cancel"
    )
    try:
        for _ in range(500):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        await ws.history_jobs.cancel(oid, job["id"])
        await asyncio.sleep(0.01)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "draining"
        assert provider.active_futures() and hub.tasks
        closing = asyncio.create_task(ws.close())
        await asyncio.sleep(0)
        assert not closing.done()
        release.set()
        await closing
        assert not provider.active_futures() and not hub.tasks
        assert ws.history_jobs.get(oid, job["id"])["state"] == "cancelled"
        with pytest.raises(StoreError):
            await ws.history_jobs.create(
                oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-after-close"
            )
    finally:
        release.set()
        await ws.close()
        await hub.close()


@pytest.mark.asyncio
async def test_completed_chunks_survive_cancel_and_explicit_retry(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    boundary = asyncio.Event()
    first = True

    def rows(p):
        nonlocal first
        if first:
            first = False
            hub.block = boundary
        return [{"date": p["end_date"], "open": 10, "high": 12, "low": 9, "close": 11}]

    hub.market_rows = rows
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="all", adjustment="none"), "history-chunks-1"
    )
    await hub.entered.wait()
    assert ws.history_jobs.get(oid, job["id"])["progress"]["chunks_completed"] == 1
    first_interval = hub.calls[0].parameters.copy()
    await ws.history_jobs.cancel(oid, job["id"])
    await hub.cancelled.wait()
    boundary.set()
    await settle(ws)
    frozen_pointer = ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"]
    hub.block = None
    retry = await ws.history_jobs.create(
        oid,
        HistoryJobRequest(scope="all", adjustment="none", retry_of=job["id"]),
        "history-chunks-2",
    )
    await settle(ws)
    assert ws.history_jobs.get(oid, retry["id"])["state"] == "completed"
    assert sum(q.parameters == first_interval for q in hub.calls) == 1
    assert ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"] != frozen_pointer


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["factor_drift", "ipo_factor", "missing_first_bar"])
async def test_real_adjustment_gate_and_old_factor_revalidation(tmp_path, monkeypatch, fault):
    ws, hub, oid, _, sdk, _ = real_workspace(tmp_path, monkeypatch)
    factors = sdk.get_factor_data
    try:
        if fault == "factor_drift":
            await ws.history_jobs.create(
                oid, HistoryJobRequest(scope="recent", adjustment="qfq"), "history-factor-1"
            )
            await settle(ws)
            old = ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"]
        else:
            old = None

        def changed(**kwargs):
            values = factors(**kwargs)
            for value in values:
                if fault == "ipo_factor" and value["截止日"] == "19991110":
                    value["复权因子"] = 2
                elif fault == "factor_drift" and value["截止日"] != "19991110":
                    value["复权因子"] = 3
            return values

        sdk.get_factor_data = changed
        if fault == "missing_first_bar":
            original_bars = sdk.get_market_data
            sdk.get_market_data = lambda **kwargs: (
                [] if kwargs["start"] == kwargs["end"] == "1999-11-10" else original_bars(**kwargs)
            )
        job = await ws.history_jobs.create(
            oid,
            HistoryJobRequest(scope="older" if old else "recent", adjustment="qfq"),
            "history-factor-2",
        )
        await settle(ws)
        final = ws.history_jobs.get(oid, job["id"])
        assert final["state"] == "failed"
        pointer = ws.observation(oid)["blocks"]["history"]["dataset"]
        assert (pointer["dataset_id"] if pointer else None) == old
        if fault == "factor_drift":
            assert final["failure_code"] == "history_factor_version_changed"
    finally:
        await ws.close()
        await hub.close()


@pytest.mark.asyncio
async def test_deleted_session_jobs_drain_before_store_purge(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    hub.block = asyncio.Event()
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-purge-1"
    )
    await hub.entered.wait()
    sid = ws.store.data["asset_observations"][oid]["session_id"]
    ws.store.data["sessions"][sid].update(deleted_at=1, native_deleted_at=1)
    with pytest.raises(StoreError) as active:
        ws.store.purge(sid)
    assert active.value.code == "history_jobs_active"
    cancel = asyncio.create_task(ws.history_jobs.cancel_session(sid))
    await hub.cancelled.wait()
    assert ws.store.data["asset_history_jobs"][job["id"]]["state"] == "draining"
    hub.block.set()
    await cancel
    ws.store.purge(sid)
    assert not ws.store.data["asset_history_jobs"] and not ws.store.data["asset_history_keys"]


def test_http_payloads_reject_untrusted_controls_and_allow_empty_panels():
    from pydantic import ValidationError

    from app.research_web.asset_routes import ChartPreferencesRequest

    assert ChartPreferencesRequest(panels=[]).panels == []
    for values in (["MACD"], ["volume", "volume"], ["unknown"]):
        with pytest.raises(ValidationError):
            ChartPreferencesRequest(panels=values)
    for key, value in (
        ("source", "wind"),
        ("path", "/tmp"),
        ("anchor", "2020-01-01"),
        ("formula", "anything"),
    ):
        with pytest.raises(ValidationError):
            HistoryJobRequest(scope="recent", adjustment="qfq", **{key: value})


@pytest.mark.asyncio
async def test_duplicate_workspace_preserves_live_job_owner_and_close(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    hub.block = asyncio.Event()
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-owner-1"
    )
    await hub.entered.wait()
    duplicate = AssetWorkspace(SimpleNamespace(store=Store(tmp_path)))
    assert duplicate.history_jobs.get(oid, job["id"])["state"] == "running"
    await duplicate.history_jobs.close()
    assert ws.history_jobs.get(oid, job["id"])["state"] == "running"
    hub.block.set()
    await settle(ws)
    assert ws.history_jobs.get(oid, job["id"])["state"] == "completed"


@pytest.mark.asyncio
async def test_provider_deadline_retains_draining_and_can_be_cancelled(tmp_path, monkeypatch):
    ws, hub, oid, _, sdk, provider = real_workspace(tmp_path, monkeypatch)
    release = threading.Event()
    original = sdk.get_market_data

    def blocked(**kwargs):
        release.wait(timeout=3)
        return original(**kwargs)

    sdk.get_market_data = blocked
    monkeypatch.setattr(provider, "DEADLINE", 0.01)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-deadline-1"
    )
    try:
        for _ in range(500):
            if ws.history_jobs.get(oid, job["id"])["state"] == "draining":
                break
            await asyncio.sleep(0.001)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "draining"
        assert provider.active_futures()
        await ws.history_jobs.cancel(oid, job["id"])
        release.set()
        await settle(ws)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "cancelled"
        assert not provider.active_futures()
    finally:
        release.set()
        await ws.close()
        await hub.close()


def test_canonical_rows_validate_actual_cjpy_identity_ohlc_and_chunk_limit():
    from app.research_web.asset_history import normalize_rows

    interval = {"start_date": "2024-01-02", "end_date": "2024-01-02"}
    row = {
        "代码": "SH600000",
        "简称": "synthetic",
        "时间": "2024-01-02 00:00:00",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
    }
    assert normalize_rows([row], "600000.SH", interval)[0]["asset"] == "600000.SH"
    with pytest.raises(StoreError) as identity:
        normalize_rows([{**row, "代码": "SH600519"}], "600000.SH", interval)
    assert identity.value.code == "history_asset_mismatch"
    with pytest.raises(StoreError) as ohlc:
        normalize_rows([{**row, "high": 10}], "600000.SH", interval)
    assert ohlc.value.code == "history_ohlc_invalid"
    with pytest.raises(StoreError) as bound:
        normalize_rows([row] * 5001, "600000.SH", interval)
    assert bound.value.code == "history_chunk_row_limit"


@pytest.mark.asyncio
async def test_recent_uses_section_cutoff_and_two_natural_years(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    ws.store.data["asset_observations"][oid]["request"]["section_ranges"] = {
        "history": {"start_date": "1990-01-01", "end_date": "2024-02-29"}
    }
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none"), "history-natural-years"
    )
    await settle(ws)
    assert ws.history_jobs.get(oid, job["id"])["state"] == "completed"
    assert hub.calls[0].parameters["start_date"] == "2022-02-28"
    assert hub.calls[0].parameters["end_date"] == "2024-02-29"


@pytest.mark.asyncio
async def test_verified_pre_listing_interval_is_explicit_and_preserves_old_pointer(tmp_path):
    ws, _, oid = workspace(tmp_path)
    ws.store.data["asset_observations"][oid]["request"]["end_date"] = "1990-01-02"
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="qfq"), "history-before-listing"
    )
    await settle(ws)
    final = ws.history_jobs.get(oid, job["id"])
    assert final["failure_code"] == "history_before_listing"
    assert final["state"] == "failed" and final["retryable"] is False
    assert ws.observation(oid)["blocks"]["history"]["dataset"] is None


@pytest.mark.asyncio
async def test_canonical_adjustment_is_not_a_generic_vendor_cache_entry(tmp_path, monkeypatch):
    from app.research_web.datahub.contracts import BusinessQuery

    ws, hub, oid, calls, _, _ = real_workspace(tmp_path, monkeypatch)
    try:
        await ws.history_jobs.create(
            oid, HistoryJobRequest(scope="recent", adjustment="qfq"), "history-cache-isolation"
        )
        await settle(ws)
        sid = ws.store.data["asset_observations"][oid]["session_id"]
        did = ws.observation(oid)["blocks"]["history"]["dataset"]["dataset_id"]
        canonical = hub.detail(sid, did)
        before = len(calls)
        result = await hub.query(
            sid, "ordinary-vendor-query", BusinessQuery.model_validate(canonical["query"])
        )
        assert len(calls) > before
        assert result["dataset_id"] != did and result.get("snapshot_kind") != "asset_history"
        assert result["provider_query"]["parameters"]["adjustment"] == "qfq"
        hub.snapshots.receipt(
            sid,
            "old-canonical-cache",
            {
                "status": "completed",
                "fingerprint": BusinessQuery.model_validate(canonical["query"]).fingerprint(
                    include_refresh=True
                ),
                "dataset_id": did,
            },
        )
        with pytest.raises(StoreError) as conflict:
            await hub.query(
                sid, "old-canonical-cache", BusinessQuery.model_validate(canonical["query"])
            )
        assert conflict.value.code == "data_cache_not_equivalent"
    finally:
        await ws.close()
        await hub.close()


def test_history_source_is_explicit_and_old_clients_keep_tinysoft():
    assert HistoryJobRequest(scope="recent", adjustment="none").source == "tinysoft"
    assert HistoryJobRequest(scope="recent", adjustment="none", source="auto").source == "auto"
    with pytest.raises(ValueError):
        HistoryJobRequest(scope="recent", adjustment="qfq", source="auto")
    with pytest.raises(ValueError):
        HistoryJobRequest(scope="all", adjustment="none", source="auto")


def test_raw_history_requires_identity_units_and_maps_declared_turnover():
    from app.research_web.asset_history import normalize_raw_rows

    interval = {"start_date": "2026-10-01", "end_date": "2026-10-20"}
    rows = [
        {
            "asset": "600000.SH",
            "date": "2026-10-20",
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 100,
            "turnover": 1100,
        }
    ]
    fields = {
        k: {"unit": "currency_per_share", "currency": "CNY"}
        for k in ("open", "high", "low", "close")
    }
    fields.update(
        volume={"unit": "share", "currency": None}, turnover={"unit": "currency", "currency": "CNY"}
    )
    assert normalize_raw_rows(rows, "600000.SH", interval, fields)[0]["amount"] == 1100
    with pytest.raises(StoreError, match="单位"):
        normalize_raw_rows(rows, "600000.SH", interval, {})
    with pytest.raises(StoreError, match="身份"):
        normalize_raw_rows(
            [{k: v for k, v in rows[0].items() if k != "asset"}], "600000.SH", interval, fields
        )


@pytest.mark.asyncio
async def test_recent_auto_freezes_requested_source_and_actual_configuration(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none", source="auto"), "auto-recent-key"
    )
    await settle(ws)
    record = ws.store.data["asset_history_jobs"][job["id"]]
    assert record["source"] == "auto"
    assert set(record["source_configuration_digests"]) == {
        "tinysoft",
        "wind",
        "akshare",
        "baostock",
    }
    assert all(query.source == "auto" for query in hub.calls)
    # A supplier with no price-unit declaration cannot produce a canonical snapshot.
    assert ws.history_jobs.get(oid, job["id"])["failure_code"] == "history_unit_unverified"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source, fault",
    [
        ("auto", None),
        ("tinysoft", None),
        ("auto", "units"),
        ("auto", "security"),
        ("auto", "date"),
        ("auto", "conflict"),
        ("auto", "revoked"),
    ],
)
async def test_http_history_real_broker_executor_fallback_chain(
    tmp_path, monkeypatch, source, fault
):
    import httpx
    from fastapi import FastAPI

    from app.research_web.asset_routes import router
    from app.research_web.datahub import providers_akshare

    ws, hub, oid, calls, sdk, _ = real_workspace(tmp_path, monkeypatch)
    statuses = {
        "tinysoft": {"configured": True, "secret_configured": True},
        "wind": {"configured": True, "preferred_adapter": "excel"},
    }
    monkeypatch.setattr(hub.connections, "statuses", lambda: statuses)

    def failed_bars(**kwargs):
        calls.append(("failed-bars", kwargs))
        raise OSError("synthetic unavailability")

    sdk.get_market_data = failed_bars
    public_calls = []

    def invoke(query):
        public_calls.append(query)
        rows = [
            {
                "date": query.parameters["end_date"],
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "amount": 1100,
            }
        ]
        if fault == "conflict":
            rows.append({**rows[0], "close": 10.5})
        import pandas as pd

        result = providers_akshare._materialize(
            query, pd.DataFrame(rows), providers_akshare._normalize_sina_stock_bars
        )
        if fault == "units":
            result.fields["close"]["currency"] = None
        if fault == "security":
            result.rows[0]["asset"] = "000001.SZ"
        if fault == "date":
            result.rows[0]["date"] = "2026-10-21"
        if fault == "revoked":
            monkeypatch.setattr(hub.connections, "configuration_revision", lambda _: "revoked")
        return result

    monkeypatch.setattr(providers_akshare, "_invoke", invoke)
    app = FastAPI()
    app.include_router(router)
    app.state.research = ws.service
    ws.service.asset_workspace = ws
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture"
        ) as client:
            response = await client.post(
                f"/api/research/assets/observations/{oid}/history-jobs",
                json={"scope": "recent", "adjustment": "none", "source": source},
                headers={"Idempotency-Key": "http-fallback-01"},
            )
            assert response.status_code == 202, response.text
            job = response.json()
            await settle(ws)
            result = (
                await client.get(
                    f"/api/research/assets/observations/{oid}/history-jobs/{job['id']}"
                )
            ).json()
        assert not any(call[0] == "factors" for call in calls)
        if source == "tinysoft":
            assert result["state"] == "failed"
            assert public_calls == []
        elif fault:
            assert result["state"] == "failed", result
            assert ws.observation(oid)["blocks"]["history"]["dataset"] is None
            assert len(public_calls) == 1
        else:
            assert result["state"] == "completed", result
            assert len(public_calls) == 1
            dataset = ws.observation(oid)["blocks"]["history"]["dataset"]
            assert dataset["provider"] == "akshare"
            assert (
                hub.detail(ws.observation(oid)["session_id"], dataset["dataset_id"])["source_url"]
                == "https://akshare.akfamily.xyz/"
            )
            history = hub.detail(ws.observation(oid)["session_id"], dataset["dataset_id"])[
                "asset_history"
            ]
            assert history["canonical_version"] == "asset-history-raw-2"
            assert history["coverage"]["listing_date"] is None
            assert history["coverage"]["boundary_verified"] is False
            assert history["coverage"]["full_history"] is False
            assert history["raw_rows"][0]["amount"] == 1100
            attempts = history["inputs"][0]["manifest"]["attempted_sources"]
            assert any(
                a["source"] == "wind" and a["reason"] == "workload_too_large" for a in attempts
            )
            assert any(
                a["source"] == "tinysoft" and a["reason"] == "price_units_unverified"
                for a in attempts
            )
            assert not any(call[0] == "failed-bars" for call in calls)
    finally:
        await hub.close()


@pytest.mark.asyncio
async def test_auto_cancellation_drains_real_public_executor_and_retry_freezes_source(
    tmp_path, monkeypatch
):
    from app.research_web.datahub import providers_akshare
    from app.research_web.datahub.providers import Result

    ws, hub, oid, _, _sdk, _ = real_workspace(tmp_path, monkeypatch)
    statuses = {"tinysoft": {"configured": False}}
    monkeypatch.setattr(hub.connections, "statuses", lambda: statuses)
    entered, release = threading.Event(), threading.Event()

    def invoke(query):
        entered.set()
        assert release.wait(3), "fixture did not release public executor"
        return Result(
            rows=[],
            raw=[b"[]"],
            status="empty",
            pagination_complete=True,
            provider_id="akshare",
            fields={
                k: {"unit": "currency_per_share", "currency": "CNY"}
                for k in ("open", "high", "low", "close")
            },
        )

    monkeypatch.setattr(providers_akshare, "_invoke", invoke)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none", source="auto"), "auto-cancel-key"
    )
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        cancelled = await ws.history_jobs.cancel(oid, job["id"])
        await asyncio.sleep(0.01)
        assert cancelled["state"] == "cancelling"
        assert ws.history_jobs.active(oid)
        assert providers_akshare.active_futures()
        release.set()
        await settle(ws)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "cancelled"
        assert not providers_akshare.active_futures()
        assert ws.observation(oid)["blocks"]["history"]["dataset"] is None
        with pytest.raises(StoreError) as error:
            await ws.history_jobs.create(
                oid,
                HistoryJobRequest(
                    scope="recent", adjustment="none", source="baostock", retry_of=job["id"]
                ),
                "auto-retry-changed",
            )
        assert error.value.code == "history_retry_invalid"
    finally:
        release.set()
        await settle(ws)
        await hub.close()


def test_reading_legacy_job_does_not_backfill_source_on_disk(tmp_path):
    ws, _, oid = workspace(tmp_path)
    row = {
        "id": "legacy",
        "observation_id": oid,
        "state": "failed",
        "scope": "recent",
        "adjustment": "none",
        "failure_code": "provider_error",
    }
    ws.store.data["asset_history_jobs"]["legacy"] = row
    ws.store.save()
    before = (tmp_path / "index.json").read_bytes()
    assert ws.history_jobs.get(oid, "legacy")["source"] == "tinysoft"
    assert "source" not in row
    assert (tmp_path / "index.json").read_bytes() == before


@pytest.mark.parametrize("extra", [{"code": "000001.SZ"}, {"日期": "2026-10-19"}])
def test_raw_history_rejects_conflicting_identity_or_date_aliases(extra):
    from app.research_web.asset_history import normalize_raw_rows

    fields = {
        key: {"unit": "currency_per_share", "currency": "CNY"}
        for key in ("open", "high", "low", "close")
    }
    row = {
        "asset": "600000.SH",
        "date": "2026-10-20",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        **extra,
    }
    with pytest.raises(StoreError):
        normalize_raw_rows(
            [row], "600000.SH", {"start_date": "2026-10-01", "end_date": "2026-10-20"}, fields
        )


@pytest.mark.parametrize(
    "key, alias, value, alias_unit",
    [
        ("open", "开盘", 999, "valid"),
        ("volume", "vol", 999, "valid"),
        ("amount", "成交额", 999, "valid"),
        ("amount", "turnover", 999, "valid"),
        ("volume", "vol", 100, "unknown"),
        ("amount", "成交额", 1100, "wrong"),
        ("open", "开盘", 10, "unknown"),
    ],
)
def test_raw_history_checks_every_numeric_alias_and_its_declared_unit(
    key, alias, value, alias_unit
):
    from app.research_web.asset_history import normalize_raw_rows

    fields = {
        name: {"unit": "currency_per_share", "currency": "CNY"}
        for name in ("open", "high", "low", "close")
    }
    fields.update(
        volume={"unit": "share", "currency": None}, amount={"unit": "currency", "currency": "CNY"}
    )
    fields[alias] = (
        dict(fields[key])
        if alias_unit == "valid"
        else ({"unit": "lot", "currency": None} if alias_unit == "wrong" else {})
    )
    row = {
        "asset": "600000.SH",
        "date": "2026-10-20",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "volume": 100,
        "amount": 1100,
        alias: value,
    }
    with pytest.raises(StoreError):
        normalize_raw_rows(
            [row], "600000.SH", {"start_date": "2026-10-01", "end_date": "2026-10-20"}, fields
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_during_drain", [False, True])
async def test_history_deadline_keeps_owned_call_draining_until_real_executor_exits(
    tmp_path, monkeypatch, cancel_during_drain
):
    import app.research_web.datahub as datahub_module
    from app.research_web.datahub import providers_akshare
    from app.research_web.datahub.providers import Result

    ws, hub, oid, _, _sdk, _ = real_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(hub.connections, "statuses", lambda: {"tinysoft": {"configured": False}})
    monkeypatch.setattr(datahub_module, "TOTAL_DEADLINE", 0.03)
    entered, release = threading.Event(), threading.Event()

    def invoke(_query):
        entered.set()
        assert release.wait(3)
        return Result(
            rows=[], raw=[b"[]"], status="empty", pagination_complete=True, provider_id="akshare"
        )

    monkeypatch.setattr(providers_akshare, "_invoke", invoke)
    job = await ws.history_jobs.create(
        oid,
        HistoryJobRequest(scope="recent", adjustment="none", source="auto"),
        "deadline-drain-key",
    )
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(0.08)
        current = ws.history_jobs.get(oid, job["id"])
        record = ws.store.data["asset_history_jobs"][job["id"]]
        assert current["state"] == "draining"
        assert current["retryable"] is False and ws.history_jobs.active(oid)
        assert record.get("child_call_id")
        assert providers_akshare.active_futures() and len(hub.tasks) == 1
        with pytest.raises(StoreError) as busy:
            await ws.history_jobs.create(
                oid,
                HistoryJobRequest(scope="recent", adjustment="none", source="auto"),
                "deadline-busy-key",
            )
        assert busy.value.code == "history_busy"
        if cancel_during_drain:
            await ws.history_jobs.cancel(oid, job["id"])
            assert ws.history_jobs.active(oid)
            assert record.get("child_call_id") and providers_akshare.active_futures()
        release.set()
        await settle(ws)
        current = ws.history_jobs.get(oid, job["id"])
        assert current["state"] == ("cancelled" if cancel_during_drain else "failed")
        assert current["failure_code"] == (
            "history_cancelled" if cancel_during_drain else "data_query_deadline"
        )
        assert current["retryable"] is True
        assert (
            not record.get("child_call_id")
            and not providers_akshare.active_futures()
            and not hub.tasks
        )
        assert ws.observation(oid)["blocks"]["history"]["dataset"] is None
    finally:
        release.set()
        await settle(ws)
        await hub.close()


def test_raw_history_equal_declared_aliases_and_optional_none_do_not_fill_zero():
    from app.research_web.asset_history import normalize_raw_rows

    fields = {
        name: {"unit": "currency_per_share", "currency": "CNY"}
        for name in ("open", "high", "low", "close", "开盘")
    }
    fields.update(
        volume={"unit": "share", "currency": None},
        vol={"unit": "share", "currency": None},
        amount={"unit": "currency", "currency": "CNY"},
        turnover={"unit": "currency", "currency": "CNY"},
    )
    row = {
        "asset": "600000.SH",
        "date": "2026-10-20",
        "open": 10,
        "开盘": "10.0",
        "high": 12,
        "low": 9,
        "close": 11,
        "volume": 100,
        "vol": "100",
        "amount": 1100,
        "turnover": "1100.0",
    }
    interval = {"start_date": "2026-10-01", "end_date": "2026-10-20"}
    value = normalize_raw_rows([row], "600000.SH", interval, fields)[0]
    assert value["open"] == 10 and value["volume"] == 100 and value["amount"] == 1100
    optional = {**row, "volume": None, "vol": None, "amount": None, "turnover": None}
    value = normalize_raw_rows([optional], "600000.SH", interval, fields)[0]
    assert "volume" not in value and "amount" not in value
    with pytest.raises(StoreError):
        normalize_raw_rows(
            [{**optional, "open": None, "开盘": None}], "600000.SH", interval, fields
        )


@pytest.mark.asyncio
async def test_history_requests_frozen_raw_semantics_before_source_admission(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    job = await ws.history_jobs.create(
        oid, HistoryJobRequest(scope="recent", adjustment="none", source="auto"), "semantic-job-key"
    )
    await settle(ws)
    row = ws.store.data["asset_history_jobs"][job["id"]]
    assert row["required_semantics"] == "cn_stock_daily_cny_share_v1"
    assert hub.calls[0].required_semantics == row["required_semantics"]


@pytest.mark.asyncio
async def test_native_cjpy_success_cannot_mask_canonical_auto_or_its_cache_identity(
    tmp_path, monkeypatch
):
    import pandas as pd

    from app.research_web.datahub import providers_akshare

    ws, hub, oid, calls, sdk, _ = real_workspace(tmp_path, monkeypatch)
    sdk.__version__ = "0.5.2"
    sid = ws.observation(oid)["session_id"]
    parameters = {
        "asset": "600000.SH",
        "asset_type": "stock",
        "frequency": "daily",
        "adjustment": "none",
        "start_date": "2024-10-20",
        "end_date": "2026-10-20",
    }
    native_query = BusinessQuery(capability="market_bars", parameters=parameters)
    native = await hub.query(sid, "native-success-old", native_query)
    assert native["status"] == "complete" and native["provider"] == "tinysoft"
    assert native["row_count"] == 731
    old = hub.detail(sid, native["dataset_id"])
    assert old["fields"]["close"] == {"unit": None, "currency": None}
    public = []

    def invoke(query):
        public.append(query)
        frame = pd.DataFrame(
            [
                {
                    "date": "2026-10-20",
                    "open": 10,
                    "high": 12,
                    "low": 9,
                    "close": 11,
                    "volume": 100,
                    "amount": 1100,
                }
            ]
        )
        return providers_akshare._materialize(
            query, frame, providers_akshare._normalize_sina_stock_bars
        )

    monkeypatch.setattr(providers_akshare, "_invoke", invoke)
    required = BusinessQuery(
        capability="market_bars",
        parameters=parameters,
        required_semantics="cn_stock_daily_cny_share_v1",
    )
    try:
        canonical = await hub.query(sid, "canonical-success-new", required)
        assert canonical["provider"] == "akshare" and canonical["cache_hit"] is False
        assert len(public) == 1 and len([call for call in calls if call[0] == "bars"]) == 1
        detail = hub.detail(sid, canonical["dataset_id"])
        assert detail["query"]["required_semantics"] == required.required_semantics
        assert detail["query_fingerprint"] != old["query_fingerprint"]
        assert any(
            attempt["source"] == "tinysoft" and attempt["reason"] == "price_units_unverified"
            for attempt in detail["attempted_sources"]
        )
        again = await hub.query(sid, "canonical-cache-new", required)
        assert again["cache_hit"] is True and again["dataset_id"] == canonical["dataset_id"]
        native_again = await hub.query(sid, "native-cache-old", native_query)
        assert native_again["cache_hit"] is True and native_again["provider"] == "tinysoft"
        assert len(public) == 1
        job = await ws.history_jobs.create(
            oid,
            HistoryJobRequest(scope="recent", adjustment="none", source="auto"),
            "native-history-policy",
        )
        await settle(ws)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "completed"
        dataset = ws.observation(oid)["blocks"]["history"]["dataset"]
        assert dataset["provider"] == "akshare" and len(public) == 2
        assert len([call for call in calls if call[0] == "bars"]) == 1
        history = hub.detail(sid, dataset["dataset_id"])["asset_history"]
        assert history["required_semantics"] == required.required_semantics

        def fail_native(**_kwargs):
            raise OSError("synthetic-native-runtime-failure")

        sdk.get_market_data = fail_native
        fallback = await hub.query(
            sid, "generic-runtime-fallback", native_query.model_copy(update={"refresh": True})
        )
        assert fallback["provider"] == "akshare" and len(public) == 3
        assert fallback["provider_metadata"]["execution_attempts"][0]["source"] == "tinysoft"
        assert fallback["provider_metadata"]["execution_attempts"][0]["status"] == "failed"
        fixed = await hub.query(
            sid,
            "fixed-native-failure",
            native_query.model_copy(update={"refresh": True, "source": "tinysoft"}),
        )
        assert fixed["status"] == "failed" and len(public) == 3
    finally:
        await hub.close()


@pytest.mark.asyncio
async def test_retry_keeps_legacy_missing_semantics_instead_of_adopting_new_policy(tmp_path):
    ws, hub, oid = workspace(tmp_path)
    job = await ws.history_jobs.create(
        oid,
        HistoryJobRequest(scope="recent", adjustment="none", source="auto"),
        "legacy-policy-one",
    )
    await ws.history_jobs.cancel(oid, job["id"])
    await settle(ws)
    previous = ws.store.data["asset_history_jobs"][job["id"]]
    previous.pop("required_semantics")
    ws.store.save()
    retry = await ws.history_jobs.create(
        oid,
        HistoryJobRequest(scope="recent", adjustment="none", source="auto", retry_of=job["id"]),
        "legacy-policy-two",
    )
    await settle(ws)
    assert ws.store.data["asset_history_jobs"][retry["id"]]["required_semantics"] is None
    assert hub.calls[0].required_semantics is None
    assert "required_semantics" not in previous


@pytest.mark.asyncio
async def test_http_policy_skips_unknown_prices_then_recovers_ak_failure_with_bao_and_binds_cache(
    tmp_path, monkeypatch
):
    import copy

    import httpx
    from fastapi import FastAPI

    from app.research_web.asset_routes import router
    from app.research_web.datahub import providers_akshare, public_worker
    from app.research_web.datahub.providers import ProviderError

    ws, hub, oid, calls, _sdk, _ = real_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(
        hub.connections,
        "statuses",
        lambda: {
            "tinysoft": {"configured": True, "secret_configured": True},
            "wind": {"configured": True, "preferred_adapter": "excel"},
        },
    )
    executions = []

    def fail_ak(query):
        executions.append("akshare")
        raise ProviderError("vendor_unreachable")

    def fake_bao(source, query):
        assert source == "baostock"
        executions.append(source)
        rows = [
            {
                "asset": "600000.SH",
                "date": "2026-10-20",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "turnover": 1100,
            }
        ]
        fields = {
            key: {"unit": "currency_per_share", "currency": "CNY"}
            for key in ("open", "high", "low", "close")
        }
        fields.update(
            volume={"unit": "share", "currency": None},
            turnover={"unit": "currency", "currency": "CNY"},
        )
        return Result(
            rows=rows,
            raw=[json.dumps(rows).encode()],
            fields=fields,
            status="complete",
            pagination_complete=True,
            provider_id="baostock",
            source_url="https://www.baostock.com/",
        )

    monkeypatch.setattr(providers_akshare, "_invoke", fail_ak)
    monkeypatch.setattr(public_worker, "invoke_worker", fake_bao)
    app = FastAPI()
    app.include_router(router)
    app.state.research = ws.service
    ws.service.asset_workspace = ws
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture"
        ) as client:
            response = await client.post(
                f"/api/research/assets/observations/{oid}/history-jobs",
                json={"scope": "recent", "adjustment": "none", "source": "auto"},
                headers={"Idempotency-Key": "http-ak-bao-policy"},
            )
            assert response.status_code == 202
            job = response.json()
            await settle(ws)
        assert ws.history_jobs.get(oid, job["id"])["state"] == "completed"
        assert calls == [] and executions == ["akshare", "baostock"]
        dataset = ws.observation(oid)["blocks"]["history"]["dataset"]
        history = hub.detail(ws.observation(oid)["session_id"], dataset["dataset_id"])[
            "asset_history"
        ]
        assert dataset["provider"] == "baostock"
        evidence = history["inputs"][0]
        assert any(
            a["source"] == "tinysoft" and a["reason"] == "price_units_unverified"
            for a in evidence["manifest"]["attempted_sources"]
        )
        assert any(
            a["source"] == "wind" and a["reason"] == "workload_too_large"
            for a in evidence["manifest"]["attempted_sources"]
        )
        assert [
            a["source"] for a in evidence["provider_metadata"]["execution_attempts"]
        ] == executions
        record = ws.store.data["asset_history_jobs"][job["id"]]
        chunk = json.loads(
            (
                ws.store.root
                / ".control"
                / "asset-history"
                / "chunks"
                / record["chunks"][0]["name"]
            ).read_text()
        )
        assert chunk["required_semantics"] == record["required_semantics"]
        assert chunk["evidence"]["required_semantics"] == record["required_semantics"]
        assert (await ws.history_jobs._reuse(record, record["chunks"][0]["interval"], {}, None))[
            "normalized"
        ]
        changed = {**record, "required_semantics": None}
        with pytest.raises(StoreError) as changed_policy:
            await ws.history_jobs._reuse(changed, record["chunks"][0]["interval"], {}, None)
        assert changed_policy.value.code == "history_cache_version_changed"
        forged = copy.deepcopy(evidence)
        forged["query"]["required_semantics"] = None
        with pytest.raises(StoreError) as invalid_input:
            ws.history_jobs._authorize_inputs(record, [forged])
        assert invalid_input.value.code == "history_cache_version_changed"
    finally:
        await hub.close()
