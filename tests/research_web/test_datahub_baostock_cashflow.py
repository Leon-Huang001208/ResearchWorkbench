"""Synthetic cash-flow ratios: exact supplier schema and no inferred units."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_baostock import invoke
from tests.research_web.test_datahub_baostock import Rows

FIELDS = "code,pubDate,statDate,CAToAsset,NCAToAsset,tangibleAssetToAsset,ebitToInterest,CFOToOR,CFOToNP,CFOToGr"


def query(**updates):
    return BusinessQuery(
        capability="financials",
        source="baostock",
        parameters={
            "asset": "600000.SH",
            "statements": ["cash_flow"],
            "periods": ["2025-06-30"],
            **updates,
        },
    )


def row(**updates):
    return {
        **dict(
            zip(
                FIELDS.split(","),
                [
                    "sh.600000",
                    "2025-08-20",
                    "2025-06-30",
                    "",
                    "",
                    "",
                    "",
                    "-3.07155",
                    "0",
                    "-3.07155",
                ],
                strict=True,
            )
        ),
        **updates,
    }


def replay(rows=None):
    rows = [row()] if rows is None else rows
    calls = []

    def cash(**kwargs):
        calls.append(kwargs)
        return Rows(FIELDS, [[r[key] for key in FIELDS.split(",")] for r in rows])

    result = invoke(query(), sdk=SimpleNamespace(query_cash_flow_data=cash))
    assert calls == [{"code": "sh.600000", "year": 2025, "quarter": 2}]
    return result


def test_projection_and_result_preserve_exact_raw_and_unknown_ratio_scale():
    from app.research_web.datahub.providers_baostock_cashflow import (
        cash_flow_fields,
        cash_flow_metadata,
        cash_flow_projection,
    )

    result = replay()
    assert result.status == "complete"
    assert json.loads(result.raw[0]) == [row()]
    assert cash_flow_projection(result.raw[0], "600000.SH", "2025-06-30") == (result.rows, [])
    assert result.rows[0]["CFOToNP"] == 0
    assert result.rows[0]["CFOToOR"] == -3.07155
    assert result.rows[0]["CAToAsset"] is None
    assert result.fields == cash_flow_fields()
    assert result.metadata == cash_flow_metadata()
    assert all(
        f
        == {
            "unit": None,
            "currency": None,
            "semantic": "provider_native_ratio",
            "scale": "unverified",
        }
        for f in result.fields.values()
    )
    assert result.metadata["projection_scope"] == "quarterly_cash_flow_ratios_native"
    assert result.metadata["formal_backtest_eligible"] is False
    assert "source_missing:CAToAsset" in result.limitations


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "sz.000001"},
        {"statDate": "2025-03-31"},
        {"pubDate": "2025-06-29"},
        {"pubDate": "2099-01-01"},
        {"pubDate": "2025-02-30"},
        {"CFOToOR": "NaN"},
        {"CFOToOR": "inf"},
        {"CFOToOR": True},
        {"CFOToOR": 1},
        {"CFOToOR": None},
    ],
)
def test_bad_source_values_fail_closed(changes):
    with pytest.raises(ProviderError):
        replay([row(**changes)])


def test_projection_rejects_duplicate_keys_fields_rows_and_bad_json():
    from app.research_web.datahub.providers_baostock_cashflow import cash_flow_projection

    for raw in (
        b"{",
        b"{}",
        b"null",
        json.dumps([row(), row()]).encode(),
        json.dumps([row(extra="1")]).encode(),
        json.dumps([row()]).replace('"code":', '"code":"sh.600000","code":').encode(),
    ):
        with pytest.raises(ProviderError):
            cash_flow_projection(raw, "600000.SH", "2025-06-30")


def test_missing_values_partial_and_empty_unknown():
    result = replay([row(pubDate="")])
    assert result.status == "partial" and result.missing == ["publication_date"]
    result = replay([row(**dict.fromkeys(FIELDS.split(",")[3:], ""))])
    assert result.status == "partial" and result.missing == ["cash_flow_metrics"]
    assert replay([]).status == "empty"


@pytest.mark.parametrize(
    "periods", [[], ["2016-12-31"], ["2025-06-29"], ["2099-03-31"], ["2025-03-31", "2025-06-30"]]
)
def test_closed_periods(periods):
    with pytest.raises(ProviderError):
        invoke(query(periods=periods), sdk=SimpleNamespace())


@pytest.mark.parametrize(
    "updates",
    [
        {"source": "akshare"},
        {"purpose": "backtest"},
        {"as_of": "2025-09-01"},
        {"required_semantics": "unsupported"},
    ],
)
def test_closed_query_rejects_before_sdk(updates):
    with pytest.raises(ProviderError):
        invoke(query().model_copy(update=updates), sdk=SimpleNamespace())


def test_sdk_missing_and_vendor_schema_rejected():
    with (
        patch("importlib.import_module", side_effect=ImportError),
        pytest.raises(ProviderError, match="missing_dependency"),
    ):
        invoke(query())
    with pytest.raises(ProviderError, match="vendor_schema_invalid"):
        invoke(query(), sdk=SimpleNamespace(query_cash_flow_data=lambda **_: Rows("code", [])))


def test_broker_only_selects_matching_cash_flow_binding(monkeypatch):
    from app.research_web.datahub.broker import resolve
    from app.research_web.datahub.catalog import build_catalog

    monkeypatch.setattr(
        "app.research_web.datahub.catalog._dependency_status", lambda *_: (True, None)
    )
    catalog = build_catalog(environ={})
    binding = next(
        b
        for b in catalog["bindings"]
        if b["source_id"] == "baostock" and b["capability_id"] == "financials"
    )
    assert "quarterly_cash_flow_ratios" in binding["datasets"]
    assert (
        resolve(query().model_copy(update={"source": "auto"}), environ={}).provider_id == "baostock"
    )


def test_cash_flow_source_mismatch_never_falls_back(monkeypatch):
    from app.research_web.datahub.broker import resolve
    from app.research_web.store import StoreError

    monkeypatch.setattr(
        "app.research_web.datahub.catalog._dependency_status", lambda *_: (True, None)
    )
    for source in ("akshare", "wind", "tinysoft"):
        with pytest.raises(StoreError):
            resolve(
                query().model_copy(update={"source": source, "allow_fallback": True}), environ={}
            )
    with pytest.raises(StoreError):
        resolve(
            query().model_copy(update={"source": "auto"}),
            environ={},
            excluded_sources=frozenset({"baostock"}),
        )


def test_sdk_field_missing_extra_duplicate_and_failed_response():
    for response in (
        Rows(FIELDS + ",extra", []),
        Rows(FIELDS + ",CFOToNP", []),
        SimpleNamespace(error_code="1"),
    ):
        with pytest.raises(ProviderError):
            invoke(
                query(),
                sdk=SimpleNamespace(query_cash_flow_data=lambda response=response, **_: response),
            )


def test_metadata_freshness_and_official_dictionary_binding():
    from app.research_web.datahub.providers_baostock import (
        FINANCIAL_DICTIONARY,
        FINANCIAL_DICTIONARY_SHA256,
    )
    from app.research_web.datahub.providers_baostock_cashflow import (
        cash_flow_fields,
        cash_flow_metadata,
    )

    metadata = cash_flow_metadata()
    evidence = metadata["field_dictionary_evidence"]
    assert evidence["source_url"] == FINANCIAL_DICTIONARY
    assert evidence["document_sha256"] == FINANCIAL_DICTIONARY_SHA256
    assert evidence["fields"] == FIELDS.split(",")[3:]
    evidence["fields"].clear()
    fields = cash_flow_fields()
    fields["CFOToNP"]["unit"] = "CNY"
    assert len(cash_flow_metadata()["field_dictionary_evidence"]["fields"]) == 7
    assert cash_flow_fields()["CFOToNP"]["unit"] is None
