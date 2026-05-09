"""
AkShare 财务数据获取器
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from core.observability import get_logger

from .base import BaseAkShareFetcher, FinancialData
from .config import AkShareConfig

logger = get_logger("akshare_financial")


class AkShareFinancialFetcher(BaseAkShareFetcher):
    """AkShare 财务数据获取器"""

    def __init__(self, config: Optional[AkShareConfig] = None):
        super().__init__(config)

    def get_financial_abstract(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取个股财务摘要

        Args:
            symbol: 股票代码

        Returns:
            财务摘要字典
        """
        self._initialize()
        clean_symbol = self._clean_symbol(symbol)
        logger.debug(f"Fetching financial abstract for {clean_symbol}")

        try:
            # 使用同花顺财务摘要接口
            df = self.ak.stock_financial_abstract_ths(symbol=clean_symbol, indicator="按报告期")

            if df is None or df.empty:
                logger.warning(f"No financial abstract for {symbol}")
                return None

            # 转换为字典，返回最新一期
            result = df.iloc[0].to_dict() if not df.empty else {}
            logger.info(f"Fetched financial abstract for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch financial abstract for {symbol}: {e}")
            return None

    def get_financial_indicators(self, symbol: str) -> List[FinancialData]:
        """
        获取财务指标数据

        Args:
            symbol: 股票代码

        Returns:
            财务数据列表
        """
        self._initialize()
        clean_symbol = self._clean_symbol(symbol)
        logger.debug(f"Fetching financial indicators for {clean_symbol}")

        try:
            # 获取主要财务指标
            df = self.ak.stock_financial_abstract_ths(symbol=clean_symbol, indicator="按报告期")

            if df is None or df.empty:
                logger.warning(f"No financial indicators for {symbol}")
                return []

            result: List[FinancialData] = []

            for _, row in df.iterrows():
                try:
                    report_date = self._parse_report_date(row)
                    if report_date is None:
                        continue

                    financial_data = FinancialData(
                        symbol=symbol,
                        report_date=report_date,
                        report_type=self._infer_report_type(report_date),
                        # 尝试解析各种财务指标
                        total_revenue=self._safe_float(row, "营业总收入"),
                        net_profit=self._safe_float(row, "净利润"),
                        total_assets=self._safe_float(row, "总资产"),
                        total_liabilities=self._safe_float(row, "总负债"),
                        equity=self._safe_float(row, "股东权益合计"),
                        roe=self._safe_float(row, "净资产收益率"),
                        roa=self._safe_float(row, "总资产净利率"),
                        gross_margin=self._safe_float(row, "销售毛利率"),
                        net_margin=self._safe_float(row, "销售净利率"),
                        debt_ratio=self._safe_float(row, "资产负债率"),
                        extra=row.to_dict(),
                    )
                    result.append(financial_data)
                except Exception as e:
                    logger.debug(f"Error processing financial row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} financial records for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch financial indicators for {symbol}: {e}")
            return []

    def get_earnings_report(
        self, symbol: str, year: Optional[int] = None, quarter: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取业绩报表

        Args:
            symbol: 股票代码
            year: 年份
            quarter: 季度 (1-4)

        Returns:
            业绩报表数据
        """
        self._initialize()
        clean_symbol = self._clean_symbol(symbol)
        logger.debug(f"Fetching earnings report for {clean_symbol}")

        try:
            # 获取利润表
            df = self.ak.stock_profit_sheet_by_yearly_em(symbol=clean_symbol)

            if df is None or df.empty:
                logger.warning(f"No earnings report for {symbol}")
                return None

            if year is not None:
                # 筛选指定年份
                year_str = str(year)
                df = df[df.astype(str).apply(lambda x: x.str.contains(year_str)).any(axis=1)]

            result = df.iloc[0].to_dict() if not df.empty else {}
            logger.info(f"Fetched earnings report for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch earnings report for {symbol}: {e}")
            return None

    def get_balance_sheet(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取资产负债表

        Args:
            symbol: 股票代码

        Returns:
            资产负债表数据
        """
        self._initialize()
        clean_symbol = self._clean_symbol(symbol)
        logger.debug(f"Fetching balance sheet for {clean_symbol}")

        try:
            df = self.ak.stock_balance_sheet_by_yearly_em(symbol=clean_symbol)

            if df is None or df.empty:
                logger.warning(f"No balance sheet for {symbol}")
                return None

            result = df.iloc[0].to_dict() if not df.empty else {}
            logger.info(f"Fetched balance sheet for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch balance sheet for {symbol}: {e}")
            return None

    def get_cash_flow_sheet(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取现金流量表

        Args:
            symbol: 股票代码

        Returns:
            现金流量表数据
        """
        self._initialize()
        clean_symbol = self._clean_symbol(symbol)
        logger.debug(f"Fetching cash flow sheet for {clean_symbol}")

        try:
            df = self.ak.stock_cash_flow_sheet_by_yearly_em(symbol=clean_symbol)

            if df is None or df.empty:
                logger.warning(f"No cash flow sheet for {symbol}")
                return None

            result = df.iloc[0].to_dict() if not df.empty else {}
            logger.info(f"Fetched cash flow sheet for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch cash flow sheet for {symbol}: {e}")
            return None

    def _clean_symbol(self, symbol: str) -> str:
        """清理股票代码"""
        symbol = symbol.strip()
        if "." in symbol:
            return symbol.split(".")[0]
        return symbol

    def _safe_float(self, row: pd.Series, key: str) -> Optional[float]:
        """安全地获取浮点值"""
        if key not in row:
            return None
        val = row[key]
        if pd.isna(val):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _parse_report_date(self, row: pd.Series) -> Optional[date]:
        """从行数据中解析报告日期"""
        date_keys = ["报告期", "日期", "截止日期", "REPORT_DATE"]

        for key in date_keys:
            if key in row:
                date_str = str(row[key])
                parsed = self._try_parse_date(date_str)
                if parsed:
                    return parsed

        return None

    def _try_parse_date(self, date_str: str) -> Optional[date]:
        """尝试解析日期字符串"""
        date_str = date_str.strip()

        for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y-%m", "%Y年%m月%d日"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date()
            except ValueError:
                continue

        # 尝试只解析年份
        if len(date_str) == 4 and date_str.isdigit():
            try:
                return date(int(date_str), 12, 31)
            except ValueError:
                pass

        return None

    def _infer_report_type(self, report_date: date) -> str:
        """推断报告类型"""
        if report_date.month == 12:
            return "annual"
        elif report_date.month in [3, 6, 9]:
            return "quarterly"
        else:
            return "quarterly"
