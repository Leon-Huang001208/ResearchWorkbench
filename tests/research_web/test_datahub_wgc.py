"""Synthetic offline checks for WGC's four-region monthly tonnes slice."""

import copy
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.research_web.datahub import providers_external as external
from app.research_web.datahub import providers_wgc as wgc
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError

DATASETS = ("etf-holdings", "etf-flows")
NAMES = ["North America", "Europe", "Asia", "Other"]
FIELDS = ["north_america", "europe", "asia", "other"]
DATES = ["2024-01-31", "2024-02-29", "2024-03-31"]
TIMES = [int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp() * 1000) for d in DATES]


def payload(dataset):
    # Deliberately synthetic observations, including missing and zero values.
    values = [[1, None, 0, 4, 100], [2, 3, 0, 5, 101], [3, 4, 1, 6, 102]]
    monthly = (
        {
            "tonnes": {
                "columns": ["Date", *NAMES, "Gold, US$/oz"],
                "set": [[stamp, *row] for stamp, row in zip(TIMES, values, strict=True)],
            }
        }
        if dataset == "etf-holdings"
        else {
            "series": {
                "tonnes": [
                    {
                        "name": name,
                        "data": [[stamp, row[i]] for stamp, row in zip(TIMES, values, strict=True)],
                    }
                    for i, name in enumerate([*NAMES, "Gold Price (rhs)"])
                ]
            }
        }
    )
    return {"chartData": {"asOfDate": "2024-04-15", "data": {"Monthly": monthly}}}


def query(dataset, **params):
    return BusinessQuery(
        capability="external_data", source="ext_wgc", parameters={"dataset": dataset, **params}
    )


def project(body, dataset):
    return wgc.wgc_projection(json.dumps(body).encode(), dataset)


def cells(body, dataset):
    monthly = body["chartData"]["data"]["Monthly"]
    return (
        monthly["tonnes"]["set"]
        if dataset == "etf-holdings"
        else monthly["series"]["tonnes"][0]["data"]
    )


async def replay(body, dataset, request=None):
    raw = json.dumps(body).encode()

    def handle(req):
        assert req.method == "GET"
        assert req.url.host == "fsapi.gold.org"
        assert req.url.path.endswith(
            "/" + ("holdings-chart2" if dataset == "etf-holdings" else "flows-chart2")
        )
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    return (
        await external.fetch(request or query(dataset), transport=httpx.MockTransport(handle)),
        raw,
    )


@pytest.mark.parametrize("dataset", DATASETS)
def test_wide_monthly_rows_preserve_missing_zero_and_timestamps(dataset):
    rows = project(payload(dataset), dataset)
    assert len(rows) == 3
    assert rows[0] == {
        "reference_date": DATES[0],
        "source_timestamp": TIMES[0],
        "source_as_of_date": "2024-04-15",
        "frequency": "Monthly",
        "metric": "holdings" if dataset == "etf-holdings" else "flows",
        "north_america": 1,
        "europe": None,
        "asia": 0,
        "other": 4,
    }
    assert [r["reference_date"] for r in rows] == DATES
    assert all(set(r) == set(rows[0]) for r in rows)
    assert wgc.WGC_NUMERIC_CONTRACT == "wgc-etf-monthly-tonnes-v1"
    assert wgc.WGC_DATASETS == frozenset(DATASETS)
    assert all(wgc.wgc_fields()[f] == {"type": "number", "unit": "tonnes"} for f in FIELDS)


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("limit", [1, 3, 5])
async def test_provider_raw_metadata_and_honest_limits(dataset, limit):
    result, raw = await replay(payload(dataset), dataset, query(dataset, limit=limit))
    assert result.status == ("partial" if limit < 3 else "snapshot")
    assert result.provider_total == 3 and result.pagination_complete is (limit >= 3)
    assert len(result.rows) == min(limit, 3) and result.raw == [raw]
    assert result.fields == wgc.wgc_fields()
    assert result.metadata == {
        "schema_version": wgc.WGC_NUMERIC_CONTRACT,
        "provider_semantics_revision": wgc.WGC_NUMERIC_CONTRACT,
        "upstream_id": "worldgoldcouncil",
        "availability_basis": "first_observed",
        "revision_policy": "first_observed_not_historical_vintage",
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
        "units": {f: "tonnes" for f in FIELDS},
        "projection_scope": "monthly_tonnes_four_regions",
    }


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize(
    "value", [True, False, "1", {}, [], float("nan"), float("inf"), -float("inf")]
)
def test_invalid_region_number(dataset, value):
    body = payload(dataset)
    cells(body, dataset)[0][1] = value
    with pytest.raises(ProviderError, match="wgc_numeric_schema_invalid"):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("index", [0, 1, 2, 3, 4])
def test_every_selected_numeric_series_is_validated_including_excluded_price(dataset, index):
    body = payload(dataset)
    monthly = body["chartData"]["data"]["Monthly"]
    if dataset == "etf-holdings":
        monthly["tonnes"]["set"][1][index + 1] = True
    else:
        monthly["series"]["tonnes"][index]["data"][1][1] = True
    with pytest.raises(ProviderError):
        project(body, dataset)


def test_gold_price_never_becomes_flows_even_if_series_are_reordered():
    body = payload("etf-flows")
    body["chartData"]["data"]["Monthly"]["series"]["tonnes"].reverse()
    assert project(body, "etf-flows")[1]["north_america"] == 2
    assert all(set(row) == set(wgc.wgc_fields()) for row in project(body, "etf-flows"))


def test_negative_flow_is_source_value_and_negative_holding_rejected():
    for dataset in DATASETS:
        body = payload(dataset)
        cells(body, dataset)[0][1] = -5
        if dataset == "etf-flows":
            assert project(body, dataset)[0]["north_america"] == -5
        else:
            with pytest.raises(ProviderError):
                project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
def test_null_month_preserved_but_all_null_regions_are_no_observations(dataset):
    body = payload(dataset)
    if dataset == "etf-holdings":
        rows = body["chartData"]["data"]["Monthly"]["tonnes"]["set"]
        rows[0][1:5] = [None] * 4
    else:
        series = body["chartData"]["data"]["Monthly"]["series"]["tonnes"]
        for region in series[:4]:
            region["data"][0][1] = None
    assert all(project(body, dataset)[0][field] is None for field in FIELDS)
    if dataset == "etf-holdings":
        for row in rows:
            row[1:5] = [None] * 4
    else:
        for region in series[:4]:
            for point in region["data"]:
                point[1] = None
    with pytest.raises(ProviderError):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize(
    "stamp", [True, "1706659200000", None, 1.5, TIMES[0] + 1, TIMES[0] - 86400000, -(10**30)]
)
def test_non_month_end_or_wrong_timestamp_rejected(dataset, stamp):
    body = payload(dataset)
    cells(body, dataset)[0][0] = stamp
    with pytest.raises(ProviderError):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("mode", ["duplicate", "unsorted", "gap", "empty", "too_many", "short_row"])
def test_complete_selected_slice_required(dataset, mode):
    body = payload(dataset)
    rows = cells(body, dataset)
    if mode == "duplicate":
        rows[1][0] = rows[0][0]
    elif mode == "unsorted":
        rows.reverse()
    elif mode == "gap":
        del rows[1]
    elif mode == "empty":
        rows.clear()
    elif mode == "too_many":
        rows.extend(copy.deepcopy(rows[0]) for _ in range(5000))
    else:
        rows[0].pop()
    with pytest.raises(ProviderError):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize(
    "day", [None, True, "", "2024-02-30", "2024-3-31", "2024-03-31T00:00:00Z", "2024-03-30"]
)
def test_source_asof_is_valid_date_not_before_observations(dataset, day):
    body = payload(dataset)
    body["chartData"]["asOfDate"] = day
    with pytest.raises(ProviderError):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize(
    "error", [{"error": "denied"}, {"success": False}, {"code": 403}, {"error_code": 7}]
)
def test_business_error_cannot_hide_valid_slice(dataset, error):
    body = {**payload(dataset), **error}
    with pytest.raises(ProviderError):
        project(body, dataset)


@pytest.mark.parametrize("dataset", DATASETS)
def test_only_selected_monthly_tonnes_is_validated(dataset):
    body = payload(dataset)
    body["chartData"]["data"]["Weekly"] = {"bad": True}
    body["chartData"]["data"]["Monthly"]["usd"] = {"bad": True}
    assert len(project(body, dataset)) == 3


@pytest.mark.parametrize("mode", ["missing", "duplicate", "unknown", "misaligned", "extra_point"])
def test_flows_exact_series_and_region_alignment(mode):
    body = payload("etf-flows")
    series = body["chartData"]["data"]["Monthly"]["series"]["tonnes"]
    if mode == "missing":
        series.pop(1)
    elif mode == "duplicate":
        series[1]["name"] = series[0]["name"]
    elif mode == "unknown":
        series[1]["name"] = "USD"
    elif mode == "misaligned":
        series[1]["data"][0][0] = TIMES[1]
    else:
        series[1]["data"].append(series[1]["data"][-1])
    with pytest.raises(ProviderError):
        project(body, "etf-flows")


@pytest.mark.parametrize("column", ["Gold Price (rhs)", "Europe", "north_america", "Date"])
def test_holdings_exact_column_contract(column):
    body = payload("etf-holdings")
    body["chartData"]["data"]["Monthly"]["tonnes"]["columns"][1] = column
    with pytest.raises(ProviderError):
        project(body, "etf-holdings")


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"null",
        b"[]",
        b"{}",
        b'{"chartData":{},"chartData":{}}',
        b"x" * (external.MAX_RESPONSE_BYTES + 1),
    ],
)
def test_invalid_json_envelope_and_byte_budget(raw):
    with pytest.raises(ProviderError):
        wgc.wgc_projection(raw, "etf-holdings")


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize(
    "changes",
    [
        {"arguments_json": '{"query":{}}'},
        {"arguments_json": '{"body":{}}'},
        {"arguments_json": '{"params":{}}'},
        {"as_of": datetime(2024, 5, 1, tzinfo=UTC)},
        {"purpose": "backtest"},
        {"required_semantics": ["historical_point_in_time"]},
    ],
)
async def test_fixed_request_rejects_before_transport_or_credentials(dataset, changes):
    req = query(dataset, **{k: v for k, v in changes.items() if k == "arguments_json"})
    req = req.model_copy(update={k: v for k, v in changes.items() if k != "arguments_json"})

    def forbidden(_req):
        pytest.fail("rejected request reached network")

    class ForbiddenConnections:
        def __getattr__(self, _name):
            pytest.fail("rejected request reached credentials")

    result = await external.fetch(
        req, transport=httpx.MockTransport(forbidden), connections=ForbiddenConnections()
    )
    assert result.status == "failed" and result.rows == [] and result.raw == []
    assert result.limitations[0].startswith("wgc_")


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset", DATASETS)
async def test_full_slice_invalid_after_requested_limit_still_fails(dataset):
    body = payload(dataset)
    cells(body, dataset)[-1][1] = True
    result, _ = await replay(body, dataset, query(dataset, limit=1))
    assert result.status == "failed" and result.rows == [] and result.raw == []
