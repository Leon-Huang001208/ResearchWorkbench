"""WGC snapshots retain their own metric identity and first-observed revisions."""

import copy
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.providers_wgc import (
    WGC_NUMERIC_CONTRACT,
    WGC_UNITS,
    wgc_fields,
    wgc_projection,
)
from app.research_web.datahub.research_snapshot_store import SnapshotSeries
from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)


def query(dataset="etf-holdings", **updates):
    return BusinessQuery(
        capability="external_data",
        source="ext_wgc",
        parameters={"dataset": dataset, "arguments_json": "{}", "limit": 5000},
        **updates,
    )


def response(dataset="etf-holdings", value=1):
    timestamp = int(datetime(2024, 1, 31, tzinfo=UTC).timestamp() * 1000)
    labels = ["North America", "Europe", "Asia", "Other"]
    monthly = (
        {
            "tonnes": {
                "columns": ["Date", *labels, "Gold, US$/oz"],
                "set": [[timestamp, value, None, 0, 4, 2000]],
            }
        }
        if dataset == "etf-holdings"
        else {
            "series": {
                "tonnes": [
                    {"name": label, "data": [[timestamp, number]]}
                    for label, number in zip(
                        [*labels, "Gold Price (rhs)"], [value, None, 0, 4, 2000], strict=True
                    )
                ]
            }
        }
    )
    raw = json.dumps(
        {"chartData": {"asOfDate": "2024-02-09", "data": {"Monthly": monthly}}}
    ).encode()
    return Result(
        rows=wgc_projection(raw, dataset),
        raw=[raw],
        fields=wgc_fields(),
        provider_id="ext_wgc",
        status="snapshot",
        provider_total=1,
        pagination_complete=True,
        metadata={
            "schema_version": WGC_NUMERIC_CONTRACT,
            "provider_semantics_revision": WGC_NUMERIC_CONTRACT,
            "upstream_id": "worldgoldcouncil",
            "availability_basis": "first_observed",
            "revision_policy": "first_observed_not_historical_vintage",
            "historical_point_in_time": False,
            "formal_backtest_eligible": False,
            "units": dict(WGC_UNITS),
            "projection_scope": "monthly_tonnes_four_regions",
        },
    )


def binding():
    scope = StoreScope("alice", "personal", "ext_wgc", "a" * 64)
    service = MarketStoreService(
        InMemoryMarketStore(), lambda actor, wanted, _: actor == "alice" and wanted == scope
    )
    return (
        scope,
        service,
        SnapshotSeries(
            service,
            "alice",
            scope,
            schema_identity=WGC_NUMERIC_CONTRACT,
            units_identity=WGC_NUMERIC_CONTRACT,
        ),
    )


def test_wgc_holdings_and_flows_restore_separately_without_invented_pit():
    scope, service, series = binding()
    for dataset, value in [("etf-holdings", 1), ("etf-flows", -1)]:
        request, original = query(dataset), response(dataset, value)
        assert series.ingest(request, original)
        display = request.model_copy(update={"purpose": "display", "quality": "allow_stale"})
        captured = series.read(display)
        assert captured.rows == original.rows and captured.fields == original.fields
        assert captured.metadata["historical_point_in_time"] is False
        assert captured.metadata["projection_scope"] == "monthly_tonnes_four_regions"
        assert captured.metadata["formal_backtest_eligible"] is False
        frozen = service.freeze(
            "alice", scope, series.dataset(request), date(1970, 1, 1), date(1970, 1, 1)
        )
        target = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
        assert target.export_restore("alice", scope, frozen.export()).digest == frozen.digest
        restored = SnapshotSeries(
            target,
            "alice",
            scope,
            schema_identity=WGC_NUMERIC_CONTRACT,
            units_identity=WGC_NUMERIC_CONTRACT,
        ).read(display)
        assert restored.rows == captured.rows and restored.fields == captured.fields
        assert series.read(query(dataset, as_of=datetime(2020, 1, 1, tzinfo=UTC))) is None
        with pytest.raises(MarketStoreError):
            series.read(query(dataset, purpose="backtest", as_of=datetime(2020, 1, 1, tzinfo=UTC)))
    assert series.dataset(query("etf-holdings")) != series.dataset(query("etf-flows"))


@pytest.mark.parametrize(
    "bad", ["units", "rows", "fields", "raw", "total", "partial", "pit", "schema", "scope"]
)
def test_wgc_unbound_projection_is_not_published(bad):
    _, _, series = binding()
    result = copy.deepcopy(response())
    if bad == "units":
        result.metadata["units"] = {"north_america": "USD"}
    if bad == "rows":
        result.rows[0]["north_america"] = True
    if bad == "fields":
        result.fields = {}
    if bad == "raw":
        result.raw = []
    if bad == "total":
        result.provider_total = 2
    if bad == "partial":
        result.pagination_complete = False
    if bad == "pit":
        result.metadata["formal_backtest_eligible"] = True
    if bad == "schema":
        result.metadata["schema_version"] = "old"
    if bad == "scope":
        result.metadata["projection_scope"] = "whole_api"
    assert series.ingest(query(), result) is None


def test_wgc_nonempty_arguments_do_not_create_warehouse_identity():
    _, _, series = binding()
    q = query().model_copy(
        update={"parameters": {"dataset": "etf-holdings", "arguments_json": '{"query":{}}'}}
    )
    assert series.dataset(q) is None


@pytest.mark.parametrize("dataset", ["etf-holdings", "etf-flows"])
def test_wgc_revision_cutoff_keeps_old_capture_and_never_promotes_to_pit(dataset):
    scope, service, series = binding()
    request = query(dataset)
    first = datetime(2026, 1, 20, 10, tzinfo=UTC)
    second = first + timedelta(days=1)
    series._now = lambda: first
    assert series.ingest(request, response(dataset, 1))
    series._now = lambda: second
    assert series.ingest(request, response(dataset, 2))
    assert series.read(query(dataset, as_of=first - timedelta(microseconds=1))) is None
    for cutoff, expected in [(first, 1), (second - timedelta(microseconds=1), 1), (second, 2)]:
        captured = series.read(query(dataset, as_of=cutoff))
        assert captured.rows[0]["north_america"] == expected
        assert captured.metadata["formal_backtest_eligible"] is False
        assert captured.metadata["historical_point_in_time"] is False
        frozen = service.freeze(
            "alice",
            scope,
            series.dataset(request),
            date(1970, 1, 1),
            date(1970, 1, 1),
            as_of=cutoff,
        )
        target = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
        target.export_restore("alice", scope, frozen.export())
        restored = SnapshotSeries(
            target,
            "alice",
            scope,
            schema_identity=WGC_NUMERIC_CONTRACT,
            units_identity=WGC_NUMERIC_CONTRACT,
        ).read(query(dataset, as_of=cutoff))
        assert restored.rows == captured.rows
