"""Synthetic, offline SPDR GLD four-metric snapshot contract."""

import json

import httpx
import pytest

from app.research_web.datahub import providers_external as external
from app.research_web.datahub.contracts import BusinessQuery

UNITS = {
    "total_nav_usd": "USD",
    "total_tonnes": "tonnes",
    "total_ounces": "ounces",
    "shares_outstanding": "shares",
}


def payload():
    values = ["US$ 123,456.7800", "12.50", "400,000.00", "1,000"]
    return {
        "data": {
            metric: {
                "value": value,
                "date": "January 1, 2024" if metric == "total_ounces" else "January 2, 2024",
                "performance": -1,
            }
            for metric, value in zip(UNITS, values, strict=True)
        },
        "other_source_fields": {"untouched": True},
    }


def query(**changes):
    return BusinessQuery(
        capability="external_data", source="ext_spdr", parameters={"dataset": "gld", **changes}
    )


async def replay(body, request=None):
    raw = json.dumps(body).encode()

    def handle(req):
        assert str(req.url) == (
            "https://api.spdrgoldshares.com/api/v1/data?product=gld&exchange=NYSE&lang=en"
        )
        assert req.method == "GET"
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    return await external.fetch(request or query(), transport=httpx.MockTransport(handle)), raw


@pytest.mark.asyncio
async def test_typed_projection_preserves_originals_and_independent_dates():
    body = payload()
    result, raw = await replay(body)
    assert result.status == "snapshot"
    assert result.provider_total == 4 and result.pagination_complete is True
    assert result.raw == [raw]
    assert external.SPDR_NUMERIC_CONTRACT == "spdr-gld-trust-snapshot-v1"
    assert external.SPDR_METRIC_UNITS == UNITS
    assert [r["metric"] for r in result.rows] == list(UNITS)
    for row in result.rows:
        metric = row["metric"]
        assert row["source_value"] == body["data"][metric]["value"]
        assert row["source_reference_date"] == body["data"][metric]["date"]
        assert row["reference_date"] == ("2024-01-01" if metric == "total_ounces" else "2024-01-02")
        assert row["unit"] == UNITS[metric]
        assert row["currency"] == ("USD" if metric == "total_nav_usd" else None)
        assert isinstance(row["value"], (float, int))
    assert result.rows[0]["value_decimal"] == "123456.7800"
    assert result.rows[0]["value"] == 123456.78
    assert result.metadata["schema_version"] == external.SPDR_NUMERIC_CONTRACT
    assert result.metadata["provider_semantics_revision"] == external.SPDR_NUMERIC_CONTRACT
    assert result.metadata["upstream_id"] == "spdrgoldshares"
    assert result.metadata["availability_basis"] == "first_observed"
    assert result.metadata["revision_policy"] == "first_observed_not_historical_vintage"
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert result.metadata["units"] == UNITS
    assert result.fields["reference_date"]["role"] == "reference_period_not_available_at"
    assert result.fields["value"]["unit"] == "per_row"
    assert result.fields["source_value"]["type"] == "string"


@pytest.mark.asyncio
async def test_zero_and_decimal_precision():
    body = payload()
    body["data"]["total_nav_usd"]["value"] = "US$ 0.000000000000000001"
    for metric in list(UNITS)[1:]:
        body["data"][metric]["value"] = "0"
    result, _ = await replay(body)
    assert result.status == "snapshot"
    assert result.rows[0]["value_decimal"] == "0.000000000000000001"
    assert all(row["value"] == 0 for row in result.rows[1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 3, 4, 5])
async def test_limit_completeness_is_only_four_metric_projection(limit):
    result, raw = await replay(payload(), query(limit=limit))
    assert len(result.rows) == min(limit, 4)
    assert result.status == ("partial" if limit < 4 else "snapshot")
    assert result.pagination_complete is (limit >= 4)
    assert result.provider_total == 4 and result.raw == [raw]
    assert "single_response_not_complete_history" in result.limitations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        12,
        {},
        "",
        "NaN",
        "Infinity",
        "-1",
        "1,00",
        "01,000",
        "1e3",
        "USD 1",
        "EUR 1",
        "US$ 1",
        " 1",
        "1 ",
        "1_000",
        "1" * 129,
    ],
)
async def test_invalid_tonnes_are_failed(value):
    body = payload()
    body["data"]["total_tonnes"]["value"] = value
    result, _ = await replay(body)
    assert result.status == "failed" and result.rows == [] and result.raw == []
    assert result.limitations == ["spdr_numeric_schema_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metric,value",
    [
        ("shares_outstanding", "1.5"),
        ("shares_outstanding", "1.00"),
        ("total_nav_usd", "EUR 1"),
        ("total_nav_usd", "$ 1"),
        ("total_nav_usd", "US$ -1"),
        ("total_nav_usd", "1"),
    ],
)
async def test_metric_specific_number_grammar(metric, value):
    body = payload()
    body["data"][metric]["value"] = value
    assert (await replay(body))[0].limitations == ["spdr_numeric_schema_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "day",
    [
        None,
        True,
        "",
        "January 32, 2024",
        "February 30, 2024",
        "Januar 2, 2024",
        "2024-01-02",
        "January 2, 0000",
        "x" * 65,
    ],
)
async def test_invalid_reference_dates(day):
    body = payload()
    body["data"]["total_ounces"]["date"] = day
    assert (await replay(body))[0].limitations == ["spdr_numeric_schema_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"data": None},
        {"error": "untrusted"},
        {"success": False, "data": {}},
        "<html>denied</html>",
    ],
)
async def test_invalid_envelopes_fail(body):
    result, _ = await replay(body)
    assert result.status == "failed" and result.rows == [] and result.raw == []


@pytest.mark.asyncio
@pytest.mark.parametrize("metric", UNITS)
async def test_missing_metric_is_not_complete(metric):
    body = payload()
    del body["data"][metric]
    assert (await replay(body))[0].limitations == ["spdr_numeric_schema_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [{"error": "untrusted"}, {"success": False}, {"code": 403}, {"error_code": 7}]
)
async def test_error_even_with_valid_data_is_rejected(error):
    body = {**payload(), **error}
    assert (await replay(body))[0].status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {"query": {"product": "other"}},
        {"query": {"exchange": "LSE"}},
        {"query": {"lang": "zh"}},
        {"params": {}},
        {"body": {}},
        {"query": {}},
    ],
)
async def test_fixed_request_rejects_overrides_before_io(args, monkeypatch):
    async def forbidden(*_, **__):
        raise AssertionError("credentials must not be accessed")

    monkeypatch.setattr(external, "credentials", forbidden)

    def no_http(_):
        raise AssertionError("HTTP must not be accessed")

    result = await external.fetch(
        query(arguments_json=json.dumps(args)), transport=httpx.MockTransport(no_http)
    )
    assert result.limitations == ["spdr_arguments_unsupported"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"as_of": "2024-01-02T00:00:00Z"},
        {"purpose": "backtest"},
        {"required_semantics": "cn_stock_daily_cny_share_v1"},
    ],
)
async def test_historical_or_normalized_semantics_reject_before_io(changes, monkeypatch):
    async def forbidden(*_, **__):
        raise AssertionError("credentials must not be accessed")

    monkeypatch.setattr(external, "credentials", forbidden)
    request = query().model_copy(update=changes)
    result = await external.fetch(
        request, transport=httpx.MockTransport(lambda _: pytest.fail("HTTP must not be accessed"))
    )
    assert result.status == "failed" and result.raw == []
    assert result.limitations == ["spdr_historical_semantics_unsupported"]


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [None, "{}"])
async def test_empty_arguments_keep_fixed_contract(arguments):
    result, _ = await replay(payload(), query(arguments_json=arguments))
    assert result.status == "snapshot"


@pytest.mark.asyncio
@pytest.mark.parametrize("metric", UNITS)
@pytest.mark.parametrize("item", [None, [], {}, {"value": "1"}, {"date": "January 2, 2024"}])
async def test_malformed_required_metric(metric, item):
    body = payload()
    body["data"][metric] = item
    assert (await replay(body))[0].limitations == ["spdr_numeric_schema_invalid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "month",
    [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
)
async def test_english_months_do_not_depend_on_locale(month):
    body = payload()
    body["data"]["total_tonnes"]["date"] = f"{month} 2, 2024"
    result, _ = await replay(body)
    assert result.status == "snapshot"
    row = result.rows[1]
    assert row["source_reference_date"] == f"{month} 2, 2024"
    assert row["reference_date"].endswith("-02")


def test_field_metadata_is_fresh_and_pure_parser_retains_only_projection():
    fields = external.spdr_fields()
    fields["value"]["unit"] = "modified"
    assert external.spdr_fields()["value"]["unit"] == "per_row"
    body = payload()
    body["data"]["outside_projection"] = {"value": "unparsed", "date": "unparsed"}
    rows = external.spdr_projection(json.dumps(body).encode())
    assert [row["metric"] for row in rows] == list(UNITS)


@pytest.mark.asyncio
async def test_invalid_json_and_html_fail_safely_without_source_values_in_logs(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        external.log, "warning", lambda event, **fields: warnings.append((event, fields))
    )
    marker = "PRIVATE_UNTRUSTED_BODY"
    for raw in [b"{invalid", f"<html>{marker}</html>".encode()]:
        result = await external.fetch(
            query(),
            transport=httpx.MockTransport(lambda _, data=raw: httpx.Response(200, content=data)),
        )
        assert result.limitations == ["spdr_numeric_schema_invalid"]
        assert result.rows == [] and result.raw == []
    assert warnings and marker not in repr(warnings)
