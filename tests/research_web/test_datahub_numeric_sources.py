"""Official numeric envelopes must count observations rather than container rows."""

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers_external import fetch

HISTORY_BODY = {
    "codes": "600000.SH",
    "indicators": "close",
    "startdate": "2026-10-21",
    "enddate": "2026-10-21",
    "functionpara": {"Interval": "D", "Currency": "RMB", "Fill": "Blank"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
async def test_quantapi_history_uses_official_endpoint_and_exact_reqbody(wrapped):
    body = {"reqBody": HISTORY_BODY} if wrapped else HISTORY_BODY
    calls = []
    raw = b'{"errorcode":0,"tables":[{"thscode":"600000.SH","time":["2026-10-21"],"table":{"close":[9.66]}}],"dataVol":1}'

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://quantapi.51ifind.com/api/v1/history_data"
        assert request.method == "POST"
        assert json.loads(request.content) == {"reqBody": HISTORY_BODY}
        assert request.headers["access_token"] == "synthetic-access"
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    result = await fetch(
        BusinessQuery(
            capability="external_data",
            source="ext_ths",
            parameters={
                "dataset": "cmd_history_quotation",
                "arguments_json": json.dumps({"body": body}),
            },
        ),
        connections=SimpleNamespace(
            read_source_secret=lambda _: '{"access_token":"synthetic-access","refresh_token":"synthetic-refresh"}'
        ),
        transport=httpx.MockTransport(handle),
    )
    assert len(calls) == 1
    assert result.status == "snapshot"
    assert result.rows == [{"asset": "600000.SH", "date": "2026-10-21", "close": 9.66}]
    assert result.raw == [raw]
    assert result.source_url == "https://quantapi.51ifind.com/api/v1/history_data"
    assert result.fields["close"]["unit"] == "provider_defined"


@pytest.mark.asyncio
@pytest.mark.parametrize("reflected", ["fixture-only-token", "fixture-refresh"])
async def test_quantapi_rejects_escaped_secret_in_discarded_envelope(reflected):
    payload = {
        "errorcode": 0,
        "message": reflected,
        "tables": [{"thscode": "000001.SZ", "time": ["2025-01-02"], "table": {"close": [11]}}],
    }
    raw = json.dumps(payload).replace(reflected, "\\u0066" + reflected[1:]).encode()

    def transport(request):
        if request.url.path.endswith("get_access_token"):
            return httpx.Response(
                200, json={"errorcode": 0, "data": {"access_token": "fixture-only-token"}}
            )
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    connections = SimpleNamespace(
        read_source_secret=lambda _source: '{"refresh_token":"fixture-refresh"}'
    )
    result = await fetch(
        query("ext_ths", "cmd_history_quotation"),
        connections=connections,
        transport=httpx.MockTransport(transport),
    )
    assert result.status == "failed"
    assert result.limitations == ["credential_reflection"]
    assert result.raw == []
    assert result.rows == []


def query(source, dataset):
    return BusinessQuery(
        capability="external_data",
        source=source,
        parameters={
            "dataset": dataset,
            "arguments_json": json.dumps({"body": HISTORY_BODY} if source == "ext_ths" else {}),
        },
    )


@pytest.mark.asyncio
async def test_worldbank_header_is_not_an_observation_and_pages_remain_partial():
    rows = json.loads(
        (Path(__file__).parent / "fixtures/official_numeric/worldbank.json").read_bytes()
    )[1]
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json=[{"page": 1, "pages": 3, "per_page": 2, "total": 6}, rows]
        )
    )
    request = query("ext_worldbank", "inflation")
    request.parameters["arguments_json"] = json.dumps({"query": {"per_page": 2}})
    result = await fetch(request, transport=transport)
    assert result.rows == rows
    assert result.provider_total == 6
    assert result.pagination_complete is False
    assert result.status == "partial"
    assert "remaining_provider_pages" in result.missing


@pytest.mark.asyncio
async def test_bls_returns_each_observation_with_series_identity_and_rejects_error():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "seriesID": "CUUR0000SA0",
                    "data": [
                        {"year": "2024", "period": "M01", "value": "308.417"},
                        {"year": "2024", "period": "M13", "value": "313.689"},
                    ],
                }
            ]
        },
    }
    result = await fetch(
        query("ext_bls", "series"),
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )
    assert len(result.rows) == 2
    assert result.rows[0]["series_id"] == "CUUR0000SA0"
    assert result.rows[1]["period"] == "M13"  # Annual averages are not December.
    rejected = await fetch(
        query("ext_bls", "series"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"status": "REQUEST_FAILED", "Results": {}})
        ),
    )
    assert rejected.status == "failed"


@pytest.mark.asyncio
async def test_quantapi_history_pairs_times_and_fields_and_rejects_length_mismatch():
    payload = {
        "errorcode": 0,
        "tables": [
            {
                "thscode": "000001.SZ",
                "time": ["2025-01-02", "2025-01-03"],
                "table": {"open": [10, 11], "close": [11, 12]},
            }
        ],
    }
    connections = SimpleNamespace(
        read_source_secret=lambda _source: '{"access_token":"fixture-only-token"}'
    )

    async def read(body):
        return await fetch(
            query("ext_ths", "cmd_history_quotation"),
            connections=connections,
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=body)),
        )

    result = await read(payload)
    assert result.rows == [
        {"asset": "000001.SZ", "date": "2025-01-02", "open": 10, "close": 11},
        {"asset": "000001.SZ", "date": "2025-01-03", "open": 11, "close": 12},
    ]
    assert result.fields["close"]["unit"] == "provider_defined"
    payload["tables"][0]["table"]["close"] = [11]
    assert (await read(payload)).status == "failed"
    assert "fixture-only-token" not in json.dumps(result.rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reqBody": None},
        {"reqBody": HISTORY_BODY, "codes": "600000.SH"},
        {**HISTORY_BODY, "unknown": "value"},
        {**HISTORY_BODY, "codes": " "},
        {**HISTORY_BODY, "codes": "x" * 4097},
        {**HISTORY_BODY, "indicators": "close,,open"},
        {**HISTORY_BODY, "startdate": "2026-02-30"},
        {**HISTORY_BODY, "enddate": "2026-10-20"},
        {**HISTORY_BODY, "functionpara": "Interval:D,Currency:RMB"},
        {**HISTORY_BODY, "functionpara": {"unknown": "value"}},
        {**HISTORY_BODY, "functionpara": {"Interval": "D", "SampleInterval": "D"}},
        {**HISTORY_BODY, "functionpara": {"Fill": None}},
        {**HISTORY_BODY, "functionpara": {"Fill": 10**400}},
        {**HISTORY_BODY, "functionpara": {"Fill": "NaN"}},
        {**HISTORY_BODY, "functionpara": {"CPS": True}},
        {**HISTORY_BODY, "functionpara": {"BaseDate": "2026-2-30"}},
        {**HISTORY_BODY, "codes": "600000.SH*"},
        {**HISTORY_BODY, "codes": "BLOCK(ALL)"},
        {**HISTORY_BODY, "codes": "SH:600000"},
        {**HISTORY_BODY, "indicators": "close/open"},
        {**HISTORY_BODY, "indicators": "close()"},
    ],
)
async def test_quantapi_invalid_history_contract_rejected_before_secret_read(body):
    def forbidden(_):
        raise AssertionError("Invalid request must not read secrets or call the vendor")

    request = BusinessQuery(
        capability="external_data",
        source="ext_ths",
        parameters={
            "dataset": "cmd_history_quotation",
            "arguments_json": json.dumps({"body": body}),
        },
    )
    result = await fetch(
        request,
        connections=SimpleNamespace(read_source_secret=forbidden),
        transport=httpx.MockTransport(forbidden),
    )
    assert result.status == "failed"
    assert result.limitations == ["quantapi_history_contract_invalid"]
    assert not result.raw and not result.rows


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "codes,indicators,days,options,accepted",
    [
        (1, 1, 5000, {"Interval": "D"}, True),
        (100, 10, 5, {"Interval": "D"}, True),
        (1, 1, 5001, {"Interval": "D"}, False),
        (1, 1, 5001, {"Interval": "W"}, False),
        (1, 1, 5001, {"SampleInterval": "M"}, False),
        (91, 11, 5, {"Interval": "D"}, False),
    ],
)
async def test_quantapi_history_bounds_upstream_work_before_credentials(
    codes, indicators, days, options, accepted
):
    start = date(2026, 1, 1)
    body = {
        "codes": ",".join(f"X{i}.SH" for i in range(codes)),
        "indicators": ",".join(f"i_{i}" for i in range(indicators)),
        "startdate": start.isoformat(),
        "enddate": (start + timedelta(days=days - 1)).isoformat(),
        "functionpara": options,
    }
    secret_reads, calls = [], []

    def secret(source):
        secret_reads.append(source)
        return "synthetic-access"

    def handle(request):
        calls.append(request)
        assert json.loads(request.content) == {"reqBody": body}
        return httpx.Response(200, json={"errorcode": 0, "tables": []})

    request = BusinessQuery(
        capability="external_data",
        source="ext_ths",
        parameters={
            "dataset": "cmd_history_quotation",
            "limit": 1,
            "arguments_json": json.dumps({"body": body}),
        },
    )
    result = await fetch(
        request,
        connections=SimpleNamespace(read_source_secret=secret),
        transport=httpx.MockTransport(handle),
    )
    if accepted:
        assert result.status == "empty"
        assert secret_reads == ["ext_ths"] and len(calls) == 1
    else:
        assert result.status == "failed"
        assert result.limitations == ["quantapi_history_workload_limit"]
        assert secret_reads == [] and calls == []
        assert result.rows == [] and result.raw == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "date,options",
    [
        ("20261021", None),
        ("2026/10/21", {}),
        (
            "2026-10-21",
            {
                "SampleInterval": "W",
                "CPS": "1",
                "PriceType": "2",
                "BaseDate": "2026-10-21",
                "Currency": "YSHB",
                "Fill": 0.0,
            },
        ),
    ],
)
async def test_quantapi_history_preserves_documented_options_without_defaults(date, options):
    body = {key: value for key, value in HISTORY_BODY.items() if key != "functionpara"}
    body.update(startdate=date, enddate=date)
    if options is not None:
        body["functionpara"] = options

    def handle(request):
        assert json.loads(request.content) == {"reqBody": body}
        return httpx.Response(200, json={"errorcode": 0, "tables": []})

    request = BusinessQuery(
        capability="external_data",
        source="ext_ths",
        parameters={
            "dataset": "cmd_history_quotation",
            "arguments_json": json.dumps({"body": body}),
        },
    )
    result = await fetch(
        request,
        connections=SimpleNamespace(read_source_secret=lambda _: "synthetic-access"),
        transport=httpx.MockTransport(handle),
    )
    assert result.status == "empty"


@pytest.mark.asyncio
async def test_quantapi_history_query_parameters_are_not_an_alternative_payload():
    def forbidden(_):
        raise AssertionError("Ambiguous query must fail before credentials or vendor access")

    request = BusinessQuery(
        capability="external_data",
        source="ext_ths",
        parameters={
            "dataset": "cmd_history_quotation",
            "arguments_json": json.dumps({"body": HISTORY_BODY, "query": {"codes": "other"}}),
        },
    )
    result = await fetch(
        request,
        connections=SimpleNamespace(read_source_secret=forbidden),
        transport=httpx.MockTransport(forbidden),
    )
    assert result.status == "failed"
    assert result.limitations == ["quantapi_history_contract_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,status,rows",
    [
        ({"errorcode": -1, "errmsg": "rejected", "tables": []}, "failed", []),
        ({"errorcode": 0, "tables": []}, "empty", []),
        ({"errorcode": 0, "tables": None}, "failed", []),
        (
            {
                "errorcode": 0,
                "tables": [
                    {"thscode": "600000.SH", "time": ["2026-10-21"], "table": {"close": [None]}}
                ],
            },
            "partial",
            [{"asset": "600000.SH", "date": "2026-10-21", "close": None}],
        ),
    ],
)
async def test_quantapi_history_empty_null_and_business_rejection_are_distinct(
    payload, status, rows
):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    result = await fetch(
        query("ext_ths", "cmd_history_quotation"),
        connections=SimpleNamespace(read_source_secret=lambda _: "synthetic-access"),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        ),
    )
    assert result.status == status
    assert result.rows == rows
    if status == "failed":
        assert result.raw == []
        assert "synthetic-access" not in json.dumps(result.limitations)
        if payload["errorcode"] != 0:
            assert result.limitations == ["vendor_rejected"]
    else:
        assert result.raw == [raw]
    if status == "partial":
        assert result.missing == ["history_values_missing"]


EXTERNAL_FIXTURES = Path(__file__).parent / "fixtures/external_envelopes"


def external_query(name, **parameters):
    args = (
        {"params": {"symbol": "AAPL"}}
        if name == "nasdaq"
        else {"params": {"code": "510050"}} if name == "danjuan" else {}
    )
    return BusinessQuery(
        capability="external_data",
        source="ext_" + name,
        parameters={
            "dataset": (
                "history"
                if name in {"nasdaq", "danjuan"}
                else "hot-list" if name == "cls" else "production"
            ),
            "arguments_json": json.dumps(args),
            **parameters,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,status",
    [("nasdaq", "failed"), ("cls", "failed"), ("danjuan", "partial"), ("kapsarc", "partial")],
)
async def test_actual_external_business_envelopes_are_not_container_success(name, status):
    raw = (EXTERNAL_FIXTURES / (name + (".csv" if name == "kapsarc" else ".json"))).read_bytes()
    result = await fetch(
        external_query(name, limit=5),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=raw,
                headers={"content-type": "text/csv" if name == "kapsarc" else "application/json"},
            )
        ),
    )
    assert result.status == status
    if name in {"nasdaq", "cls"}:
        assert result.rows == [] and result.raw == []
        assert result.limitations == ["vendor_rejected"]
    else:
        assert result.raw == [raw]
        assert result.metadata["schema_version"] == "external-envelope-v1"
        if name == "danjuan":
            assert result.rows == [] and result.provider_total == 0
            assert result.missing == ["no_observation_rows"]
        else:
            assert len(result.rows) == 5
            assert set(result.rows[0]) == {"country", "sub_commodity", "year", "production"}
            assert result.rows[0]["country"] == "South Africa"
            assert result.rows[0]["production"] == "679665.0"
            assert result.fields["production"]["unit"] == "provider_defined"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,payload,reason",
    [
        ("nasdaq", {"status": {"rCode": 200}, "data": None}, "external_numeric_schema_invalid"),
        (
            "nasdaq",
            {"status": {"rCode": 200}, "data": {"synthetic": True}},
            "external_business_schema_unverified",
        ),
        ("cls", {"errno": 0, "data": [{"synthetic": True}]}, "external_business_schema_unverified"),
        ("danjuan", {"result_code": 1, "data": {}}, "vendor_rejected"),
        (
            "danjuan",
            {"result_code": 0, "data": {"horizontal_lines": []}},
            "external_numeric_schema_invalid",
        ),
        (
            "danjuan",
            {"result_code": 0, "data": {"index_eva_pe_growths": [{"synthetic": True}]}},
            "external_business_schema_unverified",
        ),
    ],
)
async def test_synthetic_unknown_positive_envelopes_fail_closed(name, payload, reason):
    result = await fetch(
        external_query(name),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    assert result.status == "failed" and result.rows == [] and result.raw == []
    assert result.limitations == [reason]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        b"country,sub_commodity,year,production\nChina,x,2024,1\n",
        b"country;sub_commodity;year;production;extra\nChina;x;2024;1;x\n",
        b"country;sub_commodity;year;production\nChina;x;2024;NaN\n",
        b"country;sub_commodity;year;production\nChina;x;2024;-1\n",
        b"country;sub_commodity;year;production\nChina;x;2099;1\n",
        b"country;sub_commodity;year;production\n;x;2024;1\n",
        b"country;sub_commodity;year;production\nChina;x;2024;1;extra\n",
        b"<html>upstream error</html>",
    ],
)
async def test_kapsarc_closed_semicolon_csv_rejects_invalid_rows(raw):
    result = await fetch(
        external_query("kapsarc"),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "text/csv"})
        ),
    )
    assert result.status == "failed" and not result.rows and not result.raw


@pytest.mark.asyncio
async def test_danjuan_empty_is_not_success_cached_or_warehoused_and_old_receipt_remains(tmp_path):
    from app.research_web.datahub import DataHub
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope
    from app.research_web.store import Store

    raw = (EXTERNAL_FIXTURES / "danjuan.json").read_bytes()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    store = Store(tmp_path)
    sid = store.create("claw", "dan false success")["id"]
    hub = DataHub(store, transport=httpx.MockTransport(handler))
    request = external_query("danjuan")
    old = Result(
        provider_id="ext_danjuan",
        status="snapshot",
        rows=[{"data": {"horizontal_lines": []}}],
        raw=[b"legacy"],
    )
    saved = hub.snapshots.publish(
        sid,
        request,
        old,
        request_query=request,
        authorization_fingerprint=hub.source_configuration_digest("ext_danjuan"),
    )
    hub.snapshots.receipt(
        sid,
        "legacy",
        {
            "status": "completed",
            "fingerprint": request.fingerprint(include_refresh=True),
            "dataset_id": saved["dataset_id"],
            "cache_hit": False,
        },
    )
    try:
        assert (await hub.query(sid, "legacy", request))["dataset_id"] == saved["dataset_id"]
        assert not calls
        for call in ("new", "again"):
            current = await hub.query(sid, call, request)
            assert (
                current["status"] == "partial"
                and current["data_success"] is False
                and not current["cache_hit"]
            )
            assert current["dataset_id"] != saved["dataset_id"]
        assert len(calls) == 2
        result = await fetch(request, transport=httpx.MockTransport(handler))
        native = SnapshotSeries(
            MarketStoreService(InMemoryMarketStore(), lambda *_: True),
            "alice",
            StoreScope("alice", "public", "ext_danjuan", "a" * 64),
        )
        assert native.dataset(request) is None and native.ingest(request, result) is None
    finally:
        await hub.close()


@pytest.mark.asyncio
async def test_kapsarc_zero_is_valid_unknown_units_and_does_not_change_general_csv():
    from app.research_web.datahub.providers_external import response_rows

    raw = b"country;sub_commodity;year;production\nChina;gold;2024;0\n"
    result = await fetch(
        external_query("kapsarc"),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "text/csv"})
        ),
    )
    assert result.status == "snapshot" and result.rows[0]["production"] == "0"
    assert result.raw == [raw] and result.pagination_complete is False
    assert result.fields["production"]["unit"] == "provider_defined"
    assert response_rows(b"date,value\n2024,1\n", "text/csv") == [{"date": "2024", "value": "1"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,parameters", [("nasdaq", {"symbol": "../AAPL"}), ("danjuan", {"code": "../510050"})]
)
async def test_external_history_identity_parameters_reject_path_before_http(name, parameters):
    def forbidden(_):
        raise AssertionError("invalid path must not perform HTTP")

    request = external_query(name, arguments_json=json.dumps({"params": parameters}))
    result = await fetch(request, transport=httpx.MockTransport(forbidden))
    assert result.status == "failed" and result.limitations == ["external_parameters_invalid"]


@pytest.mark.parametrize(
    "source,dataset",
    [
        ("ext_nasdaq", "history"),
        ("ext_cls", "hot-list"),
        ("ext_danjuan", "history"),
        ("ext_kapsarc", "production"),
    ],
)
def test_external_envelope_repairs_do_not_expand_native_warehouse(source, dataset):
    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    native = SnapshotSeries(
        MarketStoreService(InMemoryMarketStore(), lambda *_: True),
        "alice",
        StoreScope("alice", "public", source, "a" * 64),
    )
    assert (
        native.dataset(
            BusinessQuery(
                capability="external_data", source=source, parameters={"dataset": dataset}
            )
        )
        is None
    )
