"""Synthetic and fixture evidence for the scoped NYFed native contract."""

import json

import pytest

from app.research_web.datahub.providers_external import official_numeric_contract
from app.research_web.datahub.providers_nyfed_reference import (
    NYFED_RATES_CONTRACT,
    nyfed_fields,
    nyfed_metadata,
    nyfed_projection,
)


def test_scoped_contract_and_sofrai_units():
    assert official_numeric_contract("ext_nyfed", "rates") == "nyfed-rates-native-v3"
    assert official_numeric_contract("ext_worldbank", "inflation") == "official-numeric-v2"
    assert official_numeric_contract("ext_treasury", "cash") == "official-numeric-v2"
    fields = nyfed_fields([{"type": "SOFRAI", "average30day": "1.00000", "index": "1.00000000"}])
    assert fields["average30day"]["unit"] == "percent"
    assert fields["index"]["unit"] == "index"
    assert fields["index"]["applies_to_type"] == "SOFRAI"


def test_reference_semantics_and_not_availability():
    metadata = nyfed_metadata()
    assert metadata["schema_version"] == NYFED_RATES_CONTRACT
    assert metadata["historical_point_in_time"] is False
    assert metadata["formal_backtest_eligible"] is False
    evidence = metadata["field_dictionary_evidence"]
    assert evidence["sofrai"]["day_count"] == "ACT/360"
    assert evidence["sofrai"]["window_unit"] == "calendar_days"
    assert evidence["sofrai"]["average_rounding_decimals"] == 5
    assert evidence["sofrai"]["index_rounding_decimals"] == 8
    assert evidence["sofrai"]["index_base_date"] == "2018-04-02"
    assert evidence["sofrai"]["first_official_publication_date"] == "2020-03-02"
    assert evidence["publication"]["actual_record_availability"] is False
    assert metadata["availability_basis"] == "first_observed"


def test_raw_duplicate_json_and_wrong_scope_rejected():
    args = {"params": {"start": "2024-03-01", "end": "2024-03-01"}}
    with pytest.raises(ValueError):
        nyfed_projection(b'{"refRates":[],"refRates":[]}', args)
    row = {
        "type": "SOFR",
        "effectiveDate": "2024-03-01",
        "percentRate": "1",
        "volumeInBillions": "2",
        "index": "1",
    }
    with pytest.raises(ValueError):
        nyfed_projection(json.dumps({"refRates": [row]}).encode(), args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "rows",
        "fields",
        "date",
        "doc_sha",
        "pit",
        "backtest",
        "revision",
        "url",
        "raw",
        "duplicate_raw",
        "duplicate_json",
        "count",
        "bool_count",
        "pages",
        "partial",
        "pagination",
        "missing",
        "null",
        "truncated",
        "extra_sofrai",
        "deep_raw",
        "deep_copy_raw",
        "oversize_raw",
        "metadata_object",
        "metadata_nan",
        "metadata_cycle",
        "metadata_deep",
        "fields_deep",
        "rows_deep",
        "framework_digest_type",
        "framework_digest_shape",
        "framework_quality_type",
        "framework_attempts_type",
        "framework_attempts_item_type",
        "framework_unknown_extra",
    ],
)
async def test_nyfed_admission_rebinds_raw_metadata_and_preserves_previous(mutation):
    import copy
    from datetime import UTC, datetime
    from pathlib import Path

    import httpx

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers_external import fetch
    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    raw = (Path(__file__).parent / "fixtures/official_numeric/nyfed.json").read_bytes()
    request = BusinessQuery(
        capability="external_data",
        source="ext_nyfed",
        parameters={
            "dataset": "rates",
            "arguments_json": json.dumps({"params": {"start": "2024-03-01", "end": "2024-03-01"}}),
        },
    )
    good = await fetch(
        request,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        ),
    )
    good.metadata.update(
        execution_authorization_digest="a" * 64,
        quality_accepted=True,
        execution_attempts=[{"source": "ext_nyfed", "status": "snapshot"}],
    )
    series = SnapshotSeries(
        MarketStoreService(InMemoryMarketStore(), lambda *_: True),
        "alice",
        StoreScope("alice", "public", "ext_nyfed", "a" * 64),
        schema_identity=NYFED_RATES_CONTRACT,
    )
    stamp = datetime(2026, 10, 25, tzinfo=UTC)
    series._now = lambda: stamp
    assert series.ingest(request, good)
    altered = copy.deepcopy(good)
    if mutation == "rows":
        altered.rows[-1]["index"] = "9.99999999"
    elif mutation == "fields":
        altered.fields["index"]["unit"] = "percent"
    elif mutation == "date":
        altered.rows[-1]["effectiveDate"] = "2024-03-02"
    elif mutation == "doc_sha":
        altered.metadata["field_dictionary_evidence"]["references"][0]["sha256"] = "0" * 64
    elif mutation == "pit":
        altered.metadata["historical_point_in_time"] = True
    elif mutation == "backtest":
        altered.metadata["formal_backtest_eligible"] = True
    elif mutation == "revision":
        altered.rows[-1]["revisionIndicator"] = "changed"
    elif mutation == "url":
        altered.source_url += "&unreviewed=1"
    elif mutation == "raw":
        altered.raw = [b"{}"]
    elif mutation == "duplicate_raw":
        altered.raw *= 2
    elif mutation == "duplicate_json":
        altered.raw = [b'{"refRates": [], "refRates": []}']
    elif mutation == "count":
        altered.provider_total += 1
    elif mutation == "bool_count":
        altered.provider_total = True
    elif mutation == "pages":
        altered.pages_fetched = 2
    elif mutation == "partial":
        altered.status = "partial"
    elif mutation == "pagination":
        altered.pagination_complete = False
    elif mutation == "missing":
        altered.missing = ["incomplete"]
    elif mutation == "null":
        body = json.loads(raw)
        body["refRates"][-1]["index"] = None
        altered.raw = [json.dumps(body).encode()]
        altered.rows = body["refRates"]
    elif mutation == "truncated":
        altered.rows = altered.rows[:1]
        altered.provider_total = 1
    elif mutation == "extra_sofrai":
        body = json.loads(raw)
        body["refRates"][0]["index"] = "1.00000000"
        altered.raw = [json.dumps(body).encode()]
        altered.rows = body["refRates"]
    elif mutation == "deep_raw":
        altered.raw = [b'{"refRates":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}"]
    elif mutation == "deep_copy_raw":
        row = json.dumps(json.loads(raw)["refRates"][0]).encode()
        altered.raw = [
            b'{"refRates":[' + row[:-1] + b',"extra":' + b"[" * 700 + b"0" + b"]" * 700 + b"}]}"
        ]
    elif mutation == "oversize_raw":
        altered.raw = [b" " * (1024 * 1024) + raw]
    elif mutation == "metadata_object":
        altered.metadata["untrusted"] = object()
    elif mutation == "metadata_nan":
        altered.metadata["untrusted"] = float("nan")
    elif mutation == "metadata_cycle":
        altered.metadata["untrusted"] = altered.metadata
    elif mutation in {"metadata_deep", "fields_deep", "rows_deep"}:
        deep = []
        for _ in range(10000):
            deep = [deep]
        if mutation == "metadata_deep":
            altered.metadata["untrusted"] = deep
        elif mutation == "fields_deep":
            altered.fields["untrusted"] = deep
        else:
            altered.rows[0]["untrusted"] = deep
    elif mutation == "framework_digest_type":
        altered.metadata["execution_authorization_digest"] = 123
    elif mutation == "framework_digest_shape":
        altered.metadata["execution_authorization_digest"] = "not-a-digest"
    elif mutation == "framework_quality_type":
        altered.metadata["quality_accepted"] = 1
    elif mutation == "framework_attempts_type":
        altered.metadata["execution_attempts"] = {}
    elif mutation == "framework_attempts_item_type":
        altered.metadata["execution_attempts"] = ["not-a-dict"]
    elif mutation == "framework_unknown_extra":
        altered.metadata["execution_unknown_extra"] = True
    altered.raw_bytes = sum(map(len, altered.raw))
    try:
        admitted = series.ingest(request, altered)
    finally:
        retained = series.read(request.model_copy(update={"as_of": stamp}))
        assert retained.rows == good.rows and retained.fields == good.fields
        assert retained.metadata["historical_point_in_time"] is False
        assert retained.metadata["formal_backtest_eligible"] is False
    assert admitted is None


def test_sofrai_source_values_and_unknown_revision_flag_are_not_coerced():
    args = {"params": {"start": "2024-03-01", "end": "2024-03-01"}}
    row = {
        "effectiveDate": "2024-03-01",
        "type": "SOFRAI",
        "average30day": "1.12345",
        "average90day": "2.23456",
        "average180day": "3.34567",
        "index": "1.00000001",
        "revisionIndicator": "unknown_future_flag",
    }
    assert nyfed_projection(json.dumps({"refRates": [row]}).encode(), args) == [row]
    evidence = nyfed_metadata()["field_dictionary_evidence"]
    assert (
        evidence["sofrai"]["nonbusiness_days"] == "simple_interest_at_preceding_business_day_rate"
    )
    assert evidence["revisionIndicator"]["revision_timestamp"] is False
    assert evidence["revisionIndicator"]["historical_revision_proof"] is False
    assert (
        evidence["references"][0]["sha256"]
        == "f6e7ee14b49c8d436bcd9e549db00b5b769e1a365040f0b88cf25e3f504f052f"
    )


@pytest.mark.parametrize("kind", ["EFFR", "OBFR", "TGCR", "BGCR", "SOFR"])
@pytest.mark.parametrize("field", ["average30day", "average90day", "average180day", "index"])
def test_sofrai_dictionary_cannot_apply_to_other_five_kinds(kind, field):
    args = {"params": {"start": "2024-03-01", "end": "2024-03-01"}}
    row = {
        "effectiveDate": "2024-03-01",
        "type": kind,
        "percentRate": "1.00",
        "volumeInBillions": "2",
        "revisionIndicator": "",
        field: "1.00000",
    }
    with pytest.raises(ValueError, match="nyfed_projection_invalid"):
        nyfed_projection(json.dumps({"refRates": [row]}).encode(), args)


@pytest.mark.asyncio
async def test_producer_limit_truncation_stays_unwarehouseable():
    from pathlib import Path

    import httpx

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers_external import fetch
    from app.research_web.datahub.research_snapshot_store import _complete_nyfed_snapshot

    raw = (Path(__file__).parent / "fixtures/official_numeric/nyfed.json").read_bytes()
    query = BusinessQuery(
        capability="external_data",
        source="ext_nyfed",
        parameters={
            "dataset": "rates",
            "arguments_json": json.dumps({"params": {"start": "2024-03-01", "end": "2024-03-01"}}),
            "limit": 1,
        },
    )
    result = await fetch(
        query,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        ),
    )
    assert result.status == "partial"
    assert result.pagination_complete is False and result.raw == [raw]
    assert _complete_nyfed_snapshot(query, result) is False
    result.status = "snapshot"
    result.pagination_complete = True
    result.provider_total = 1
    assert _complete_nyfed_snapshot(query, result) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("deep_copy", [False, True])
async def test_deep_json_fetch_fails_closed(deep_copy):
    import httpx

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers_external import fetch

    query = BusinessQuery(
        capability="external_data",
        source="ext_nyfed",
        parameters={
            "dataset": "rates",
            "arguments_json": json.dumps({"params": {"start": "2024-03-01", "end": "2024-03-01"}}),
        },
    )
    deep = b'{"refRates":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}"
    if deep_copy:
        deep = (
            b'{"refRates":[{"effectiveDate":"2024-03-01","type":"SOFR",'
            b'"percentRate":"1.00","volumeInBillions":"2","extra":'
            + b"[" * 700
            + b"0"
            + b"]" * 700
            + b"}]}"
        )
    result = await fetch(
        query,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=deep, headers={"content-type": "application/json"}
            )
        ),
    )
    assert result.status == "failed" and result.rows == [] and result.raw == []


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [True, False, 0, -1, 5001, "500", 1.5])
async def test_direct_nyfed_ingest_cannot_bypass_limit_validation(limit):
    import httpx

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers_external import fetch
    from app.research_web.datahub.research_snapshot_store import _complete_nyfed_snapshot

    query = BusinessQuery(
        capability="external_data",
        source="ext_nyfed",
        parameters={
            "dataset": "rates",
            "arguments_json": json.dumps({"params": {"start": "2024-03-01", "end": "2024-03-01"}}),
        },
    )
    good = await fetch(
        query,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=b'{"refRates":[]}', headers={"content-type": "application/json"}
            )
        ),
    )
    forged = query.model_copy(update={"parameters": dict(query.parameters, limit=limit)})
    assert _complete_nyfed_snapshot(forged, good) is False


def test_rounded_index_can_occasionally_differ_not_always():
    assert (
        nyfed_metadata()["field_dictionary_evidence"]["sofrai"]["rounded_index_averages"]
        == "fifth_decimal_equality_not_guaranteed_no_reconstruction"
    )


def test_official_api_schema_reference_binding_is_complete():
    evidence = nyfed_metadata()["field_dictionary_evidence"]
    references = {item["name"]: item for item in evidence["references"]}
    assert len(references) == len(evidence["references"]) == 5
    for name, url, digest in (
        (
            "api_documentation",
            "https://markets.newyorkfed.org/static/docs/markets-api.html",
            "c1ab76a0e006e7f16c5ba4660716f2ade0f8a76e58dbbe7124d73a9fbf98cd2c",
        ),
        (
            "api_schema",
            "https://markets.newyorkfed.org/static/docs/markets-api.yml",
            "5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b",
        ),
    ):
        assert references[name] == {
            "name": name,
            "url": url,
            "sha256": digest,
            "hash_scope": "original_http_decoded_body",
        }
    schema = evidence["api_schema"]
    assert schema == {
        "reference": "api_schema",
        "documentation_reference": "api_documentation",
        "component": "components.schemas.sofrai-record",
        "schema_document_version": "1.0",
        "type_selector": {"field": "type", "value": "SOFRAI", "schema_type": "string"},
        "number_fields": ["average30day", "average90day", "average180day", "index"],
        "revision_indicator": {"field": "revisionIndicator", "schema_type": "string"},
        "search_path": "/api/rates/all/search.{format}",
        "date_filters": {"startDate": "inclusive", "endDate": "inclusive"},
    }
    assert set(schema["number_fields"]) == set(evidence["sofrai"]["average_fields"]) | {"index"}


@pytest.mark.asyncio
async def test_default_host_broker_persists_nyfed_framework_metadata(tmp_path, monkeypatch):
    import base64
    from pathlib import Path
    from types import SimpleNamespace

    import httpx
    from test_api import NativeFixture

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.research_snapshot_store import METADATA_KEYS
    from app.research_web.datahub.research_warehouse import ResearchWarehouse
    from app.research_web.market_store import FrozenSnapshot, InMemoryMarketStore
    from app.research_web.mcp_registry.service import MCPRegistryService
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    class Backend(InMemoryMarketStore):
        def bootstrap(self):
            pass

    backend = Backend()
    secrets = {}
    keyring = SimpleNamespace(
        get_password=lambda service, account: secrets.get((service, account)),
        set_password=lambda service, account, value: secrets.__setitem__((service, account), value),
        delete_password=lambda service, account: secrets.pop((service, account), None),
    )
    monkeypatch.setattr(ResearchWarehouse, "_postgres", staticmethod(lambda *_: backend))
    monkeypatch.setattr(
        "app.research_web.datahub.connections.default_credential_backend", lambda: keyring
    )
    native = NativeFixture()
    host = ResearchService(
        native,
        Store(tmp_path),
        mcp_registry=MCPRegistryService(tmp_path, keyring_backend=keyring),
        mcp_keyring_backend=keyring,
        delivery_keyring_backend=keyring,
    )
    hub = host.datahub
    raw = (Path(__file__).parent / "fixtures/official_numeric/nyfed.json").read_bytes()
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    hub.transport = httpx.MockTransport(handle)
    warehouse = hub.warehouse
    saved = warehouse.save(
        {
            "host": "127.0.0.1",
            "database": "rwb_market_nyfed",
            "username": "research",
            "sslmode": "disable",
        }
    )
    warehouse.initialize(saved["profile_id"], "rwb_market_nyfed")
    sid = host.store.create("claw", "NYFed native capture")["id"]
    query = BusinessQuery(
        capability="external_data",
        source="ext_nyfed",
        purpose="display",
        quality="allow_stale",
        parameters={
            "dataset": "rates",
            "arguments_json": json.dumps({"params": {"start": "2024-03-01", "end": "2024-03-01"}}),
        },
    )
    try:
        first = await hub.query(sid, "nyfed-first", query)
        assert first["provider_metadata"]["warehouse_persisted"] is True
        assert first["row_count"] == 6 and len(calls) == 1
        second = await hub.query(sid, "nyfed-warehouse-hit", query)
        assert second["provider_metadata"]["warehouse_hit"] is True and len(calls) == 1
        binding = warehouse._snapshot_series(
            query, "ext_nyfed", hub.source_configuration_digest("ext_nyfed")
        )
        retained = binding[0].read(binding[1])
        assert retained.rows == json.loads(raw)["refRates"]
        frozen = FrozenSnapshot.load(retained.raw[0])
        original = json.loads(frozen.payload)["batch"]["originals"][0]
        captured = json.loads(base64.b64decode(original["base64"]))
        assert captured["metadata"] == {
            key: value for key, value in nyfed_metadata().items() if key in METADATA_KEYS
        }
        assert base64.b64decode(captured["payloads"][0]["base64"]) == raw
        for key in ("execution_authorization_digest", "quality_accepted", "execution_attempts"):
            assert key not in METADATA_KEYS and key not in captured["metadata"]
        assert retained.metadata["formal_backtest_eligible"] is False
        assert retained.metadata["historical_point_in_time"] is False
        assert not any(method == "session.prompt" for method, _ in native.calls)
    finally:
        await hub.close()
