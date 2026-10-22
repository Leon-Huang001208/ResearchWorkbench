"""Official numeric envelopes must count observations rather than container rows."""

import json
from datetime import date, timedelta
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
    rows = [{"date": "2024", "value": 3.1}, {"date": "2023", "value": 4.2}]
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=[{"page": 1, "pages": 3, "total": 6}, rows])
    )
    result = await fetch(query("ext_worldbank", "inflation"), transport=transport)
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
