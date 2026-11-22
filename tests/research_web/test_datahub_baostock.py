"""Closed BaoStock queries and exact unit/identity validation; no paid calls."""

import base64
import json
import sys
import unittest
from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError


class Rows:
    error_code = "0"

    def __init__(self, fields, rows):
        self.fields, self.rows, self.index = fields.split(","), rows, -1

    def next(self):
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self):
        return self.rows[self.index]


class BaoStockTests(unittest.TestCase):
    def query(self, **parameters):
        return BusinessQuery(
            capability="market_bars",
            source="baostock",
            parameters={
                "asset": "600000.SH",
                "asset_type": "stock",
                "frequency": "daily",
                "adjustment": "none",
                "start_date": "2025-01-02",
                "end_date": "2025-01-03",
                **parameters,
            },
        )

    def test_raw_stock_units_and_exact_identity(self):
        from app.research_web.datahub.providers_baostock import invoke

        calls = []
        fields = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus,pctChg"

        def history(**kwargs):
            calls.append(kwargs)
            return Rows(
                fields,
                [
                    [
                        "2025-01-02",
                        "sh.600000",
                        "10",
                        "12",
                        "9",
                        "11",
                        "1000",
                        "11000",
                        "3",
                        "1",
                        "2",
                    ]
                ],
            )

        sdk = SimpleNamespace(query_history_k_data_plus=history)
        result = invoke(self.query(), sdk=sdk)
        self.assertEqual(result.rows[0]["volume"], 1000)
        self.assertEqual(result.rows[0]["turnover"], 11000)
        self.assertEqual(result.rows[0]["asset"], "600000.SH")
        self.assertEqual(result.fields["volume"]["unit"], "share")
        self.assertEqual(calls[0]["adjustflag"], "3")

    def test_non_equivalent_queries_fail_before_sdk(self):
        from app.research_web.datahub.providers_baostock import validate_supported_query

        for kwargs in (
            {"adjustment": "qfq"},
            {"asset_type": "etf"},
            {"asset": "600000.SZ"},
            {"frequency": "weekly"},
        ):
            with self.assertRaises(ProviderError):
                validate_supported_query(self.query(**kwargs))

    def test_different_security_and_adjustment_are_rejected(self):
        from app.research_web.datahub.providers_baostock import invoke

        fields = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus,pctChg"
        for code, flag in [("sz.000001", "3"), ("sh.600000", "2")]:
            sdk = SimpleNamespace(
                query_history_k_data_plus=lambda fixed_code=code, flag=flag, **_: Rows(
                    fields,
                    [
                        [
                            "2025-01-02",
                            fixed_code,
                            "10",
                            "12",
                            "9",
                            "11",
                            "1000",
                            "11000",
                            flag,
                            "1",
                            "2",
                        ]
                    ],
                )
            )
            with self.assertRaises(ProviderError):
                invoke(self.query(), sdk=sdk)

    def test_calendar_and_search_keep_existing_semantics(self):
        from app.research_web.datahub.providers_baostock import SEMANTICS_REVISION, invoke

        calendar = invoke(
            BusinessQuery(
                capability="trading_calendar",
                source="baostock",
                parameters={"start_date": "2025-01-02", "end_date": "2025-01-03"},
            ),
            sdk=SimpleNamespace(
                query_trade_dates=lambda **_: Rows(
                    "calendar_date,is_trading_day", [["2025-01-02", "1"]]
                )
            ),
        )
        search = invoke(
            BusinessQuery(
                capability="search_assets", source="baostock", parameters={"query": "synthetic"}
            ),
            sdk=SimpleNamespace(
                query_stock_basic=lambda: Rows(
                    "code,code_name,ipoDate,outDate,type,status",
                    [["sh.600000", "synthetic", "2017-01-01", "", "1", "1"]],
                )
            ),
        )
        self.assertEqual(
            calendar.rows, [{"date": "2025-01-02", "market": "CN", "is_trading_day": True}]
        )
        self.assertEqual(search.rows[0]["asset"], "600000.SH")
        for result in (calendar, search):
            self.assertEqual(result.metadata["provider_semantics_revision"], SEMANTICS_REVISION)
            self.assertNotIn("schema", result.metadata)


class BaoStockFinancialTests(unittest.TestCase):
    fields = (
        "code,pubDate,statDate,roeAvg,npMargin,gpMargin,netProfit,epsTTM,"
        "MBRevenue,totalShare,liqaShare"
    )

    def query(self, **parameters):
        return BusinessQuery(
            capability="financials",
            source="baostock",
            parameters={
                "asset": "600000.SH",
                "statements": ["profitability"],
                "periods": ["2026-06-30"],
                **parameters,
            },
        )

    def row(self, **overrides):
        # Synthetic values only: no real issuer financials are committed.
        return {
            "code": "sh.600000",
            "pubDate": "2026-08-20",
            "statDate": "2026-06-30",
            "roeAvg": "0.25",
            "npMargin": "0.5",
            "gpMargin": "",
            "netProfit": "123.0",
            "epsTTM": "0",
            "MBRevenue": "456.0",
            "totalShare": "789",
            "liqaShare": "700",
            **overrides,
        }

    def invoke_rows(self, rows):
        from app.research_web.datahub.providers_baostock import invoke

        calls = []

        def profit(**kwargs):
            calls.append(kwargs)
            return Rows(self.fields, [[row[key] for key in self.fields.split(",")] for row in rows])

        result = invoke(self.query(), sdk=SimpleNamespace(query_profit_data=profit))
        self.assertEqual(calls, [{"code": "sh.600000", "year": 2026, "quarter": 2}])
        return result

    def test_single_quarter_preserves_native_payload_and_date_precision(self):
        from app.research_web.datahub.providers_baostock import FINANCIAL_SCHEMA

        raw = self.row()
        result = self.invoke_rows([raw])
        self.assertEqual(json.loads(result.raw[0]), [raw])
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.rows[0]["asset"], "600000.SH")
        self.assertEqual(result.rows[0]["report_period"], "2026-06-30")
        self.assertEqual(result.rows[0]["publication_date"], "2026-08-20")
        self.assertEqual(result.rows[0]["publication_precision"], "date")
        self.assertNotIn("publication_at", result.rows[0])
        self.assertEqual(result.rows[0]["roeAvg"], 0.25)
        self.assertEqual(result.rows[0]["epsTTM"], 0)
        self.assertEqual(result.metadata["schema_version"], FINANCIAL_SCHEMA)
        self.assertNotIn("schema", result.metadata)
        self.assertEqual(result.metadata["provider_semantics_revision"], FINANCIAL_SCHEMA)
        self.assertEqual(result.metadata["availability_basis"], "first_observed")
        self.assertFalse(result.metadata["historical_point_in_time"])
        self.assertFalse(result.metadata["formal_backtest_eligible"])
        self.assertIn("historical_vintage_unverified", result.limitations)

    def test_only_documented_cny_fields_have_units(self):
        result = self.invoke_rows([self.row()])
        for key in ("netProfit", "MBRevenue"):
            self.assertEqual(result.fields[key]["unit"], "CNY")
            self.assertEqual(result.fields[key]["currency"], "CNY")
        for key in ("roeAvg", "npMargin", "gpMargin", "epsTTM", "totalShare", "liqaShare"):
            self.assertIsNone(result.fields[key]["unit"])
            self.assertIsNone(result.fields[key]["currency"])
        self.assertIn("field_dictionary_evidence", result.metadata)

    def test_closed_selectors_reject_before_sdk(self):
        from app.research_web.datahub.providers_baostock import invoke

        queries = [
            self.query(statements=value)
            for value in (None, [], "profitability", ["income_statement"], ["profitability"] * 2)
        ]
        queries.extend(
            self.query(periods=value)
            for value in (
                None,
                [],
                "2026-06-30",
                ["2026-06-30", "2026-03-31"],
                ["2026-06-29"],
                ["2016-12-31"],
                ["2099-03-31"],
                ["2026-6-30"],
                ["2026-02-30"],
                [1],
            )
        )
        queries.extend(
            self.query().model_copy(update={"source": source}) for source in ("akshare",)
        )
        queries.append(
            self.query().model_copy(update={"parameters": {**self.query().parameters, "extra": 1}})
        )
        for query in queries:
            with self.subTest(query=query), self.assertRaises(ProviderError):
                invoke(query, sdk=SimpleNamespace())

    def test_auto_source_is_eligible_for_broker_validation(self):
        from app.research_web.datahub.providers_baostock import validate_supported_query

        validate_supported_query(self.query().model_copy(update={"source": "auto"}))

    def test_financial_dates_use_shanghai_day_when_utc_is_previous_day(self):
        from app.research_web.datahub.providers_baostock import invoke

        instant = datetime(2099, 3, 30, 16, 30, tzinfo=UTC)

        class ShanghaiMidnight(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz)

        row = self.row(statDate="2099-03-31", pubDate="2099-03-31")
        sdk = SimpleNamespace(query_profit_data=lambda **_: Rows(self.fields, [list(row.values())]))
        query = self.query(periods=["2099-03-31"])
        with patch(
            "app.research_web.datahub.providers_baostock.datetime", ShanghaiMidnight, create=True
        ):
            result = invoke(query, sdk=sdk)
            self.assertEqual(result.rows[0]["publication_date"], "2099-03-31")
            self.assertEqual(result.rows[0]["report_period"], "2099-03-31")
            row["pubDate"] = "2099-04-01"
            with self.assertRaisesRegex(ProviderError, "^vendor_schema_invalid$"):
                invoke(query, sdk=sdk)
            with self.assertRaisesRegex(ProviderError, "^invalid_date_range$"):
                invoke(self.query(periods=["2099-06-30"]), sdk=SimpleNamespace())

    def test_historical_queries_are_not_equivalent(self):
        from app.research_web.datahub.providers_baostock import invoke

        for purpose in ("research", "backtest"):
            query = self.query().model_copy(
                update={"purpose": purpose, "as_of": datetime(2026, 9, 1, tzinfo=UTC)}
            )
            with self.assertRaisesRegex(ProviderError, "^data_not_equivalent$"):
                invoke(query, sdk=SimpleNamespace())

    def test_invalid_native_identity_dates_and_numbers_are_rejected(self):
        for override in (
            {"code": "sz.000001"},
            {"statDate": "2026-03-31"},
            {"statDate": "2026-06-30T00:00:00"},
            {"pubDate": "2026-02-30"},
            {"pubDate": "2099-01-01"},
            {"pubDate": "2026-06-29"},
            {"pubDate": 0},
            {"pubDate": False},
            {"netProfit": "NaN"},
            {"npMargin": float("inf")},
            {"roeAvg": True},
        ):
            with self.subTest(override=override), self.assertRaises(ProviderError):
                self.invoke_rows([self.row(**override)])

    def test_duplicate_and_extra_rows_are_rejected(self):
        for rows in ([self.row(), self.row()], [self.row(), self.row(code="sz.000001")]):
            with self.assertRaisesRegex(ProviderError, "^vendor_schema_invalid$"):
                self.invoke_rows(rows)

    def test_missing_publication_and_all_empty_numbers_are_partial_but_zero_is_valid(self):
        result = self.invoke_rows([self.row(pubDate="")])
        self.assertEqual(result.status, "partial")
        self.assertIsNone(result.rows[0]["publication_date"])
        self.assertIsNone(result.rows[0]["publication_precision"])
        numbers = self.fields.split(",")[3:]
        result = self.invoke_rows([self.row(**dict.fromkeys(numbers, ""))])
        self.assertEqual(result.status, "partial")
        result = self.invoke_rows([self.row(**dict.fromkeys(numbers, "0"))])
        self.assertEqual(result.status, "complete")

    def test_empty_is_not_a_proven_coverage_claim(self):
        result = self.invoke_rows([])
        self.assertEqual(result.status, "empty")
        self.assertIn("coverage_unknown", result.limitations)

    def test_sdk_schema_and_error_reject_safely(self):
        from app.research_web.datahub.providers_baostock import invoke

        for response in (
            Rows("code", [["sh.600000"]]),
            SimpleNamespace(error_code="1", error_msg="secret"),
        ):
            with self.assertRaises(ProviderError) as caught:
                invoke(
                    self.query(),
                    sdk=SimpleNamespace(query_profit_data=lambda response=response, **_: response),
                )
            self.assertNotIn("secret", str(caught.exception))

    def test_owned_guest_login_and_logout_on_success_and_vendor_failure(self):
        from app.research_web.datahub.providers_baostock import invoke

        for failed in (False, True):
            calls = []

            def profit(calls=calls, failed=failed, **kwargs):
                calls.append(("profit", kwargs))
                if failed:
                    raise RuntimeError("secret vendor diagnostics")
                return Rows(self.fields, [list(self.row().values())])

            sdk = SimpleNamespace(
                login=lambda calls=calls: calls.append("login") or SimpleNamespace(error_code="0"),
                logout=lambda calls=calls: calls.append("logout"),
                query_profit_data=profit,
            )
            with patch.dict(sys.modules, {"baostock": sdk}):
                if failed:
                    with self.assertRaisesRegex(ProviderError, "^vendor_unreachable$"):
                        invoke(self.query())
                else:
                    self.assertEqual(invoke(self.query()).status, "complete")
            self.assertEqual(
                calls,
                ["login", ("profit", {"code": "sh.600000", "year": 2026, "quarter": 2}), "logout"],
            )

    def test_financial_worker_result_roundtrip(self):
        from app.research_web.datahub.public_worker import invoke_worker

        original = self.invoke_rows([self.row()])
        payload = asdict(original)
        payload["raw"] = [base64.b64encode(part).decode() for part in original.raw]
        response = SimpleNamespace(
            returncode=0, stdout=json.dumps({"ok": True, "result": payload}).encode()
        )
        with patch("app.research_web.datahub.public_worker.subprocess.run", return_value=response):
            restored = invoke_worker("baostock", self.query())
        self.assertEqual(restored, original)
