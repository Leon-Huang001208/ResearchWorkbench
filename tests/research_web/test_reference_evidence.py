"""Pinned reference descriptors do not confer historical availability or broad units."""

import copy
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from test_ak_native_binding import (
    macro_query,
    macro_result,
    native_series,
    sina_query,
    sina_raw,
    sina_result,
)

from app.research_web.datahub import providers_akshare as provider
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.research_snapshot_store import START, SnapshotSeries
from app.research_web.market_store import InMemoryMarketStore, MarketStoreService


@pytest.mark.parametrize("series,count", [("cpi", 6), ("pmi", 2), ("m2", 6)])
def test_monthly_reference_units_are_field_scoped_and_not_pit(series, count):
    result = macro_result(series)
    dictionary = result.metadata["field_dictionary_evidence"]["reference_evidence"]
    assert len(dictionary["ledger_sha256"]) == 64
    assert dictionary["cross_source_equivalence"] == "unverified"
    rates = [v for v in result.fields.values() if v["unit"] == "percent"]
    assert len(rates) == count
    assert all(v["currency"] is None for v in rates)
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert dictionary["historical_availability"] == "unverified"
    assert dictionary["revision_vintage"] == "unavailable"
    if series == "cpi":
        assert dictionary["index_base"] == "unverified"
        assert result.fields["NATIONAL_BASE"]["unit"] is None
        assert result.fields["NATIONAL_ACCUMULATE"]["unit"] is None
        assert dictionary["field_mapping"]["NATIONAL_ACCUMULATE"]["source_label"] == "累计"
    elif series == "pmi":
        assert result.fields["MAKE_INDEX"]["unit"] is None
        assert result.fields["MAKE_INDEX"]["semantic"] == "index_level"
        assert result.fields["MAKE_SAME"]["semantic"] == "year_over_year_change"
        assert dictionary["percentage_point_change"] == "not_asserted"
    else:
        mapping = dictionary["field_mapping"]
        assert mapping["BASIC_CURRENCY"]["monetary_aggregate"] == "M2"
        assert mapping["CURRENCY"]["monetary_aggregate"] == "M1"
        assert mapping["FREE_CASH"]["monetary_aggregate"] == "M0"
        assert dictionary["cross_vintage_definition_equivalence"] == "unverified"
        for field in ("BASIC_CURRENCY", "CURRENCY", "FREE_CASH"):
            assert result.fields[field]["unit"] == "CNY_100million"
            assert result.fields[field]["semantic"] == "month_end_stock"


@pytest.mark.parametrize("series", ["cpi", "pmi", "m2"])
def test_monthly_reference_tamper_rejected_and_previous_capture_kept(series):
    store = native_series()
    stamp = datetime(2026, 10, 25, tzinfo=UTC)
    store._now = lambda: stamp
    query = macro_query(series)
    good = macro_result(series)
    captured = store.ingest(query, good)
    assert captured is not None
    bad = copy.deepcopy(good)
    bad.metadata["field_dictionary_evidence"]["reference_evidence"][
        "historical_availability"
    ] = "verified"
    assert store.ingest(query, bad) is None
    assert store.read(query.model_copy(update={"as_of": stamp})).rows == good.rows


def test_gdp_reference_dictionary_units_and_price_bases():
    result = macro_result()
    for field in (
        "DOMESTICL_PRODUCT_BASE",
        "FIRST_PRODUCT_BASE",
        "SECOND_PRODUCT_BASE",
        "THIRD_PRODUCT_BASE",
    ):
        assert result.fields[field] == {
            "unit": "CNY_100million",
            "currency": "CNY",
            "semantic": "year_to_date_amount",
            "price_basis": "current_prices",
        }
    for field in ("SUM_SAME", "FIRST_SAME", "SECOND_SAME", "THIRD_SAME"):
        assert result.fields[field] == {
            "unit": "percent",
            "currency": None,
            "semantic": "year_to_date_year_over_year_change",
            "price_basis": "comparable_prices",
        }
    dictionary = result.metadata["field_dictionary_evidence"]["reference_evidence"]
    assert (
        dictionary["field_mapping_document"]["sha256"]
        == "e38fa8f47c56c384901e9f61292aba32e1c9cb8af875fb11ef488414e286cf61"
    )
    assert (
        dictionary["price_basis_document"]["sha256"]
        == "9a770677d59a781751b4d7c0070c250a4fa53210afccdda5efac0a12ce156f64"
    )
    assert result.metadata["formal_backtest_eligible"] is False


def scoped_raw(value="123.4500", field="BIZINCO"):
    payload = json.loads(sina_raw())
    report = payload["result"]["data"]["report_list"]["20250630"]
    report["publish_date"] = "20260827"
    report["data"][0].update(item_field=field, item_value=value)
    return json.dumps(payload).encode()


@pytest.fixture
def synthetic_reference(monkeypatch):
    from app.research_web.datahub import providers_reference_evidence as reference

    # Synthetic test numbers never duplicate the issuer's actual financial cells.
    cells = copy.deepcopy(reference.SINA_REFERENCE["cells"])
    for field in cells:
        cells[field]["canonical_decimal_sha256"] = hashlib.sha256(b"123.45").hexdigest()
    monkeypatch.setitem(reference.SINA_REFERENCE, "cells", cells)
    return reference


def test_sina_exact_cell_scope_and_supplier_date_conflict(synthetic_reference):
    result = sina_result(raw=scoped_raw())
    row = result.rows[0]
    evidence = row["reference_evidence"][0]
    assert evidence["status"] == "verified_reference_value_match"
    assert evidence["item_field"] == "BIZINCO"
    assert evidence["unit"] == "CNY"
    assert evidence["scale"] == "1"
    assert evidence["consolidation"] == "group"
    assert evidence["aggregation"] == "year_to_date"
    assert evidence["document_available_at"] is None
    assert evidence["original_release_bytes_proven"] is False
    assert row["data"][0]["item_value"] == "123.4500"
    assert row["publication_date"] == "2026-08-27"
    assert row["publication_date_role"] == "supplier_date_not_verified_original_release"
    dates = row["scoped_date_evidence"]
    assert dates["issuer_release_date_claim"] == "2025-08-26"
    assert dates["date_precision"] == "day"
    assert dates["supplier_date"] == "2026-08-27"
    assert dates["conflict"] is True
    assert result.fields["data"]["unit"] is None
    assert result.fields["reference_evidence"]["semantic"] == "reference_evidence_metadata"
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert native_series().ingest(sina_query(), result)


@pytest.mark.parametrize(
    "asset,period,field,value,status",
    [
        ("600000.SH", "2025-06-30", "BIZINCO", "123.45", None),
        ("600600.SH", "2025-03-31", "BIZINCO", "123.45", None),
        ("600600.SH", "2025-06-30", "PARENTNETPROFIT", "123.45", None),
        ("600600.SH", "2025-06-30", "NETPROFIT", "123.46", "unmatched_reference_value"),
        ("600600.SH", "2025-06-30", "NETPROFIT", None, "unmatched_reference_value"),
        ("600600.SH", "2025-06-30", "NETPROFIT", "123.450", "verified_reference_value_match"),
    ],
)
def test_sina_reference_isolation_and_revised_values(
    synthetic_reference, asset, period, field, value, status
):
    result = sina_result(
        raw=scoped_raw(value, field), request=sina_query(asset=asset, periods=[period])
    )
    refs = result.rows[0]["reference_evidence"]
    assert (refs[0]["status"] if refs else None) == status
    if status == "unmatched_reference_value":
        assert all(
            refs[0][field] is None
            for field in ("unit", "currency", "scale", "consolidation", "aggregation")
        )
        assert refs[0]["scope"]["consolidation"] == "group"
        assert refs[0]["scope"]["aggregation"] == "year_to_date"
    assert result.rows[0]["data"][0]["item_value"] == (value if period == "2025-06-30" else "1")
    assert result.fields["data"]["unit"] is None


@pytest.mark.parametrize("value", [True, False, None, "NaN", "Infinity", "1e2", {}, [], 123.45])
def test_decimal_reference_hash_rejects_noncanonical_inputs(synthetic_reference, value):
    assert synthetic_reference.canonical_decimal_sha256(value) is None


@pytest.mark.parametrize("value", ["123.4500", "+00123.450", "123.45"])
def test_decimal_reference_hash_normalizes_exact_values(synthetic_reference, value):
    assert (
        synthetic_reference.canonical_decimal_sha256(value) == hashlib.sha256(b"123.45").hexdigest()
    )


@pytest.mark.parametrize("literal", ["123.45", "123.4500000000000000001"])
def test_sina_numeric_json_float_never_receives_exact_reference_attestation(
    synthetic_reference, literal
):
    raw = scoped_raw(literal).replace(f'"{literal}"'.encode(), literal.encode())
    rows, _total, _missing = provider.sina_income_projection(raw, sina_query())
    result = sina_result(raw=raw)
    for row in (rows[0], result.rows[0]):
        assert row["data"][0]["item_value"] == 123.45
        assert isinstance(row["data"][0]["item_value"], float)
        evidence = row["reference_evidence"][0]
        assert evidence["status"] == "unmatched_reference_value"
        assert all(
            evidence[field] is None
            for field in ("unit", "currency", "scale", "consolidation", "aggregation")
        )


def test_exact_decimal_hash_preserves_integer_and_unrounded_string(synthetic_reference):
    assert synthetic_reference.canonical_decimal_sha256(123) == hashlib.sha256(b"123").hexdigest()
    text = "123.4500000000000000000000000000000000001"
    assert (
        synthetic_reference.canonical_decimal_sha256(text)
        == hashlib.sha256(text.encode()).hexdigest()
    )
    assert synthetic_reference.canonical_decimal_sha256(
        text
    ) != synthetic_reference.canonical_decimal_sha256("123.45")


@pytest.mark.parametrize(
    "error,code",
    [
        (httpx.ProxyError("secret-url"), "proxy_error"),
        (httpx.ReadTimeout("secret-url"), "timeout"),
        (ConnectionError("secret-url"), "connection_error"),
        (ValueError("secret-url"), "sdk_error"),
    ],
)
def test_natural_sdk_failure_has_only_safe_error_code(monkeypatch, error, code):
    request = BusinessQuery(
        capability="market_activity",
        source="akshare",
        parameters={"asset": "600600.SH", "dataset": "fund_flow"},
    )

    def fail(**_kwargs):
        raise error

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_individual_fund_flow=fail))
    original = provider._FeedNormalizer(
        provider._normalize_activity,
        "eastmoney",
        (
            {"upstream": "eastmoney", "endpoint": "akshare_sdk", "status": "failed"},
            {"upstream": "eastmoney", "endpoint": "webguest", "status": "snapshot"},
        ),
        limited_history=True,
    )
    monkeypatch.setattr(provider, "_fund_flow_guest", lambda _query: (pd.DataFrame(), original))
    _, normalizer = provider._invoke_sdk(request)
    assert normalizer.attempts[0] == {
        "upstream": "eastmoney",
        "endpoint": "akshare_sdk",
        "status": "failed",
        "error_code": code,
    }
    assert "error_code" not in original.attempts[0]
    assert "secret-url" not in json.dumps(normalizer.attempts)


def test_scoped_evidence_raw_binding_and_first_observation_restore(synthetic_reference):
    store, request = native_series(), sina_query()
    observed = datetime(2026, 10, 24, tzinfo=UTC)
    store._now = lambda: observed
    original = sina_result(raw=scoped_raw())
    assert store.ingest(request, original)
    for mutate in (
        lambda result: result.rows[0]["reference_evidence"][0].update(unit="CNY_100million"),
        lambda result: result.rows[0]["reference_evidence"][0].update(
            document_available_at="2025-08-26"
        ),
        lambda result: result.rows[0]["scoped_date_evidence"].update(conflict=False),
        lambda result: result.rows[0].update(publication_date="2025-08-26"),
        lambda result: result.metadata["field_dictionary_evidence"]["reference_evidence"].update(
            ledger_sha256="0" * 64
        ),
    ):
        forged = copy.deepcopy(original)
        mutate(forged)
        assert store.ingest(request, forged) is None
    revised = sina_result(raw=scoped_raw("123.46"))
    store._now = lambda: observed + timedelta(days=1)
    assert store.ingest(request, revised)
    assert (
        store.read(request.model_copy(update={"as_of": observed})).rows[0]["reference_evidence"][0][
            "status"
        ]
        == "verified_reference_value_match"
    )
    assert store.read(request) is None  # Latest strict research still fetches upstream.
    display = request.model_copy(update={"purpose": "display", "quality": "allow_stale"})
    assert (
        store.read(display).rows[0]["reference_evidence"][0]["status"]
        == "unmatched_reference_value"
    )
    for cutoff in (datetime(2025, 8, 26, tzinfo=UTC), datetime(2026, 8, 27, tzinfo=UTC)):
        assert store.read(request.model_copy(update={"as_of": cutoff})) is None
    frozen = store.service.freeze("alice", store.scope, store.dataset(request), START, START)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    service.export_restore("alice", store.scope, frozen.export())
    restored = SnapshotSeries(service, "alice", store.scope).read(
        request.model_copy(update={"as_of": observed + timedelta(days=1)})
    )
    assert restored.rows == revised.rows
    assert restored.fields["data"]["unit"] is None
    assert restored.metadata["formal_backtest_eligible"] is False
