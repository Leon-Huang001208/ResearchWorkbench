"""Closed BaoStock queries and exact unit/identity validation; no paid calls."""

import unittest
from types import SimpleNamespace

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
