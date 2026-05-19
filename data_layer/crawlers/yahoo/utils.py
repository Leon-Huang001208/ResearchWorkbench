"""
Yahoo Finance 工具函数

提供 Symbol 转换、数据格式化等功能。
"""
from typing import List, Optional


def convert_symbol(symbol: str, source: str = "akshare") -> str:
    """
    将其他数据源的 symbol 转换为 Yahoo 格式

    Args:
        symbol: 原始 symbol
        source: 原始数据源（akshare, baostock）

    Returns:
        Yahoo 格式的 symbol

    Symbol 格式说明:
        - 美股: AAPL, MSFT
        - 港股: 00700.HK, 00005.HK
        - A股: 600519.SS (上交所), 000001.SZ (深交所)
        - 指数: ^GSPC (S&P 500), ^DJI (道琼斯), ^IXIC (纳斯达克)
    """
    if source == "akshare":
        return _convert_akshare_symbol(symbol)
    elif source == "baostock":
        return _convert_baostock_symbol(symbol)
    else:
        return symbol


def _convert_akshare_symbol(symbol: str) -> str:
    """将 AkShare symbol 转换为 Yahoo 格式"""
    symbol = symbol.strip()

    if symbol.startswith("sh") and len(symbol) == 8:
        code = symbol[2:]
        return code + ".SS"
    elif symbol.startswith("sz") and len(symbol) == 8:
        code = symbol[2:]
        return code + ".SZ"

    if symbol.startswith("hk") and len(symbol) == 7:
        code = symbol[2:].zfill(4)
        return code + ".HK"

    if "." in symbol or symbol.startswith("^"):
        return symbol

    return symbol


def _convert_baostock_symbol(symbol: str) -> str:
    """将 BaoStock symbol 转换为 Yahoo 格式"""
    symbol = symbol.strip()

    if symbol.startswith("sh.") and len(symbol) == 9:
        code = symbol[3:]
        return code + ".SS"
    elif symbol.startswith("sz.") and len(symbol) == 9:
        code = symbol[3:]
        return code + ".SZ"

    if "." in symbol or symbol.startswith("^"):
        return symbol

    return symbol


def detect_market(symbol: str) -> Optional[str]:
    """
    检测 symbol 所属市场

    Returns:
        "us", "hk", "cn", "index", 或 None
    """
    symbol = symbol.strip()

    if symbol.startswith("^"):
        return "index"

    if symbol.endswith(".HK"):
        return "hk"

    if symbol.endswith(".SS") or symbol.endswith(".SZ"):
        return "cn"

    if "." not in symbol and symbol.isupper():
        return "us"

    return None


def get_supported_intervals() -> List[str]:
    """
    获取支持的 K线间隔列表

    Returns:
        支持的间隔列表
    """
    return [
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    ]


def get_supported_periods() -> List[str]:
    """
    获取支持的时间段列表

    Returns:
        支持的时间段列表
    """
    return [
        "1d",
        "5d",
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "5y",
        "10y",
        "ytd",
        "max",
    ]


def is_valid_yahoo_symbol(symbol: str) -> bool:
    """
    检查是否是有效的 Yahoo symbol 格式

    Args:
        symbol: 待检查的 symbol

    Returns:
        是否有效
    """
    if not symbol or not isinstance(symbol, str):
        return False

    symbol = symbol.strip()
    if not symbol:
        return False

    if symbol.startswith("^"):
        return len(symbol) > 1

    if "." in symbol:
        parts = symbol.split(".")
        return len(parts[0]) > 0 and len(parts[1]) > 0

    return symbol.isalnum()
