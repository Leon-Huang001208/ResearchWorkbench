"""AkShare 市场数据标准化器

将 crawler 输出的 MarketData / StockInfo dataclass 转为标准化 dict，
用于写入 SQL 结构化表。
"""
from data_layer.crawlers.akshare.base import MarketData, StockInfo
from data_layer.normalizers.common import to_decimal


def normalize_market_data(item: MarketData) -> dict:
    """将 MarketData dataclass 转为 stock_daily_bar 表格式"""
    return {
        "symbol": item.symbol,
        "trade_date": item.timestamp,
        "open": to_decimal(item.open),
        "high": to_decimal(item.high),
        "low": to_decimal(item.low),
        "close": to_decimal(item.close),
        "volume": to_decimal(item.volume),
        "amount": to_decimal(item.amount),
        "turnover": to_decimal(item.turnover),
        "source": item.source,
        "raw_payload": item.extra or {},
    }


def normalize_stock_info(item: StockInfo) -> dict:
    """将 StockInfo dataclass 转为 stock_master 表格式"""
    return {
        "symbol": item.symbol,
        "raw_code": item.symbol.split(".")[0],
        "name": item.name,
        "exchange": item.symbol.split(".")[-1] if "." in item.symbol else item.market,
        "market": "A-share",
        "industry_level1": item.industry,
        "industry_level2": None,
        "industry_level3": None,
        "list_date": item.list_date,
        "source": "akshare",
    }
