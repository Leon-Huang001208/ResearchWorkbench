"""akshare market normalizer 单元测试"""
from datetime import date, datetime

from data_layer.crawlers.akshare.base import MarketData, StockInfo
from data_layer.normalizers.akshare_market import normalize_market_data, normalize_stock_info


def test_normalize_market_data_basic():
    item = MarketData(
        symbol="600519.SH",
        timestamp=datetime(2024, 1, 15),
        open=1700.0,
        high=1720.0,
        low=1690.0,
        close=1715.0,
        volume=1000000,
        amount=1.7e9,
        turnover=0.8,
    )
    result = normalize_market_data(item)

    assert result["symbol"] == "600519.SH"
    assert result["trade_date"] == datetime(2024, 1, 15)
    assert float(result["open"]) == 1700.0
    assert float(result["close"]) == 1715.0
    assert float(result["volume"]) == 1000000
    assert float(result["turnover"]) == 0.8
    assert result["source"] == "akshare"
    assert result["raw_payload"] == {}


def test_normalize_market_data_none_fields():
    item = MarketData(
        symbol="000001.SZ",
        timestamp=datetime(2024, 1, 15),
        open=None,
        high=None,
        low=None,
        close=None,
    )
    result = normalize_market_data(item)

    assert result["open"] is None
    assert result["high"] is None
    assert result["close"] is None


def test_normalize_stock_info():
    item = StockInfo(
        symbol="600519.SH",
        name="贵州茅台",
        market="sh",
        industry="白酒",
        list_date=date(2001, 8, 27),
    )
    result = normalize_stock_info(item)

    assert result["symbol"] == "600519.SH"
    assert result["raw_code"] == "600519"
    assert result["name"] == "贵州茅台"
    assert result["exchange"] == "SH"
    assert result["market"] == "A-share"
    assert result["industry_level1"] == "白酒"
    assert result["list_date"] == date(2001, 8, 27)
    assert result["source"] == "akshare"


def test_normalize_stock_info_no_dot():
    """symbol 中无 . 号时用 market 字段作为 exchange"""
    item = StockInfo(
        symbol="600519",
        name="贵州茅台",
        market="SHA",
        industry=None,
        list_date=None,
    )
    result = normalize_stock_info(item)

    assert result["symbol"] == "600519"
    assert result["exchange"] == "SHA"
