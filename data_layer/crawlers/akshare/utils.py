"""
AkShare 工具函数模块
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from core.observability import get_logger

logger = get_logger("akshare_utils")


def df_to_dict_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    将 DataFrame 转换为字典列表

    Args:
        df: pandas DataFrame

    Returns:
        字典列表
    """
    if df is None or df.empty:
        return []

    # 替换 NaN 为 None
    df_clean = df.where(pd.notna(df), None)
    return [{str(k): v for k, v in row.items()} for row in df_clean.to_dict("records")]


def safe_float(value: Any) -> Optional[float]:
    """
    安全转换为浮点数

    Args:
        value: 任意值

    Returns:
        浮点数或 None
    """
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> Optional[int]:
    """
    安全转换为整数

    Args:
        value: 任意值

    Returns:
        整数或 None
    """
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_date(date_str: str, default: Optional[date] = None) -> Optional[date]:
    """
    解析日期字符串

    Args:
        date_str: 日期字符串
        default: 默认值

    Returns:
        date 对象或 None
    """
    if not date_str:
        return default

    date_str = str(date_str).strip()

    formats = [
        "%Y-%m-%d",
        "%Y%m%d",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%Y-%m",
        "%Y%m",
        "%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.date()
        except ValueError:
            continue

    return default


def parse_datetime(datetime_str: str, default: Optional[datetime] = None) -> Optional[datetime]:
    """
    解析日期时间字符串

    Args:
        datetime_str: 日期时间字符串
        default: 默认值

    Returns:
        datetime 对象或 None
    """
    if not datetime_str:
        return default

    datetime_str = str(datetime_str).strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue

    return default


def normalize_symbol(symbol: str) -> str:
    """
    标准化股票代码

    Args:
        symbol: 原始股票代码

    Returns:
        标准化后的代码 (带市场后缀)
    """
    symbol = str(symbol).strip().upper()

    # 已经有后缀
    if "." in symbol:
        return symbol

    # 推断市场
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    elif symbol.startswith("0") or symbol.startswith("3"):
        return f"{symbol}.SZ"
    elif symbol.startswith("8") or symbol.startswith("4"):
        return f"{symbol}.BJ"
    else:
        # 默认上海
        return f"{symbol}.SH"


def clean_symbol(symbol: str) -> str:
    """
    清理股票代码，去除市场后缀

    Args:
        symbol: 原始股票代码

    Returns:
        纯数字代码
    """
    symbol = str(symbol).strip().upper()

    if "." in symbol:
        return symbol.split(".")[0]

    return symbol


def get_date_range(
    start_date: Optional[Union[date, str, int]] = None,
    end_date: Optional[Union[date, str, int]] = None,
    days: int = 365,
) -> tuple[date, date]:
    """
    获取日期范围

    Args:
        start_date: 开始日期
        end_date: 结束日期
        days: 默认天数

    Returns:
        (start_date, end_date)
    """
    if end_date is None:
        _end_date = date.today()
    elif isinstance(end_date, str):
        _end_date = parse_date(end_date, date.today())
    elif isinstance(end_date, int):
        _end_date = date.today() - timedelta(days=end_date)
    else:
        _end_date = end_date

    if start_date is None:
        _start_date = _end_date - timedelta(days=days)
    elif isinstance(start_date, str):
        _start_date = parse_date(start_date, _end_date - timedelta(days=days))
    elif isinstance(start_date, int):
        _start_date = _end_date - timedelta(days=start_date)
    else:
        _start_date = start_date

    return _start_date, _end_date


def format_date_for_akshare(d: date) -> str:
    """
    格式化日期为 AkShare 要求的格式 (YYYYMMDD)

    Args:
        d: 日期对象

    Returns:
        格式化字符串
    """
    return d.strftime("%Y%m%d")


def deduplicate_by_key(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    """
    根据键去重

    Args:
        items: 字典列表
        key: 去重键

    Returns:
        去重后的列表
    """
    seen = set()
    result: List[Dict[str, Any]] = []

    for item in items:
        value = item.get(key)
        if value not in seen:
            seen.add(value)
            result.append(item)

    return result
