"""KAPSARC full-export numeric identity and its observed revisions remain source-qualified."""

import copy
import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.providers_kapsarc import (
    KAPSARC_NUMERIC_CONTRACT,
    KAPSARC_UNITS,
    kapsarc_fields,
    kapsarc_metadata,
    kapsarc_projection,
)
from app.research_web.datahub.research_snapshot_store import SnapshotSeries
from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)


def query(**updates):
    return BusinessQuery(
        capability="external_data",
        source="ext_kapsarc",
        parameters={"dataset": "production", "arguments_json": "{}", "limit": 5000},
        **updates,
    )


def response(value="2.50"):
    raw = f"country;sub_commodity;year;production\nAlpha;—;2020;{value}\nBeta;—;2020;0\n".encode()
    meta = json.dumps(
        {
            "dataset": {
                "dataset_id": "production-of-gold-mine",
                "visibility": "domain",
                "has_records": True,
                "data_visible": True,
                "fields": [
                    {"name": k, "type": t}
                    for k, t in [
                        ("country", "text"),
                        ("sub_commodity", "text"),
                        ("year", "date"),
                        ("production", "double"),
                    ]
                ],
                "metas": {
                    "default": {
                        "title": "Production of Gold, Mine",
                        "publisher": "British Geological Survey",
                        "records_count": 2,
                        "data_processed": "2025-10-23T13:38:10+00:00",
                        "modified": "2026-06-08T14:21:58+00:00",
                    },
                    "custom": {
                        "unit-of-measure": "kilograms",
                        "data-classification": ["Public"],
                        "publisher-periodicity": ["Annually"],
                    },
                },
            }
        }
    ).encode()
    return Result(
        rows=kapsarc_projection(raw, meta),
        raw=[raw, meta],
        fields=kapsarc_fields(),
        provider_id="ext_kapsarc",
        status="snapshot",
        provider_total=2,
        pagination_complete=True,
        metadata={
            "schema_version": KAPSARC_NUMERIC_CONTRACT,
            "provider_semantics_revision": KAPSARC_NUMERIC_CONTRACT,
            "upstream_id": "bgs-via-kapsarc",
            "availability_basis": "first_observed",
            "revision_policy": "first_observed_not_historical_vintage",
            "historical_point_in_time": False,
            "formal_backtest_eligible": False,
            "units": dict(KAPSARC_UNITS),
            "independent_source": False,
            "projection_scope": "gold_mine_annual_kg_source_export",
            "field_dictionary_evidence": kapsarc_metadata(meta)["field_dictionary_evidence"],
        },
    )


def binding(granted=None):
    granted = granted if granted is not None else {"value": True}
    scope = StoreScope("alice", "personal", "ext_kapsarc", "a" * 64)
    service = MarketStoreService(
        InMemoryMarketStore(),
        lambda actor, wanted, _: granted["value"] and actor == "alice" and wanted == scope,
    )
    return (
        scope,
        service,
        SnapshotSeries(
            service,
            "alice",
            scope,
            schema_identity=KAPSARC_NUMERIC_CONTRACT,
            units_identity=KAPSARC_NUMERIC_CONTRACT,
        ),
    )


def test_kapsarc_capture_restore_and_cutoff_never_invent_disclosure():
    scope, service, series = binding()
    q = query()
    t1 = datetime(2026, 10, 23, 12, tzinfo=UTC)
    t2 = t1 + timedelta(hours=1)
    for stamp, value in [(t1, "2.50"), (t2, "3.75")]:
        series._now = lambda stamp=stamp: stamp
        assert series.ingest(q, response(value))
    assert series.read(query(as_of=t1 - timedelta(microseconds=1))) is None
    for cutoff, expected in [(t1, 2.5), (t2 - timedelta(microseconds=1), 2.5), (t2, 3.75)]:
        captured = series.read(query(as_of=cutoff))
        assert captured.rows[0]["production_kg"] == expected
        assert captured.rows[1]["production"] == "0" and captured.rows[1]["production_kg"] == 0
        assert captured.metadata["historical_point_in_time"] is False
        assert captured.metadata["formal_backtest_eligible"] is False
        assert captured.metadata["projection_scope"] == "gold_mine_annual_kg_source_export"
        assert captured.metadata["independent_source"] is False
        frozen = service.freeze(
            "alice", scope, series.dataset(q), date(1970, 1, 1), date(1970, 1, 1), as_of=cutoff
        )
        target = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
        assert target.export_restore("alice", scope, frozen.export()).digest == frozen.digest
        restored = SnapshotSeries(
            target,
            "alice",
            scope,
            schema_identity=KAPSARC_NUMERIC_CONTRACT,
            units_identity=KAPSARC_NUMERIC_CONTRACT,
        ).read(query(as_of=cutoff))
        assert (
            restored.rows == captured.rows
            and restored.fields == captured.fields
            and restored.raw == captured.raw
        )
    with pytest.raises(MarketStoreError):
        series.read(query(purpose="backtest", as_of=t1))


@pytest.mark.parametrize(
    "bad",
    [
        "unit",
        "schema",
        "publisher",
        "numeric",
        "dictionary",
        "metadata_original",
        "csv_original",
        "total",
        "partial",
        "missing",
        "pit",
        "independent",
        "rawcount",
        "fields",
        "scope",
    ],
)
def test_unbound_or_incomplete_export_is_not_ingested(bad):
    _, _, s = binding()
    r = copy.deepcopy(response())
    if bad == "unit":
        r.metadata["units"] = {"production": "tonnes"}
    if bad == "schema":
        r.metadata["schema_version"] = "external-envelope-v1"
    if bad == "publisher":
        r.metadata["upstream_id"] = "independent-kapsarc"
    if bad == "numeric":
        r.rows[0]["production_kg"] = True
    if bad == "dictionary":
        r.metadata["field_dictionary_evidence"]["unit"] = "tonnes"
    if bad == "metadata_original":
        r.raw[1] = r.raw[1].replace(b"kilograms", b"tonnes")
    if bad == "csv_original":
        r.raw[0] = r.raw[0].replace(b"2.50", b"8.50")
    if bad == "total":
        r.provider_total = True
    if bad == "partial":
        r.pagination_complete = False
    if bad == "missing":
        r.missing = ["remaining_provider_rows"]
    if bad == "pit":
        r.metadata["formal_backtest_eligible"] = True
    if bad == "independent":
        r.metadata["independent_source"] = True
    if bad == "rawcount":
        r.raw = r.raw[:1]
    if bad == "fields":
        r.fields = {}
    if bad == "scope":
        r.metadata["projection_scope"] = "all_global_history"
    assert s.ingest(query(), r) is None


def test_kapsarc_authorization_and_arguments_are_rechecked():
    granted = {"value": True}
    _, _, s = binding(granted)
    q = query()
    assert s.ingest(q, response())
    granted["value"] = False
    with pytest.raises(MarketStoreError):
        s.read(query(purpose="display", quality="allow_stale"))
    _, _, s = binding()
    q = q.model_copy(
        update={"parameters": {"dataset": "production", "arguments_json": '{"query":{}}'}}
    )
    assert s.dataset(q) is None


@pytest.mark.asyncio
async def test_new_cache_contract_is_used_and_old_receipt_remains_readable(tmp_path, monkeypatch):
    from app.research_web.datahub import DataHub, connections, providers
    from app.research_web.store import Store

    monkeypatch.setattr(connections.os, "environ", {})
    monkeypatch.setattr(
        connections,
        "default_credential_backend",
        lambda: SimpleNamespace(get_password=lambda *_: None),
    )
    calls = []

    async def fetch(request, **_):
        calls.append(request)
        r = response()
        if len(calls) == 1:
            r.metadata["schema_version"] = "external-envelope-v1"
        return r

    monkeypatch.setattr(providers, "fetch", fetch)
    store = Store(tmp_path)
    sid = store.create("claw", "KAPSARC source contract")["id"]
    hub = DataHub(store)
    try:
        first = await hub.query(sid, "first", query())
        second = await hub.query(sid, "second", query())
        third = await hub.query(sid, "third", query())
        assert len(calls) == 2 and not second["cache_hit"] and third["cache_hit"]
        assert (
            first["dataset_id"] != second["dataset_id"]
            and third["dataset_id"] == second["dataset_id"]
        )
        again = await hub.query(sid, "first", query())
        assert again["dataset_id"] == first["dataset_id"] and len(calls) == 2
    finally:
        await hub.close()
