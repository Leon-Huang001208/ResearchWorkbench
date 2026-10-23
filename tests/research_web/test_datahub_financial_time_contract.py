"""Offline disclosure contracts do not manufacture historical vintages or units."""

import copy
import json
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pandas as pd
import pytest
from pydantic import ValidationError

from app.research_web.datahub import providers_akshare as provider
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError


def query(**updates):
    return BusinessQuery(
        capability="financials",
        source="akshare",
        parameters={"asset": "600600.SH", "statements": ["income_statement"], **updates},
    )


def test_disclosure_natural_day_uses_shanghai_not_utc(monkeypatch):
    class ShanghaiMidnight(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 8, 26, 16, 30, tzinfo=UTC)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(provider, "datetime", ShanghaiMidnight)
    result, _calls = replay()
    assert result.rows[0]["publication_date"] == "2026-08-27"
    with pytest.raises(ValueError, match="future_day"):
        provider._sina_day("20260828")


@pytest.mark.parametrize("value,expected", [(None, "partial"), ("0", "snapshot")])
def test_all_missing_financial_values_are_not_a_numeric_success(value, expected):
    payload = envelope()
    for item in payload["result"]["data"]["report_list"]["20260630"]["data"]:
        item["item_value"] = value
    result, _calls = replay(payload)
    assert result.status == expected
    if value is None:
        assert "financial_numeric_values_missing" in result.missing


@pytest.mark.parametrize("transport", ["akshare_sdk", "webguest"])
def test_flow_endpoint_attempts_survive_native_freeze_restore(transport):
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.research_snapshot_store import START, SnapshotSeries
    from app.research_web.market_store import (
        InMemoryMarketStore,
        MarketStoreError,
        MarketStoreService,
        StoreScope,
    )

    scope = StoreScope("alice", "personal", "akshare", "a" * 64)
    service = MarketStoreService(
        InMemoryMarketStore(),
        lambda actor, requested, _action: actor == "alice" and requested == scope,
    )
    series = SnapshotSeries(service, "alice", scope)
    request = BusinessQuery(
        capability="market_activity",
        source="akshare",
        parameters={"asset": "600600.SH", "dataset": "fund_flow"},
        purpose="display",
        quality="allow_stale",
    )
    attempts = [
        {
            "upstream": "eastmoney",
            "endpoint": "akshare_sdk",
            "status": "snapshot" if transport == "akshare_sdk" else "failed",
        }
    ]
    if transport == "webguest":
        attempts.append({"upstream": "eastmoney", "endpoint": "webguest", "status": "snapshot"})
    response = Result(
        rows=[{"date": "2026-08-27", "main_net": 1}],
        raw=[b"synthetic-flow"],
        status="snapshot",
        provider_id="akshare",
        metadata={
            "schema_version": provider.FUND_FLOW_SCHEMA,
            "upstream_id": "eastmoney",
            "transport": transport,
            "independent_source": False,
            "upstream_attempts": attempts,
            "token": "must-not-save",
        },
    )
    series.ingest(request, response)
    frozen = service.freeze("alice", scope, series.dataset(request), START, START)
    other = MarketStoreService(
        InMemoryMarketStore(),
        lambda actor, requested, _action: actor == "alice" and requested == scope,
    )
    other.export_restore("alice", scope, frozen.export())
    restored = SnapshotSeries(other, "alice", scope).read(request)
    assert restored.metadata["upstream_attempts"] == attempts
    assert restored.metadata["independent_source"] is False
    assert "token" not in restored.metadata
    response.metadata["upstream_attempts"][0]["token"] = "must-not-save"
    with pytest.raises(MarketStoreError, match="snapshot_attempt_evidence_invalid"):
        series.ingest(request, response)


def test_income_statement_auto_never_selects_a_generic_financial_summary(monkeypatch):
    from app.research_web.datahub import broker
    from app.research_web.datahub.catalog import build_catalog

    catalog = build_catalog(environ={})
    for source in catalog["sources"]:
        source["readiness"].update(
            configured=True,
            dependency_ready=True,
            allowed=True,
            integration_completed=True,
            health="healthy",
        )
    monkeypatch.setattr(broker, "build_catalog", lambda **_kwargs: catalog)
    selected = broker.resolve(query(periods=1).model_copy(update={"source": "auto"}))
    assert selected.provider_id == "akshare"


def envelope():
    return {
        "result": {
            "status": {"code": 0},
            "data": {
                "report_count": "117",
                "report_date": [
                    {"date_value": "20260630", "date_description": "2026半年报", "date_type": 2}
                ],
                "report_list": {
                    "20260630": {
                        "rType": "合并期末",
                        "rCurrency": "CNY",
                        "data_source": "定期报告",
                        "is_audit": "未审计",
                        "publish_date": "20260827",
                        "update_time": 1787746924,
                        "data": [
                            {
                                "item_field": "BIZINCO",
                                "item_title": "营业收入",
                                "item_value": "19654849637.000000",
                                "item_source": "lrb",
                                "item_precision": "f2",
                                "item_display_type": 1,
                            },
                            {
                                "item_field": "UNKNOWN_NEW",
                                "item_title": "新字段",
                                "item_value": None,
                                "item_source": "lrb",
                            },
                        ],
                    }
                },
            },
        }
    }


def replay(body=None, request=None, status=200):
    raw = (
        body
        if isinstance(body, bytes)
        else json.dumps(body if body is not None else envelope(), ensure_ascii=False).encode()
    )
    original = httpx.Client
    calls = []

    def handler(req):
        calls.append(req)
        assert req.url.host == "quotes.sina.cn"
        assert dict(req.url.params) == {
            "paperCode": "sh600600",
            "source": "lrb",
            "type": "0",
            "page": "1",
            "num": "8",
        }
        return httpx.Response(status, content=raw)

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch.dict(sys.modules, {"akshare": SimpleNamespace()}),
        patch.object(provider.httpx, "Client", side_effect=client),
    ):
        result = provider.invoke_public(request or query())
    assert len(calls) == 1
    return result, raw


def test_preserves_wire_items_and_disclosure_date_without_pit_or_unit_invention():
    result, raw = replay()
    assert result.raw == [raw]
    assert result.status == "snapshot"
    assert result.provider_total == 117
    assert result.pagination_complete is False
    row = result.rows[0]
    assert row["asset"] == "600600.SH"
    assert row["report_period"] == "2026-06-30"
    assert row["publication_date"] == "2026-08-27"
    assert row["publication_precision"] == "date"
    assert "publication_at" not in row
    assert row["supplier_update_time"] == 1787746924
    assert row["data"] == envelope()["result"]["data"]["report_list"]["20260630"]["data"]
    assert result.metadata["schema_version"] == provider.SINA_FINANCIAL_SCHEMA
    assert result.metadata["upstream_id"] == "sina"
    assert result.metadata["availability_basis"] == "first_observed"
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert result.metadata["field_dictionary_evidence"]["unit_status"] == "unverified"
    assert all(field["unit"] is None for field in result.fields.values())


def test_explicit_period_missing_is_partial_and_never_substituted():
    result, _ = replay(request=query(periods=["2025-12-31"]))
    assert result.rows == []
    assert result.status == "partial"
    assert "requested_report_periods_missing" in result.missing


def test_duplicate_json_keys_and_nonfinite_extra_values_fail_closed():
    raw = json.dumps(envelope()).encode().replace(b'"code": 0', b'"code": 1, "code": 0')
    with pytest.raises(ProviderError):
        replay(raw)
    body = envelope()
    body["result"]["data"]["report_list"]["20260630"]["data"][0]["item_tongbi"] = float("inf")
    with pytest.raises(ProviderError):
        replay(body)


@pytest.mark.parametrize("status", [302, 403, 500])
def test_http_errors_are_one_request_without_fallback(status):
    with pytest.raises(ProviderError, match="vendor_unreachable"):
        replay(status=status)


def test_backtest_and_asof_are_denied_before_http():
    for change in ({"purpose": "backtest"}, {"as_of": "2026-08-28T00:00:00Z"}):
        request = query().model_copy(update=change)
        with (
            patch.object(provider.httpx, "Client", side_effect=AssertionError("no HTTP")),
            pytest.raises(ProviderError),
        ):
            provider.invoke_public(request)


@pytest.mark.parametrize(
    "updates",
    [
        {"asset": "600600"},
        {"asset": "600600.SZ"},
        {"asset": "830001.BJ"},
        {"periods": 9},
        {"periods": 0},
        {"periods": ["2026-06-30"] * 2},
        {"periods": ["2026-06-29"]},
        {"url": "https://example.com"},
    ],
)
def test_closed_requests_fail_before_http(updates):
    with (
        patch.object(provider.httpx, "Client", side_effect=AssertionError("no HTTP")),
        pytest.raises((ProviderError, ValidationError)),
    ):
        provider.invoke_public(query(**updates))


@pytest.mark.parametrize(
    "case",
    [
        "error",
        "bool_code",
        "missing_report",
        "extra_report",
        "duplicate_date",
        "bad_date",
        "type_conflict",
        "currency_conflict",
        "publication_conflict",
        "bad_update",
        "duplicate_item",
        "nonfinite",
        "boolean",
        "source_conflict",
    ],
)
def test_bad_envelopes_fail_closed(case):
    body = envelope()
    data = body["result"]["data"]
    report = data["report_list"]["20260630"]
    if case == "error":
        body["result"]["status"]["code"] = 1
    if case == "bool_code":
        body["result"]["status"]["code"] = False
    if case == "missing_report":
        data["report_list"] = {}
    if case == "extra_report":
        data["report_list"]["20260331"] = copy.deepcopy(report)
    if case == "duplicate_date":
        data["report_date"] *= 2
    if case == "bad_date":
        data["report_date"][0]["date_value"] = "20260631"
    if case == "type_conflict":
        data["report_date"][0]["date_type"] = 4
    if case == "currency_conflict":
        report["rCurrency"] = "USD"
    if case == "publication_conflict":
        report["publish_date"] = "20260629"
    if case == "bad_update":
        report["update_time"] = True
    if case == "duplicate_item":
        report["data"].append(copy.deepcopy(report["data"][0]))
    if case == "nonfinite":
        report["data"][0]["item_value"] = "NaN"
    if case == "boolean":
        report["data"][0]["item_value"] = True
    if case == "source_conflict":
        report["data"][0]["item_source"] = "fzb"
    with pytest.raises(ProviderError):
        replay(body)


def test_missing_publication_precision_is_partial_never_pit():
    body = envelope()
    del body["result"]["data"]["report_list"]["20260630"]["publish_date"]
    result, _ = replay(body)
    assert result.status == "partial"
    assert result.rows[0]["publication_date"] is None
    assert result.rows[0]["publication_precision"] == "unknown"
    assert result.metadata["historical_point_in_time"] is False


@pytest.mark.parametrize("statement", ["metrics", "indicators"])
def test_old_abstract_contract_keeps_sdk_and_normalizer(statement):
    calls = []

    def abstract(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame([{"报告期": "2024-12-31", "营业收入": "2亿元"}])

    with patch.dict(
        sys.modules, {"akshare": SimpleNamespace(stock_financial_abstract_ths=abstract)}
    ):
        result = provider.invoke_public(query(statements=[statement], periods=["2024-12-31"]))
    assert calls == [{"symbol": "600600", "indicator": "按报告期"}]
    assert result.rows[0]["revenue"] == 200000000
    assert "schema_version" not in result.metadata


def test_fund_flow_sdk_and_guest_have_same_nonindependent_source():
    request = BusinessQuery(
        capability="market_activity",
        source="akshare",
        parameters={"asset": "600600.SH", "dataset": "fund_flow"},
    )
    sdk = SimpleNamespace(
        stock_individual_fund_flow=lambda **kwargs: pd.DataFrame(
            [{"日期": "2026-06-30", "主力净流入-净额": 10}]
        )
    )
    with patch.dict(sys.modules, {"akshare": sdk}):
        result = provider.invoke_public(request)
    assert result.metadata["upstream_id"] == "eastmoney"
    assert result.metadata["transport"] == "akshare_sdk"
    assert result.metadata["independent_source"] is False
    assert result.metadata["availability_basis"] == "first_observed"
    assert result.metadata["historical_point_in_time"] is False
    assert result.metadata["formal_backtest_eligible"] is False
    assert "fund_flow_units_unverified" in result.limitations
