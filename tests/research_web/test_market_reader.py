"""Fixed public indices enter the personal warehouse without a research session."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_market_service import payload

from app.research_web.datahub.providers_market import INDEXES
from app.research_web.datahub.research_warehouse import ResearchWarehouse
from app.research_web.datahub.storage_activity import StorageRunner
from app.research_web.market_store import InMemoryMarketStore, MarketStoreError


def indices():
    result = payload(
        [
            {
                "asset": asset,
                "code": asset[:6],
                "name": name,
                "price": 100,
                "change": 1,
                "change_pct": 1,
                "as_of": "2026-10-22T10:00:00+08:00",
                "series": [{"time": "2026-10-22T09:30:00+08:00", "price": 100, "change_pct": 1}],
                "stale": False,
            }
            for asset, name, _ in INDEXES
        ]
    )
    result.update(
        quote_trade_date="2026-10-22",
        temporal_complete=True,
        missing={"indices": 0, "intraday": 0, "quote_date": 0},
    )
    return result


@pytest.fixture(autouse=True)
def forbid_credentials(monkeypatch):
    from app.research_web import credential_backend

    def forbidden(*_args, **_kwargs):
        raise AssertionError("ambient_credentials_forbidden")

    for cls in (
        credential_backend.SystemKeyringBackend,
        credential_backend.PrivateFileCredentialBackend,
    ):
        for method in ("__init__", "get_password", "set_password", "delete_password"):
            monkeypatch.setattr(cls, method, forbidden)


@pytest.fixture
def context(tmp_path):
    class Backend(InMemoryMarketStore):
        def bootstrap(self):
            pass

    backend = Backend()
    warehouse = ResearchWarehouse(
        tmp_path,
        keyring=SimpleNamespace(get_password=lambda *_: None),
        backend_factory=lambda *_: backend,
    )
    config = {
        "host": "127.0.0.1",
        "database": "rwb_market_indices",
        "username": "research",
        "sslmode": "disable",
    }
    saved = warehouse.save(config)
    warehouse.initialize(saved["profile_id"], config["database"])
    hub = SimpleNamespace(
        store=SimpleNamespace(root=tmp_path),
        warehouse=warehouse,
        storage_runner=StorageRunner(),
        closed=False,
        source_configuration_digest=lambda source: "source-epoch",
    )
    return hub, backend, saved, config


class Provider:
    def __init__(self):
        self.calls = 0
        self.value = indices()
        self.on_fetch = lambda: None

    async def fetch(self, section, **_kwargs):
        assert section == "indices"
        self.calls += 1
        self.on_fetch()
        if isinstance(self.value, Exception):
            raise self.value
        return deepcopy(self.value)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_complete_capture_cache_and_explicit_refresh(context):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, _ = context
    provider = Provider()
    reader = MarketReader(hub)
    try:
        first = await reader.indices(provider, refresh=True)
        assert first["warehouse"]["persisted"] is True
        second = await reader.indices(provider, refresh=False)
        assert second["warehouse"]["hit"] is True
        assert second["rows"] == first["rows"]
        assert provider.calls == 1
        third = await reader.indices(provider, refresh=True)
        assert third["warehouse"]["hit"] is False
        assert provider.calls == 2
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
async def test_partial_does_not_replace_complete_and_database_failure_is_explicit(
    context, monkeypatch
):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, _ = context
    provider = Provider()
    reader = MarketReader(hub)
    try:
        original = await reader.indices(provider, refresh=True)
        provider.value["complete"] = False
        partial = await reader.indices(provider, refresh=True)
        assert partial["warehouse"]["persisted"] is False
        cached = await reader.indices(provider, refresh=False)
        assert cached["rows"] == original["rows"]
        assert provider.calls == 2
        provider.value = indices()

        def unavailable(*_):
            raise MarketStoreError("warehouse_database_unavailable")

        monkeypatch.setattr(hub.warehouse, "ingest", unavailable)
        degraded = await reader.indices(provider, refresh=True)
        assert degraded["warehouse"]["persisted"] is False
        assert degraded["warehouse"]["status"] == "warehouse_database_unavailable"
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
async def test_nonfinite_response_is_safe_failure_without_capture(context):
    from app.research_web.datahub.market_reader import MarketReader

    hub, backend, _, _ = context
    provider = Provider()
    provider.value["rows"][0]["price"] = float("nan")
    try:
        with pytest.raises(MarketStoreError, match="market_indices_response_invalid"):
            await MarketReader(hub).indices(provider, refresh=True)
        assert not backend._batches
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["missing_index", "missing_intraday", "missing_declared", "failed"]
)
async def test_missing_or_failed_response_preserves_last_complete(context, mutation):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, _ = context
    reader, provider = MarketReader(hub), Provider()
    try:
        original = await reader.indices(provider, refresh=True)
        if mutation == "missing_index":
            provider.value["rows"].pop()
        elif mutation == "missing_intraday":
            provider.value["rows"][0]["series"] = []
        elif mutation == "missing_declared":
            provider.value["missing"] = {"indices": 1}
        else:
            provider.value = RuntimeError("fixture_provider_failure")
        if mutation == "failed":
            with pytest.raises(RuntimeError, match="fixture_provider_failure"):
                await reader.indices(provider, refresh=True)
        else:
            rejected = await reader.indices(provider, refresh=True)
            assert rejected["warehouse"]["status"] == "incomplete"
        cached = await reader.indices(provider, refresh=False)
        assert cached["warehouse"]["hit"] is True
        assert cached["rows"] == original["rows"]
        assert provider.calls == 2
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "series_not_dict",
        "quote_time",
        "missing_change_pct",
        "null_change",
        "series_time",
        "series_date",
        "series_order",
        "series_value",
        "temporal",
        "trade_date",
        "identity",
        "missing",
    ],
)
async def test_malformed_complete_envelope_never_replaces_valid_capture(context, mutation):
    from app.research_web.datahub.market_reader import MarketReader

    hub, backend, _, _ = context
    reader, provider = MarketReader(hub), Provider()
    try:
        original = await reader.indices(provider, refresh=True)
        batches_before = deepcopy(backend._batches)
        row = provider.value["rows"][0]
        if mutation == "series_not_dict":
            row["series"] = [None]
        elif mutation == "quote_time":
            row["as_of"] = "not-a-time"
        elif mutation == "missing_change_pct":
            row.pop("change_pct")
        elif mutation == "null_change":
            row["change"] = None
        elif mutation == "series_time":
            row["series"][0]["time"] = "09:30"
        elif mutation == "series_date":
            row["series"][0]["time"] = "2026-10-21T09:30:00+08:00"
        elif mutation == "series_order":
            row["series"] *= 2
        elif mutation == "series_value":
            row["series"][0]["change_pct"] = None
        elif mutation == "temporal":
            provider.value["temporal_complete"] = False
        elif mutation == "trade_date":
            provider.value["quote_trade_date"] = "2026-10-21"
        elif mutation == "identity":
            row["code"] = "999999"
        else:
            provider.value["missing"] = {}
        rejected = await reader.indices(provider, refresh=True)
        assert rejected["warehouse"]["persisted"] is False
        assert rejected["warehouse"]["status"] == "incomplete"
        assert backend._batches == batches_before
        cached = await reader.indices(provider, refresh=False)
        assert cached["rows"] == original["rows"]
        assert cached["warehouse"]["hit"] is True
        assert provider.calls == 2
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
async def test_disabled_profile_never_delivers_old_cache(context):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, saved, _ = context
    reader, provider = MarketReader(hub), Provider()
    try:
        await reader.indices(provider, refresh=True)
        hub.warehouse.disable(saved["profile_id"])
        response = await reader.indices(provider, refresh=False)
        assert provider.calls == 2
        assert response["warehouse"]["status"] == "disabled"
        assert response["warehouse"]["persisted"] is False
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
async def test_profile_or_source_change_during_fetch_rejects(context):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, saved, _ = context
    provider = Provider()
    provider.on_fetch = lambda: hub.warehouse.disable(saved["profile_id"])
    try:
        with pytest.raises(MarketStoreError, match="market_authorization_changed"):
            await MarketReader(hub).indices(provider, refresh=True)
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
async def test_cache_read_rechecks_admission_after_storage(context, monkeypatch):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, _ = context
    provider = Provider()
    reader = MarketReader(hub)
    try:
        await reader.indices(provider, refresh=True)
        real_read = hub.warehouse.read

        def changed(*args):
            result = real_read(*args)
            hub.source_configuration_digest = lambda _: "changed-source"
            return result

        monkeypatch.setattr(hub.warehouse, "read", changed)
        with pytest.raises(MarketStoreError, match="market_authorization_changed"):
            await reader.indices(provider, refresh=False)
        assert provider.calls == 1
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["root", "host_closed", "profile", "source"])
async def test_changed_host_or_profile_never_reuses_foreign_cache(context, tmp_path, mutation):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, config = context
    provider = Provider()
    reader = MarketReader(hub)
    try:
        await reader.indices(provider, refresh=True)
        if mutation == "root":
            hub.store.root = tmp_path / "other-user"
        elif mutation == "host_closed":
            hub.closed = True
        elif mutation == "profile":
            hub.warehouse.save(config)
        else:
            hub.source_configuration_digest = lambda _: "new-source-epoch"
        if mutation in {"root", "host_closed"}:
            with pytest.raises(MarketStoreError, match="market_host_access_denied"):
                await reader.indices(provider, refresh=False)
            assert provider.calls == 1
        else:
            result = await reader.indices(provider, refresh=False)
            assert result["warehouse"]["hit"] is False
            assert provider.calls == 2
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["warehouse_access_denied", "snapshot_source_mismatch"])
async def test_authorization_failure_is_never_database_fallback(context, monkeypatch, failure):
    from app.research_web.datahub.market_reader import MarketReader

    hub, _, _, _ = context
    provider = Provider()

    def rejected(*_):
        raise MarketStoreError(failure)

    monkeypatch.setattr(hub.warehouse, "read", rejected)
    try:
        with pytest.raises(MarketStoreError, match=failure):
            await MarketReader(hub).indices(provider, refresh=False)
        assert provider.calls == 0
    finally:
        await hub.storage_runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["cancel", "close"])
async def test_market_cancel_or_close_waits_for_real_storage_worker(
    context, monkeypatch, operation
):
    import threading

    from app.research_web.datahub.market_reader import MarketReader
    from app.research_web.market_service import MarketService

    hub, _, _, _ = context
    started, released = threading.Event(), threading.Event()
    original = hub.warehouse.ingest

    def blocked(*args):
        started.set()
        if not released.wait(5):
            raise RuntimeError("test_worker_release_timeout")
        return original(*args)

    monkeypatch.setattr(hub.warehouse, "ingest", blocked)
    service = MarketService(hub.store.root, provider=Provider(), market_reader=MarketReader(hub))
    stopping = None
    try:
        job = await service.refresh(["indices"])
        assert await asyncio.to_thread(started.wait, 5)
        stopping = asyncio.create_task(
            service.cancel(job["request_id"]) if operation == "cancel" else service.close()
        )
        for _ in range(10):
            await asyncio.sleep(0)
        assert not stopping.done()
        assert hub.storage_runner.active
        assert service.activity_witness()["active"] is True
        released.set()
        await stopping
        assert not hub.storage_runner.active
    finally:
        released.set()
        if stopping is not None:
            await stopping
        await service.close()
        await hub.storage_runner.close()


async def exercise_default_host(tmp_path, monkeypatch, backend):
    import httpx
    from fastapi import FastAPI
    from test_api import NativeFixture

    from app.research_web.market_routes import router
    from app.research_web.mcp_registry.service import MCPRegistryService
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    secrets = {}
    memory = SimpleNamespace(
        get_password=lambda service, key: secrets.get((service, key)),
        set_password=lambda service, key, value: secrets.__setitem__((service, key), value),
        delete_password=lambda service, key: secrets.pop((service, key), None),
    )
    monkeypatch.setattr(
        "app.research_web.datahub.connections.default_credential_backend", lambda: memory
    )
    monkeypatch.setattr(ResearchWarehouse, "_postgres", staticmethod(lambda *_: backend))
    host = ResearchService(
        NativeFixture(),
        Store(tmp_path),
        mcp_registry=MCPRegistryService(tmp_path, keyring_backend=memory),
        mcp_keyring_backend=memory,
        delivery_keyring_backend=memory,
    )
    saved = host.datahub.warehouse.save(
        {
            "host": "127.0.0.1",
            "database": "rwb_market_host",
            "username": "research",
            "sslmode": "disable",
        }
    )
    host.datahub.warehouse.initialize(saved["profile_id"], "rwb_market_host")
    provider = Provider()
    host.market.provider = provider
    app = FastAPI()
    app.include_router(router)
    app.state.research = host
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/api/research/market")).status_code == 200
            assert provider.calls == 0
            posted = await client.post(
                "/api/research/market/refresh", json={"sections": ["indices"]}
            )
            assert posted.status_code == 202
            job = posted.json()
            async with asyncio.timeout(5):
                while host.market.request(job["request_id"])["status"] in {"pending", "running"}:
                    await asyncio.sleep(0)
            visible = (await client.get("/api/research/market")).json()
            assert visible["sections"]["indices"]["warehouse"]["persisted"] is True
            cached = await host.market.market_reader.indices(provider, refresh=False)
            assert cached["warehouse"]["hit"] is True
            assert provider.calls == 1
            assert host.store.data["sessions"] == {}
            assert not any(method == "session.prompt" for method, _ in host.client.calls)
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_default_host_http_post_uses_warehouse_and_get_never_fetches(tmp_path, monkeypatch):
    class Backend(InMemoryMarketStore):
        def bootstrap(self):
            pass

    await exercise_default_host(tmp_path, monkeypatch, Backend())
