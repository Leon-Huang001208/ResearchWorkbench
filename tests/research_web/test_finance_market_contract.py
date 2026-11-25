"""Gangtise normalization rejects non-equivalent or incomplete payloads."""

import unittest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_finance_market import project, validate_supported_query


def query(**params):
    return BusinessQuery(
        capability="market_bars",
        source="ext_finance_mcp",
        parameters={
            "asset": "600519.SH",
            "asset_type": "stock",
            "frequency": "daily",
            "adjustment": "none",
            "start_date": "2026-11-10",
            "end_date": "2026-11-13",
            **params,
        },
    )


def row(**values):
    return {
        "securityCode": "600519.SH",
        "tradeDate": "2026-11-10",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "volume": 100,
        "amount": 1100,
        **values,
    }


class FinanceMarketTests(unittest.TestCase):
    def test_maps_native_amount_without_rescaling_volume(self):
        result = project(query(), [row()], 1)
        self.assertEqual(result[0]["turnover"], 1100)
        self.assertEqual(result[0]["volume"], 100)
        self.assertEqual(result[0]["adjustment"], "none")

    def test_truncated_response_is_rejected(self):
        with self.assertRaises(ProviderError):
            project(query(), [row()], 2)

    def test_mixed_asset_response_is_rejected(self):
        with self.assertRaises(ProviderError):
            project(query(), [row(securityCode="000001.SZ")], 1)

    def test_duplicate_dates_are_rejected(self):
        with self.assertRaises(ProviderError):
            project(query(), [row(), row()], 2)

    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaises(ProviderError):
            project(query(), [row(high=8)], 1)

    def test_adjustment_not_inferred_from_factor(self):
        with self.assertRaises(ProviderError):
            validate_supported_query(query(adjustment="qfq"))

    def test_empty_response_needs_explicit_zero_total(self):
        self.assertEqual(project(query(), [], 0), [])
        with self.assertRaises(ProviderError):
            project(query(), [], None)
