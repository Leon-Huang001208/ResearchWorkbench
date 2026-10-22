"""Official numeric envelopes must count observations rather than container rows."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers_external import fetch


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
        parameters={"dataset": dataset, "arguments_json": "{}"},
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
