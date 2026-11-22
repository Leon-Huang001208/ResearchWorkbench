"""Official release vintages must not leak later revisions into an earlier cutoff."""

import asyncio
import base64
import dataclasses
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.research_web.datahub.bea_archive_store import archive_bridge
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_bea_archive import (
    CATALOG,
    fetch,
    parse_release,
    validate_supported_query,
)
from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)

FIXTURES = Path(__file__).parent / "fixtures" / "bea_archive"


def original(index):
    envelope = json.loads((FIXTURES / f"{index}.json").read_text())
    raw = base64.b64decode(envelope["raw_base64"], validate=True)
    assert hashlib.sha256(raw).hexdigest() == envelope["sha256"]
    return raw


def query(**changes):
    values = {
        "capability": "factor_macro",
        "source": "bea_archive",
        "parameters": {
            "series": "us_real_gdp_qoq_saar",
            "start_date": "2024-06-30",
            "end_date": "2024-06-30",
        },
    }
    values.update(changes)
    return BusinessQuery(**values)


@pytest.mark.parametrize(
    "index,value,stamp",
    [
        (0, 2.8, "2024-07-25T12:30:00+00:00"),
        (1, 3.0, "2024-08-29T12:30:00+00:00"),
    ],
)
def test_real_archived_release_identity(index, value, stamp):
    row = parse_release(original(index), CATALOG[index])
    assert row["value"] == value
    assert row["published_at"] == stamp
    assert row["report_period"] == "2024-06-30"
    assert row["unit"] == "percent_qoq_saar"
    assert row["current_latest_verified"] is False


def test_wrong_release_and_nominal_paragraph_rejected():
    raw = original(0)
    with pytest.raises(ProviderError):
        parse_release(raw, CATALOG[1])
    raw = raw.replace(b"Real ", b"Nominal ")
    with pytest.raises(ProviderError):
        parse_release(raw, CATALOG[0])


def test_cutoff_closed_interval_and_refresh_fail_closed():
    validate_supported_query(query(), storage_read=False)
    first = datetime(2024, 7, 25, 12, 30, tzinfo=UTC)
    validate_supported_query(query(as_of=first, purpose="backtest"), storage_read=True)
    for stamp in [datetime(2024, 7, 25, 12, 29, tzinfo=UTC), datetime(2024, 9, 26, 4, tzinfo=UTC)]:
        with pytest.raises(ProviderError):
            validate_supported_query(query(as_of=stamp), storage_read=True)
    with pytest.raises(ProviderError):
        validate_supported_query(query(as_of=first), storage_read=False)
    with pytest.raises(ProviderError):
        validate_supported_query(query(as_of=first, refresh=True), storage_read=True)


def test_broker_has_executable_route_for_the_registered_archive():
    from app.research_web.datahub.broker import resolve

    assert resolve(query()).provider_id == "bea_archive"
    historical = query(as_of=CATALOG[0].published_at, purpose="backtest")
    assert resolve(historical, storage_read=True).query == historical


def capture():
    calls = []

    def response(request):
        calls.append(str(request.url))
        index = next(i for i, item in enumerate(CATALOG) if item.url == str(request.url))
        return httpx.Response(200, content=original(index))

    result = asyncio.run(fetch(query(), transport=httpx.MockTransport(response)))
    assert len(calls) == 2
    return result


def store():
    allowed = [True]
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: allowed[0])
    scope = StoreScope("alice", "personal-research-v1", "bea_archive", "a" * 64)
    return service, scope, archive_bridge(service, "alice", scope), allowed


def test_two_real_vintages_cutoff_freeze_restore_and_authority():
    _service, _scope, bridge, allowed = store()
    result = capture()
    assert bridge.read(query(), "bea_archive", "a" * 64) is None
    version = bridge.ingest(query(), "bea_archive", "a" * 64, result)
    assert bridge.ingest(query(), "bea_archive", "a" * 64, result) == version
    restored_service, restored_scope, restored, _allowed = store()
    frozen_digests = []
    for stamp, value in [
        (CATALOG[0].published_at, 2.8),
        (CATALOG[1].published_at - timedelta(microseconds=1), 2.8),
        (CATALOG[1].published_at, 3.0),
    ]:
        request = query(as_of=stamp, purpose="backtest")
        hit = bridge.read(request, "bea_archive", "a" * 64)
        assert hit.rows[0]["value"] == value
        assert hit.source_url == hit.rows[0]["source_url"]
        assert hit.metadata["formal_backtest_eligible"] is True
        assert hit.metadata["system_known_at_publication"] is False
        frozen = restored_service.export_restore("alice", restored_scope, hit.raw[0])
        assert frozen.digest == hit.metadata["warehouse_snapshot_sha256"]
        frozen_digests.append(frozen.digest)
        assert restored.read(request, "bea_archive", "a" * 64).rows == hit.rows
        document = json.loads(frozen.payload)
        assert all(f["ingested_at"] > f["available_at"] for f in document["batch"]["facts"])
    assert len(set(frozen_digests)) == 3  # cutoff itself belongs to the manifest
    allowed[0] = False
    with pytest.raises(MarketStoreError):
        bridge.read(query(as_of=CATALOG[0].published_at), "bea_archive", "a" * 64)


def test_old_release_change_rejects_whole_batch_and_preserves_frozen():
    _service, _scope, bridge, _allowed = store()
    result = capture()
    bridge.ingest(query(), "bea_archive", "a" * 64, result)
    first = query(as_of=CATALOG[0].published_at)
    before = bridge.read(first, "bea_archive", "a" * 64).raw[0]
    # Only mutate the old release. The latest projection alone would miss this.
    result.raw[0] = result.raw[0].replace(b"2.8 percent", b"2.9 percent")
    with pytest.raises(MarketStoreError, match="release_conflict"):
        bridge.ingest(query(), "bea_archive", "a" * 64, result)
    assert bridge.read(first, "bea_archive", "a" * 64).raw[0] == before


def test_provider_never_fetches_for_historical_cutoff():
    calls = []
    transport = httpx.MockTransport(lambda request: calls.append(request))
    with pytest.raises(ProviderError):
        asyncio.run(fetch(query(as_of=CATALOG[0].published_at), transport=transport))
    assert calls == []


def test_research_warehouse_archive_needs_no_equity_calendar(tmp_path):
    from app.research_web.datahub.research_warehouse import ResearchWarehouse

    class Backend(InMemoryMarketStore):
        def bootstrap(self):
            return None

    backend = Backend()
    warehouse = ResearchWarehouse(
        tmp_path,
        keyring=SimpleNamespace(get_password=lambda *_: None),
        backend_factory=lambda *_: backend,
    )
    saved = warehouse.save(
        {
            "host": "127.0.0.1",
            "port": 65473,
            "database": "rwb_market_archive",
            "username": "research",
            "sslmode": "disable",
        }
    )
    warehouse.initialize(saved["profile_id"], "rwb_market_archive")
    assert warehouse.read(query(), "bea_archive", "a" * 64) is None
    warehouse.ingest(query(), "bea_archive", "a" * 64, capture())
    assert warehouse.read(query(), "bea_archive", "a" * 64).rows[0]["value"] == 3.0
    assert (
        warehouse.read(query(as_of=CATALOG[0].published_at), "bea_archive", "a" * 64).rows[0][
            "value"
        ]
        == 2.8
    )


def test_same_release_committed_concurrently_is_idempotent(monkeypatch):
    service, _scope, bridge, _allowed = store()
    commit = service.commit_batch
    raced = [False]

    def racing_commit(actor, scope, dataset, batch):
        if not raced[0]:
            raced[0] = True
            other = dataclasses.replace(
                batch,
                facts=tuple(
                    dataclasses.replace(
                        fact, ingested_at=fact.ingested_at + timedelta(microseconds=1)
                    )
                    for fact in batch.facts
                ),
            )
            commit(actor, scope, dataset, other)
        return commit(actor, scope, dataset, batch)

    monkeypatch.setattr(service, "commit_batch", racing_commit)
    bridge.ingest(query(), "bea_archive", "a" * 64, capture())
    assert raced[0]
    assert bridge.read(query(), "bea_archive", "a" * 64).rows[0]["value"] == 3.0


def test_partial_restore_must_not_substitute_an_older_catalog_release():
    _service, _scope, original, _allowed = store()
    original.ingest(query(), "bea_archive", "a" * 64, capture())
    first_query = query(as_of=CATALOG[0].published_at, purpose="backtest")
    second_query = query(as_of=CATALOG[1].published_at, purpose="backtest")
    first = original.read(first_query, "bea_archive", "a" * 64)
    second = original.read(second_query, "bea_archive", "a" * 64)
    for frozen, earlier_available, later_available in [(first, True, False), (second, False, True)]:
        service, scope, restored, _allowed = store()
        service.export_restore("alice", scope, frozen.raw[0])
        assert (
            restored.read(first_query, "bea_archive", "a" * 64) is not None
        ) == earlier_available
        assert (restored.read(second_query, "bea_archive", "a" * 64) is not None) == later_available
        assert (restored.read(query(), "bea_archive", "a" * 64) is not None) == later_available
