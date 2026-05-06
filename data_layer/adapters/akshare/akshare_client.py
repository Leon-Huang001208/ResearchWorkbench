
"""AkShare API 封装层 - 直接调用 akshare Python 包"""
import os
import re
import time
import json
from typing import Any
import pandas as pd
import requests
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
        # 清除代理环境变量，避免 Shadowrocket fake-ip 劫持
        for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
            os.environ.pop(k, None)
        self._rate_limit_delay = 0.1  # 100ms 延迟防止触发频率限制

    def _convert_code(self, symbol: str, source: str = "sina") -> str:
        """将纯数字代码转换为新浪/腾讯格式（sh/sz前缀）"""
        if symbol.startswith("sh") or symbol.startswith("sz"):
            return symbol
        if symbol.startswith("6"):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"

    def _fetch_sina_kline(self, symbol: str, period: str = "daily", start_date: str = "", end_date: str = "", adjust: str = "") -> pd.DataFrame:
        """获取新浪日K线数据"""
        code = self._convert_code(symbol, "sina")
        # 新浪 scale 参数：240=日K
        scale = 240
        if period == "weekly":
            scale = 1200  # 新浪周K
        elif period == "monthly":
            scale = 7200  # 新浪月K
        # 新浪 datalen：获取最近N条数据
        datalen = 1023  # 新浪最大支持
        url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var=/CN_MarketDataService.getKLineData?symbol={code}&scale={scale}&ma=no&datalen={datalen}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        try:
            time.sleep(self._rate_limit_delay)
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            # 解析 JSONP：去掉 var=( 和 );
            text = resp.text.strip()
            json_str = text.removeprefix("var=(").removesuffix(");")
            data = json.loads(json_str)
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            # 重命名列以匹配 akshare 格式
            df = df.rename(columns={
                "day": "日期",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "close": "收盘",
                "volume": "成交量"
            })
            # 转换日期格式为 YYYYMMDD
            df["日期"] = df["日期"].str.replace("-", "")
            # 转换数值列为 float
            for col in ["开盘", "最高", "最低", "收盘", "成交量"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            # 按日期筛选
            if start_date:
                df = df[df["日期"] >= start_date]
            if end_date:
                df = df[df["日期"] <= end_date]
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch Sina kline for {symbol}: {e}")
            raise

    def _fetch_tencent_kline(self, symbol: str, period: str = "daily", start_date: str = "", end_date: str = "", adjust: str = "") -> pd.DataFrame:
        """获取腾讯日K线数据"""
        code = self._convert_code(symbol, "tencent")
        # 腾讯 period 参数：day/week/month
        tencent_period = "day"
        if period == "weekly":
            tencent_period = "week"
        elif period == "monthly":
            tencent_period = "month"
        # 腾讯复权：qfq=前复权
        fq_type = "qfq" if adjust == "qfq" else ("hfq" if adjust == "hfq" else "")
        # 腾讯日期格式：YYYY-MM-DD
        t_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}" if start_date else ""
        t_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}" if end_date else ""
        # 获取最近1000条
        param = f"{code},{tencent_period},{t_start},{t_end},1000,{fq_type}" if fq_type else f"{code},{tencent_period},{t_start},{t_end},1000"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
        try:
            time.sleep(self._rate_limit_delay)
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0 or not data.get("data"):
                return pd.DataFrame()
            kline_data = data["data"].get(code, {}).get(tencent_period, [])
            if not kline_data:
                return pd.DataFrame()
            # 解析腾讯K线数据：[日期,开盘,收盘,最高,最低,成交量,...]
            df = pd.DataFrame(kline_data, columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])
            # 转换日期格式为 YYYYMMDD
            df["日期"] = df["日期"].str.replace("-", "")
            # 转换数值列为 float
            for col in ["开盘", "最高", "最低", "收盘", "成交量"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch Tencent kline for {symbol}: {e}")
            raise

    def _fetch_realtime_quotes(self, codes: list[str]) -> dict:
        """获取实时行情（新浪+腾讯双源）"""
        # TODO: 实现实时行情获取
        return {}

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
        # 先尝试新浪接口
        try:
            logger.debug("Trying Sina kline API...")
            df = self._fetch_sina_kline(symbol, period, start_date, end_date, adjust)
            if not df.empty:
                logger.debug("Successfully fetched from Sina")
                return df
        except Exception as e:
            logger.warning(f"Sina API failed for {symbol}: {e}")
        # 新浪失败，尝试腾讯接口
        try:
            logger.debug("Trying Tencent kline API...")
            df = self._fetch_tencent_kline(symbol, period, start_date, end_date, adjust)
            if not df.empty:
                logger.debug("Successfully fetched from Tencent")
                return df
        except Exception as e:
            logger.warning(f"Tencent API failed for {symbol}: {e}")
        # 腾讯失败，兜底使用 AkShare 原接口
        try:
            logger.debug("Falling back to AkShare original API...")
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

