"""akshare financial normalizer 单元测试"""
from datetime import date

from data_layer.crawlers.akshare.base import FinancialData
from data_layer.normalizers.akshare_financial import normalize_financial_data


def test_normalize_financial_data():
    item = FinancialData(
        symbol="600519.SH",
        report_date=date(2024, 3, 31),
        report_type="quarterly",
        total_revenue=457.8e8,
        net_profit=240.7e8,
        total_assets=3000e8,
        total_liabilities=500e8,
        equity=2500e8,
        roe=9.63,
        roa=8.02,
        gross_margin=92.5,
        net_margin=52.6,
        debt_ratio=16.7,
    )
    result = normalize_financial_data(item)

    assert result["symbol"] == "600519.SH"
    assert result["report_date"] == date(2024, 3, 31)
    assert result["report_type"] == "quarterly"
    assert float(result["total_revenue"]) == 45780000000.0
    assert float(result["net_profit"]) == 24070000000.0
    assert float(result["roe"]) == 9.63
    assert float(result["gross_margin"]) == 92.5
    assert result["source"] == "akshare"
    assert result["raw_payload"] == {}
