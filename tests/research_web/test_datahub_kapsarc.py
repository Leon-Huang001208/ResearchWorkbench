"""Synthetic offline evidence for the KAPSARC mirror's fixed gold-mine export."""

import json

import httpx
import pytest

from app.research_web.datahub import providers_external as external
from app.research_web.datahub import providers_kapsarc as kapsarc
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError

CSV = "country;sub_commodity;year;production\r\nExample Republic;—;2001;12.3400\r\nExample Republic;—;2003;0\r\n".encode()


def metadata():
    return {
        "dataset": {
            "dataset_id": "production-of-gold-mine",
            "visibility": "domain",
            "has_records": True,
            "data_visible": True,
            "fields": [
                {"name": name, "type": kind}
                for name, kind in [
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
                    "data_processed": "2025-01-01T00:00:00+00:00",
                    "modified": "2026-01-01T00:00:00+00:00",
                    "description": "Stale prose 1900-1901",
                },
                "custom": {"unit-of-measure": "kilograms", "data-classification": ["Public"]},
            },
        }
    }


def raw_metadata():
    return json.dumps(metadata()).encode()


def query(**kwargs):
    parameters = {"dataset": "production", **kwargs.pop("parameters", {})}
    return BusinessQuery(
        capability="external_data", source="ext_kapsarc", parameters=parameters
    ).model_copy(update=kwargs)


def test_projection_preserves_originals_and_zero_without_gap_fill():
    rows = kapsarc.kapsarc_projection(CSV, raw_metadata())
    assert rows == [
        {
            "country": "Example Republic",
            "sub_commodity": "—",
            "year": "2001",
            "production": "12.3400",
            "production_kg": 12.34,
        },
        {
            "country": "Example Republic",
            "sub_commodity": "—",
            "year": "2003",
            "production": "0",
            "production_kg": 0.0,
        },
    ]
    assert kapsarc.kapsarc_fields()["production_kg"] == {"type": "number", "unit": "kg"}
    summary = kapsarc.kapsarc_metadata(raw_metadata())
    assert summary["records_count"] == 2
    assert summary["field_dictionary_evidence"]["unit"] == "kilograms"


@pytest.mark.parametrize(
    "value", ["", "null", "True", "-1", "NaN", "Infinity", "1e999", "1,000", " 2"]
)
def test_invalid_numbers(value):
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_projection(CSV.replace(b"12.3400", value.encode()), raw_metadata())


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"<html>error</html>",
        CSV.replace(b";", b","),
        CSV + b"\n",
        CSV.replace(b"Example", b"Ex\x00ample"),
        CSV.replace(b"Example", b"Ex\xffample"),
        CSV.replace(b"12.3400", b"1;2"),
        CSV.splitlines(keepends=True)[0] + CSV.splitlines(keepends=True)[1] * 2,
        CSV.rsplit(b"\r\n", 2)[0] + b"\r\n",
    ],
)
def test_invalid_csv(raw):
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_projection(raw, raw_metadata())


@pytest.mark.parametrize(
    "case",
    [
        "count",
        "bool_count",
        "unit",
        "field",
        "visibility",
        "records",
        "visible",
        "publisher",
        "title",
        "identity",
        "public",
    ],
)
def test_invalid_metadata(case):
    body = metadata()
    dataset = body["dataset"]
    if case == "count":
        dataset["metas"]["default"]["records_count"] = 3
    elif case == "bool_count":
        dataset["metas"]["default"]["records_count"] = True
    elif case == "unit":
        dataset["metas"]["custom"]["unit-of-measure"] = "tonnes"
    elif case == "field":
        dataset["fields"][3]["type"] = "text"
    elif case == "visibility":
        dataset["visibility"] = "private"
    elif case == "records":
        dataset["has_records"] = False
    elif case == "visible":
        dataset["data_visible"] = False
    elif case == "publisher":
        dataset["metas"]["default"]["publisher"] = "Other"
    elif case == "title":
        dataset["metas"]["default"]["title"] = "Other"
    elif case == "identity":
        dataset["dataset_id"] = "other"
    else:
        dataset["metas"]["custom"]["data-classification"] = ["Private"]
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_projection(CSV, json.dumps(body).encode())


@pytest.mark.parametrize(
    "raw", [b"{}", b"[]", b"<html>error</html>", b'{"dataset":{},"dataset":{}}']
)
def test_bad_metadata_envelope(raw):
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_metadata(raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 2, 4])
async def test_provider_fixed_two_requests_and_limits(limit):
    requests = []

    def handle(req):
        requests.append(req)
        assert req.method == "GET"
        assert req.url.host == "datasource.kapsarc.org"
        return httpx.Response(200, content=CSV if len(requests) == 1 else raw_metadata())

    result = await external.fetch(
        query(parameters={"limit": limit}), transport=httpx.MockTransport(handle)
    )
    assert len(requests) == 2
    assert str(requests[1].url) == kapsarc.KAPSARC_METADATA_URL
    assert "/exports/csv" in requests[0].url.path
    assert result.status == ("partial" if limit == 1 else "snapshot")
    assert result.rows == kapsarc.kapsarc_projection(CSV, raw_metadata())[:limit]
    assert result.raw == [CSV, raw_metadata()]
    assert result.raw_bytes == len(CSV) + len(raw_metadata())
    assert result.pages_fetched == 2 and result.provider_total == 2
    assert result.pagination_complete is (limit != 1)
    assert result.metadata["schema_version"] == kapsarc.KAPSARC_NUMERIC_CONTRACT
    assert result.metadata["upstream_id"] == "bgs-via-kapsarc"
    assert result.metadata["independent_source"] is False
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert result.metadata["units"] == kapsarc.KAPSARC_UNITS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"purpose": "backtest"},
        {"as_of": "2024-01-01"},
        {"required_semantics": "strict"},
        {"parameters": {"arguments_json": '{"query":{}}'}},
    ],
)
async def test_reject_unsupported_before_network(params):
    def handle(req):
        pytest.fail("unsupported request must not reach network")

    result = await external.fetch(query(**params), transport=httpx.MockTransport(handle))
    assert result.status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403),
        httpx.Response(302, headers={"location": "https://other.invalid"}),
        httpx.Response(200, content=b"<html>error</html>"),
    ],
)
async def test_metadata_failure_does_not_publish_csv(response):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(200, content=CSV) if len(calls) == 1 else response

    result = await external.fetch(query(), transport=httpx.MockTransport(handle))
    assert result.status == "failed" and result.rows == [] and result.raw == []


@pytest.mark.parametrize("target", ["csv", "metadata"])
def test_byte_caps(target):
    csv_raw, meta_raw = CSV, raw_metadata()
    huge = b"x" * (kapsarc.MAX_RESPONSE_BYTES + 1)
    if target == "csv":
        csv_raw = huge
    else:
        meta_raw = huge
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_projection(csv_raw, meta_raw)


@pytest.mark.parametrize("count", [0, -1, 5001, None, 2.0])
def test_metadata_count_bounds(count):
    body = metadata()
    body["dataset"]["metas"]["default"]["records_count"] = count
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_metadata(json.dumps(body).encode())


@pytest.mark.asyncio
async def test_two_fetches_share_one_deadline(monkeypatch):
    import asyncio

    monkeypatch.setattr(external, "DEADLINE", 0.08)
    calls = []

    async def handle(req):
        calls.append(req)
        await asyncio.sleep(0.05)
        return httpx.Response(200, content=CSV if len(calls) == 1 else raw_metadata())

    result = await external.fetch(query(), transport=httpx.MockTransport(handle))
    assert len(calls) == 2
    assert result.status == "failed" and result.limitations == ["deadline"]


def test_truncated_final_record_rejected():
    with pytest.raises(ProviderError):
        kapsarc.kapsarc_projection(CSV[:-2], raw_metadata())
