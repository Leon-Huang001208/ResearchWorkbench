
"""AkShare API 封装层 - 直接调用 akshare Python 包"""
from typing import Any
import time
import pandas as pd
from core.observability import get_logger
from data_layer.adapters.akshare.exceptions import (
    AkShareClientError,
    AkShareDataError,
    AkShareRateLimitError,
)

logger = get_logger(__name__)

try:
    import akshare as ak
except ImportError:
    logger.error("akshare package not installed")
    raise AkShareClientError("akshare package not installed, please install with pip install akshare")


class AkShareClient:
    """AkShare API 封装客户端"""

    def __init__(self):
        self._rate_limit_delay = 0.1  # 100ms 延迟防止触发频率限制

    def _with_retry(self, func, *args, max_retries=3, **kwargs):
        """带重试的函数调用"""
        retries = 0
        while retries < max_retries:
            try:
                time.sleep(self._rate_limit_delay)
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                retries += 1
                if "频率" in str(e) or "rate limit" in str(e).lower():
                    logger.warning(f"Hit AkShare rate limit, retrying after delay... (attempt {retries}/{max_retries})")
                    time.sleep(self._rate_limit_delay * 2 * retries)
                    if retries >= max_retries:
                        raise AkShareRateLimitError("AkShare rate limit exceeded after retries") from e
                else:
                    logger.error(f"AkShare client error: {e}, retrying... (attempt {retries}/{max_retries})")
                    if retries >= max_retries:
                        raise AkShareClientError(f"AkShare client failed after retries: {e}") from e

    def get_stock_hist(self, symbol: str, period: str = "daily", start_date: str = "", end_date: str = "", adjust: str = "") -> pd.DataFrame:
        """
        获取股票历史行情数据
        :param symbol: 股票代码
        :param period: 周期：daily/weekly/monthly
        :param start_date: 开始日期，格式：YYYYMMDD
        :param end_date: 结束日期，格式：YYYYMMDD
        :param adjust: 复权类型：qfq/hfq/""
        :return: DataFrame
        """
        logger.debug(f"Fetching stock hist for {symbol}, period={period}, start={start_date}, end={end_date}")
        try:
            df = self._with_retry(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            return df
        except Exception as e:
            logger.error(f"Failed to get stock hist for {symbol}: {e}")
            raise AkShareDataError(f"Failed to get stock hist: {symbol}") from e

    def get_financial_report(self, symbol: str) -> pd.DataFrame:
        """获取财务报表数据"""
        logger.debug(f"Fetching financial report for {symbol}")
        try:
            df = self._with_retry(ak.stock_financial_report_sina, symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to get financial report for {symbol}: {e}")
            raise AkShareDataError(f"Failed to get financial report: {symbol}") from e

    def get_stock_individual_fund_flow(self, symbol: str) -> pd.DataFrame:
        """获取个股资金流向数据"""
        logger.debug(f"Fetching individual fund flow for {symbol}")
        try:
            df = self._with_retry(ak.stock_individual_fund_flow, symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to get individual fund flow for {symbol}: {e}")
            raise AkShareDataError(f"Failed to get individual fund flow: {symbol}") from e

    def get_stock_a_indicator_lg(self, symbol: str) -> pd.DataFrame:
        """获取股票估值指标"""
        logger.debug(f"Fetching valuation indicators for {symbol}")
        try:
            df = self._with_retry(ak.stock_a_indicator_lg, symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to get valuation indicators for {symbol}: {e}")
            raise AkShareDataError(f"Failed to get valuation indicators: {symbol}") from e

    def get_macro_china_gdp(self) -> pd.DataFrame:
        """获取中国GDP数据"""
        logger.debug("Fetching China GDP data")
        try:
            df = self._with_retry(ak.macro_china_gdp)
            return df
        except Exception as e:
            logger.error(f"Failed to get China GDP data: {e}")
            raise AkShareDataError("Failed to get China GDP data") from e

    def get_macro_china_cpi(self) -> pd.DataFrame:
        """获取中国CPI数据"""
        logger.debug("Fetching China CPI data")
        try:
            df = self._with_retry(ak.macro_china_cpi)
            return df
        except Exception as e:
            logger.error(f"Failed to get China CPI data: {e}")
            raise AkShareDataError("Failed to get China CPI data") from e

    def get_stock_hsgt_north_net_flow_in_em(self) -> pd.DataFrame:
        """获取北向资金净流入"""
        logger.debug("Fetching northbound net flow in")
        try:
            df = self._with_retry(ak.stock_hsgt_north_net_flow_in_em)
            return df
        except Exception as e:
            logger.error(f"Failed to get northbound net flow: {e}")
            raise AkShareDataError("Failed to get northbound net flow") from e

    def get_stock_zt_pool_em(self, date: str = "") -> pd.DataFrame:
        """获取涨停池数据"""
        logger.debug(f"Fetching zt pool for date {date}")
        try:
            if date:
                df = self._with_retry(ak.stock_zt_pool_em, date=date)
            else:
                df = self._with_retry(ak.stock_zt_pool_em)
            return df
        except Exception as e:
            logger.error(f"Failed to get zt pool: {e}")
            raise AkShareDataError("Failed to get zt pool data") from e

