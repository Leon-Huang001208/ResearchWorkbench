
"""
Yahoo Finance 基本面数据获取器

提供股票信息、财务报表、分红拆股等数据。
"""
from datetime import date
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from .base import (
    BaseYahooFetcher,
    YahooConfig,
    YahooFinancialData,
    YahooStockInfo,
)

logger = get_logger("yahoo_fundamental")


class YahooFundamentalFetcher(BaseYahooFetcher):
    """Yahoo 基本面数据获取器"""

    def __init__(self, config: Optional[YahooConfig] = None):
        super(YahooFundamentalFetcher, self).__init__(config)

    def get_stock_info(self, symbol: str) -> YahooStockInfo:
        """
        获取股票详细信息（包含基本面指标）

        Args:
            symbol: Yahoo 格式的代码

        Returns:
            YahooStockInfo 对象
        """
        self._smart_delay(is_heavy_request=False)

        try:
            ticker = self.yf.Ticker(symbol)
            info = ticker.info

            self._record_success()

            return YahooStockInfo(
                symbol=symbol,
                name=info.get("longName", info.get("shortName", "")),
                currency=info.get("currency", ""),
                exchange=info.get("exchange", ""),
                country=info.get("country"),
                industry=info.get("industry"),
                sector=info.get("sector"),
                market_cap=self._safe_float(info.get("marketCap")),
                pe_ratio=self._safe_float(info.get("trailingPE")),
                pb_ratio=self._safe_float(info.get("priceToBook")),
                dividend_yield=self._safe_float(info.get("dividendYield")),
                beta=self._safe_float(info.get("beta")),
                fifty_two_week_high=self._safe_float(info.get("fiftyTwoWeekHigh")),
                fifty_two_week_low=self._safe_float(info.get("fiftyTwoWeekLow")),
                current_price=self._safe_float(info.get("currentPrice")),
                extra=info,
            )

        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch stock info for %s: %s", symbol, e)
            raise

    def get_financials(self, symbol: str) -> Dict[str, YahooFinancialData]:
        """
        获取财务报表（利润表、资产负债表、现金流量表）

        Args:
            symbol: Yahoo 格式的代码

        Returns:
            字典，key 为报告日期，value 为 YahooFinancialData 对象
        """
        self._smart_delay(is_heavy_request=True)

        try:
            ticker = self.yf.Ticker(symbol)

            income_stmt = ticker.income_stmt
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow

            self._record_success()

            result = {}

            if not income_stmt.empty:
                for report_date in income_stmt.columns:
                    date_key = report_date.date().isoformat()
                    if date_key not in result:
                        result[date_key] = YahooFinancialData(
                            symbol=symbol,
                            report_date=report_date.date(),
                            report_type="annual",
                        )

                    row_data = income_stmt[report_date]
                    result[date_key].total_revenue = self._safe_float(row_data.get("Total Revenue"))
                    result[date_key].net_income = self._safe_float(row_data.get("Net Income"))

                    revenue = result[date_key].total_revenue
                    net_inc = result[date_key].net_income
                    if revenue and revenue > 0:
                        gross_profit = self._safe_float(row_data.get("Gross Profit"))
                        if gross_profit is not None:
                            result[date_key].gross_margin = gross_profit / revenue
                        if net_inc is not None:
                            result[date_key].net_margin = net_inc / revenue

            if not balance_sheet.empty:
                for report_date in balance_sheet.columns:
                    date_key = report_date.date().isoformat()
                    if date_key not in result:
                        result[date_key] = YahooFinancialData(
                            symbol=symbol,
                            report_date=report_date.date(),
                            report_type="annual",
                        )

                    row_data = balance_sheet[report_date]
                    result[date_key].total_assets = self._safe_float(row_data.get("Total Assets"))
                    result[date_key].total_liabilities = self._safe_float(
                        row_data.get("Total Liabilities Net Minority Interest")
                    )
                    result[date_key].total_equity = self._safe_float(row_data.get("Stockholders Equity"))

                    equity = result[date_key].total_equity
                    net_inc = result[date_key].net_income
                    if equity and equity > 0 and net_inc is not None:
                        result[date_key].roe = net_inc / equity

            if not cash_flow.empty:
                for report_date in cash_flow.columns:
                    date_key = report_date.date().isoformat()
                    if date_key not in result:
                        result[date_key] = YahooFinancialData(
                            symbol=symbol,
                            report_date=report_date.date(),
                            report_type="annual",
                        )

                    row_data = cash_flow[report_date]
                    result[date_key].operating_cash_flow = self._safe_float(
                        row_data.get("Operating Cash Flow")
                    )
                    result[date_key].free_cash_flow = self._safe_float(row_data.get("Free Cash Flow"))

            logger.info("Fetched financials for %s: %d periods", symbol, len(result))
            return result

        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch financials for %s: %s", symbol, e)
            raise

    def get_income_statement(self, symbol: str, quarterly: bool = False) -> Any:
        self._smart_delay(is_heavy_request=True)
        try:
            ticker = self.yf.Ticker(symbol)
            df = ticker.quarterly_income_stmt if quarterly else ticker.income_stmt
            self._record_success()
            return df
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch income statement for %s: %s", symbol, e)
            raise

    def get_balance_sheet(self, symbol: str, quarterly: bool = False) -> Any:
        self._smart_delay(is_heavy_request=True)
        try:
            ticker = self.yf.Ticker(symbol)
            df = ticker.quarterly_balance_sheet if quarterly else ticker.balance_sheet
            self._record_success()
            return df
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch balance sheet for %s: %s", symbol, e)
            raise

    def get_cash_flow(self, symbol: str, quarterly: bool = False) -> Any:
        self._smart_delay(is_heavy_request=True)
        try:
            ticker = self.yf.Ticker(symbol)
            df = ticker.quarterly_cashflow if quarterly else ticker.cashflow
            self._record_success()
            return df
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch cash flow for %s: %s", symbol, e)
            raise

    def get_dividends(self, symbol: str) -> Any:
        self._smart_delay(is_heavy_request=False)
        try:
            ticker = self.yf.Ticker(symbol)
            dividends = ticker.dividends
            self._record_success()
            logger.info("Fetched %d dividend records for %s", len(dividends), symbol)
            return dividends
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch dividends for %s: %s", symbol, e)
            raise

    def get_splits(self, symbol: str) -> Any:
        self._smart_delay(is_heavy_request=False)
        try:
            ticker = self.yf.Ticker(symbol)
            splits = ticker.splits
            self._record_success()
            logger.info("Fetched %d split records for %s", len(splits), symbol)
            return splits
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch splits for %s: %s", symbol, e)
            raise

    def get_earnings_dates(self, symbol: str) -> Any:
        self._smart_delay(is_heavy_request=False)
        try:
            ticker = self.yf.Ticker(symbol)
            earnings_dates = ticker.earnings_dates
            self._record_success()
            return earnings_dates
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch earnings dates for %s: %s", symbol, e)
            raise

    def get_earnings(self, symbol: str) -> Any:
        self._smart_delay(is_heavy_request=False)
        try:
            ticker = self.yf.Ticker(symbol)
            earnings = ticker.earnings
            self._record_success()
            return earnings
        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch earnings for %s: %s", symbol, e)
            raise

