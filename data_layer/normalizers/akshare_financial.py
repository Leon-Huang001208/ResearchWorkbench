"""AkShare 财务数据标准化器

将 crawler 输出的 FinancialData dataclass 转为标准化 dict，
用于写入 stock_financial_metric 表。
"""

from data_layer.crawlers.akshare.base import FinancialData
from data_layer.normalizers.common import to_decimal


def normalize_financial_data(item: FinancialData) -> dict:
    """将 FinancialData dataclass 转为 stock_financial_metric 表格式"""
    return {
        "symbol": item.symbol,
        "report_date": item.report_date,
        "report_type": item.report_type,
        "total_revenue": to_decimal(item.total_revenue),
        "net_profit": to_decimal(item.net_profit),
        "total_assets": to_decimal(item.total_assets),
        "total_liabilities": to_decimal(item.total_liabilities),
        "equity": to_decimal(item.equity),
        "roe": to_decimal(item.roe),
        "roa": to_decimal(item.roa),
        "gross_margin": to_decimal(item.gross_margin),
        "net_margin": to_decimal(item.net_margin),
        "debt_ratio": to_decimal(item.debt_ratio),
        "source": "akshare",
        "raw_payload": item.extra or {},
    }
