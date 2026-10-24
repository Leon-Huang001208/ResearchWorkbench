"""Synthetic originals bind native projections without implying historical PIT."""

import base64
import copy
import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.research_web.datahub import providers_akshare as provider
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.research_snapshot_store import START, SnapshotSeries
from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope


def macro_query(series="gdp"):
    return BusinessQuery(
        capability="factor_macro",
        source="akshare",
        parameters={"series": series, "start_date": "2025-09-01", "end_date": "2025-09-30"},
    )


def macro_raw(series="gdp", value=1):
    row = dict.fromkeys(provider.CHINA_MACRO_CONTRACTS[series][1].split(","), value)
    row.update(
        REPORT_DATE="2025-09-01 00:00:00",
        TIME="2025年第1-3季度" if series == "gdp" else "2025年09月份",
    )
    return json.dumps(
        {"success": True, "code": 0, "result": {"pages": 1, "count": 1, "data": [row]}}
    ).encode()


def macro_result(series="gdp", value=1):
    request = macro_query(series)
    raw = macro_raw(series, value)
    row = json.loads(raw)["result"]["data"][0]
    row.update(
        series=series,
        date="2025-09-30",
        reference_period="2025-Q3" if series == "gdp" else "2025-09",
        aggregation="year_to_date" if series == "gdp" else "period",
    )
    return provider._materialize(
        request,
        pd.DataFrame([row]),
        provider._MacroNormalizer(raw, provider.china_macro_source_url(request), 1, True, series),
    )


def native_series():
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    return SnapshotSeries(service, "alice", StoreScope("alice", "personal", "akshare", "a" * 64))


def sina_query(**updates):
    return BusinessQuery(
        capability="financials",
        source="akshare",
        parameters={
            "asset": "600600.SH",
            "statements": ["income_statement"],
            "periods": ["2025-06-30"],
            **updates,
        },
    )


def sina_raw(value="1"):
    dates = [
        "20250630",
        "20250331",
        "20241231",
        "20240930",
        "20240630",
        "20240331",
        "20231231",
        "20230930",
    ]
    reports = {
        day: {
            "rType": "合并期末",
            "rCurrency": "CNY",
            "publish_date": "20250801",
            "update_time": 1754006400,
            "data": [
                {
                    "item_field": "SYNTHETIC",
                    "item_title": "合成项",
                    "item_value": value,
                    "item_source": "lrb",
                }
            ],
        }
        for day in dates
    }
    return json.dumps(
        {
            "result": {
                "status": {"code": 0},
                "data": {
                    "report_count": "117",
                    "report_date": [
                        {"date_value": day, "date_type": int(day[4:6]) // 3} for day in dates
                    ],
                    "report_list": reports,
                },
            }
        }
    ).encode()


def sina_result(value="1", raw=None, request=None):
    request = request or sina_query()
    raw = raw or sina_raw(value)
    rows, total, _missing = provider.sina_income_projection(raw, request)
    periods = tuple(
        report["date_value"] for report in json.loads(raw)["result"]["data"]["report_date"]
    )
    return provider._materialize(
        request,
        pd.DataFrame(rows),
        provider._FinancialNormalizer(
            raw, provider.sina_income_source_url(request), total, periods
        ),
    )


@pytest.mark.parametrize("series", ["gdp", "cpi", "pmi", "m2"])
def test_macro_genuine_projection_accepted_and_forgery_protects_prior(series):
    store, request, result = native_series(), macro_query(series), macro_result(series)
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    store._now = lambda: stamp
    assert store.ingest(request, result)
    for mutate in (
        lambda r: r.rows[0].update(aggregation="quarterly_saar"),
        lambda r: r.rows[0].update(series="other"),
        lambda r: r.fields.clear(),
        lambda r: r.metadata.update(historical_point_in_time=True),
        lambda r: r.metadata.update(formal_backtest_eligible=0),
        lambda r: r.metadata.update(currency="USD"),
        lambda r: setattr(r, "provider_total", True),
        lambda r: setattr(r, "pages_fetched", True),
        lambda r: setattr(r, "raw", [b"not-json"]),
        lambda r: r.raw.append(r.raw[0]),
        lambda r: setattr(r, "provider_id", "wind"),
        lambda r: setattr(r, "source_url", "https://example.invalid/"),
        lambda r: setattr(r, "as_of", "1900-01-01"),
    ):
        forged = copy.deepcopy(result)
        mutate(forged)
        assert store.ingest(request, forged) is None
        assert store.read(request.model_copy(update={"as_of": stamp})).rows == result.rows


def test_sina_eight_of_117_snapshot_binds_rows_fields_metadata_and_asset():
    store, request, result = (
        native_series(),
        sina_query(periods=8),
        sina_result(request=sina_query(periods=8)),
    )
    store._now = lambda: datetime(2026, 1, 1, tzinfo=UTC)
    assert len(result.rows) == 8 and result.provider_total == 117
    assert result.status == "snapshot" and result.pagination_complete is False
    assert result.metadata["reporting_basis"] == "unknown"
    assert store.ingest(request, result)
    for mutate in (
        lambda r: r.rows[0].update(asset="600000.SH"),
        lambda r: r.rows[0].update(report_period="2025-03-31"),
        lambda r: r.rows[0]["data"][0].update(item_value=True),
        lambda r: r.rows.pop(),
        lambda r: r.fields.clear(),
        lambda r: r.metadata.update(reporting_basis="year_to_date"),
        lambda r: r.metadata.update(currency="CNY"),
        lambda r: r.metadata["field_dictionary_evidence"].update(publication_precision="instant"),
        lambda r: r.metadata.update(formal_backtest_eligible=0),
        lambda r: setattr(r, "pagination_complete", True),
        lambda r: setattr(r, "provider_total", 8),
        lambda r: setattr(r, "as_of", "2025-06-30"),
        lambda r: setattr(r, "raw", [b"[]"]),
        lambda r: setattr(
            r, "source_url", provider.sina_income_source_url(sina_query(asset="600000.SH"))
        ),
    ):
        forged = copy.deepcopy(result)
        mutate(forged)
        assert store.ingest(request, forged) is None
        read = store.read(request.model_copy(update={"as_of": datetime(2026, 1, 1, tzinfo=UTC)}))
        assert read.rows == result.rows

    frozen = store.service.freeze("alice", store.scope, store.dataset(request), START, START)
    envelope = json.loads(
        base64.b64decode(json.loads(frozen.payload)["batch"]["originals"][0]["base64"])
    )
    assert base64.b64decode(envelope["payloads"][0]["base64"]) == result.raw[0]
    restored_service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    restored_service.export_restore("alice", store.scope, frozen.export())
    restored = SnapshotSeries(restored_service, "alice", store.scope).read(
        request.model_copy(update={"as_of": datetime(2026, 1, 1, tzinfo=UTC)})
    )
    assert restored.fields == result.fields
    assert restored.rows == result.rows
    assert restored.metadata["reporting_basis"] == "unknown"
    assert (
        restored.metadata["field_dictionary_evidence"]
        == result.metadata["field_dictionary_evidence"]
    )
    assert restored.pagination_complete is False and restored.provider_total == 117


@pytest.mark.parametrize("gap", ["publication", "all_null", "period"])
def test_sina_missing_source_evidence_remains_partial_and_cannot_ingest(gap):
    body = json.loads(sina_raw())
    request = sina_query()
    if gap == "publication":
        body["result"]["data"]["report_list"]["20250630"]["publish_date"] = ""
    elif gap == "all_null":
        body["result"]["data"]["report_list"]["20250630"]["data"][0]["item_value"] = None
    else:
        request = sina_query(periods=["2025-09-30"])
    result = sina_result(raw=json.dumps(body).encode(), request=request)
    assert result.status == "partial" and result.missing
    assert native_series().ingest(request, result) is None


@pytest.mark.parametrize("family", ["macro", "sina"])
def test_query_validation_is_repeated_at_ingest(family):
    request, result = (
        (macro_query(), macro_result()) if family == "macro" else (sina_query(), sina_result())
    )
    for parameters in (
        {**request.parameters, "unknown": "x"},
        {**request.parameters, "periods": True},
    ):
        assert (
            native_series().ingest(request.model_copy(update={"parameters": parameters}), result)
            is None
        )


def test_gdp_units_remain_unknown_with_ytd_semantics():
    result = macro_result()
    assert result.fields["DOMESTICL_PRODUCT_BASE"] == {
        "unit": None,
        "currency": None,
        "semantic": "year_to_date_amount",
    }
    assert all(
        field["unit"] is None and field["currency"] is None for field in result.fields.values()
    )
    assert result.fields["SUM_SAME"]["semantic"] == "year_to_date_year_over_year_change"


@pytest.mark.parametrize(
    "field,unit,currency",
    [
        ("DOMESTICL_PRODUCT_BASE", "CNY_100million", "CNY"),
        ("DOMESTICL_PRODUCT_BASE", "CNY", "CNY"),
        ("SUM_SAME", "percent", None),
        ("SUM_SAME", "percent_qoq_saar", None),
    ],
)
def test_gdp_forged_units_cannot_replace_prior_native_capture(field, unit, currency):
    request, result, store = macro_query(), macro_result(), native_series()
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    store._now = lambda: stamp
    assert store.ingest(request, result)
    forged = copy.deepcopy(result)
    forged.fields[field].update(unit=unit, currency=currency)
    assert store.ingest(request, forged) is None
    assert store.read(request.model_copy(update={"as_of": stamp})).fields == result.fields


def test_macro_duplicate_json_key_rejected():
    raw = macro_raw().replace(b'"code": 0', b'"code": 1, "code": 0')
    result = macro_result()
    result.raw = [raw]
    assert native_series().ingest(macro_query(), result) is None


@pytest.mark.parametrize("series", ["gdp", "cpi", "pmi", "m2"])
def test_macro_missing_values_and_bad_numeric_are_not_ingestible(series):
    result = macro_result(series)
    body = json.loads(result.raw[0])
    numeric = next(
        field for field in body["result"]["data"][0] if field not in {"TIME", "REPORT_DATE"}
    )
    for value in (None, True, "1", float("inf")):
        body["result"]["data"][0][numeric] = value
        forged = copy.deepcopy(result)
        forged.raw = [json.dumps(body).encode()]
        assert native_series().ingest(macro_query(series), forged) is None


def test_sina_fixed_contract_excludes_dynamic_provider_observation_clock():
    result = sina_result()
    result.metadata["observed_at"] = "irrelevant-provider-clock"
    assert native_series().ingest(sina_query(), result)
