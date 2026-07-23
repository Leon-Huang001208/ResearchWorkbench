"""
Yahoo Finance 数据适配器

提供全球市场数据，作为 AkShare/BaoStock 的补充数据源。
"""

import importlib
from datetime import datetime

from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.crawlers.yahoo import YahooAdapter as CrawlerYahooAdapter
from data_layer.crawlers.yahoo import YahooConfig

logger = get_logger(__name__)


class YahooAdapter(BaseDataAdapter):
    """
    Yahoo Finance 数据适配器

    提供美股、港股等全球市场数据，作为 AkShare/BaoStock 的补充。
    """

    def __init__(self):
        super().__init__(source_type="yahoo")
        self.config = YahooConfig()
        self.crawler_adapter = CrawlerYahooAdapter(self.config)
        self._is_available = self._check_availability()

    def _check_availability(self):
        """检查 Yahoo Finance 是否可用"""
        try:
            importlib.import_module("yfinance")

            return True
        except ImportError:
            logger.warning("yfinance not available")
            return False

    def is_available(self):
        return self._is_available

    async def fetch_stock_quotes(
        self,
        code,
        start_date=None,
        end_date=None,
        period="1y",
        interval="1d",
        auto_convert_symbol=True,
    ):
        """
        获取股票历史行情

        Args:
            code: 股票代码（可以是 AkShare/BaoStock 格式，会自动转换）
            start_date: 开始日期（YYYY-MM-DD 格式）
            end_date: 结束日期（YYYY-MM-DD 格式）
            period: 时间段（与 start/end 二选一）
            interval: K线间隔
            auto_convert_symbol: 是否自动转换 symbol 为 Yahoo 格式

        Returns:
            行情数据列表
        """
        if not self._is_available:
            return []

        try:
            from data_layer.crawlers.yahoo.utils import convert_symbol

            yahoo_code = code
            if auto_convert_symbol:
                yahoo_code = convert_symbol(code, source="akshare")

            start_dt = None
            end_dt = None
            if start_date:
                start_dt = (
                    datetime.strptime(start_date, "%Y-%m-%d").date()
                    if isinstance(start_date, str)
                    else start_date
                )
            if end_date:
                end_dt = (
                    datetime.strptime(end_date, "%Y-%m-%d").date()
                    if isinstance(end_date, str)
                    else end_date
                )

            market_data_list = self.crawler_adapter.market.get_historical_data(
                symbol=yahoo_code,
                start_date=start_dt,
                end_date=end_dt,
                period=period,
                interval=interval,
            )

            result = []
            for md in market_data_list:
                result.append(
                    {
                        "code": code,
                        "yahoo_code": yahoo_code,
                        "date": md.timestamp.strftime("%Y-%m-%d"),
                        "timestamp": md.timestamp.isoformat(),
                        "open": md.open,
                        "high": md.high,
                        "low": md.low,
                        "close": md.close,
                        "adj_close": md.adj_close,
                        "volume": md.volume,
                        "source": "yahoo",
                    }
                )

            logger.info(f"Yahoo fetched {len(result)} quotes for {code}")
            return result

        except Exception as e:
            logger.error(f"Yahoo fetch quotes failed for {code}: {e}")
            return []

    async def fetch_stock_info(
        self,
        code,
        auto_convert_symbol=True,
    ):
        """
        获取股票基本信息和基本面指标

        Args:
            code: 股票代码
            auto_convert_symbol: 是否自动转换 symbol 为 Yahoo 格式

        Returns:
            股票信息字典
        """
        if not self._is_available:
            return None

        try:
            from data_layer.crawlers.yahoo.utils import convert_symbol

            yahoo_code = code
            if auto_convert_symbol:
                yahoo_code = convert_symbol(code, source="akshare")

            stock_info = self.crawler_adapter.fundamental.get_stock_info(yahoo_code)

            result = stock_info.to_dict()
            result["original_code"] = code

            logger.info(f"Yahoo fetched stock info for {code}")
            return result

        except Exception as e:
            logger.error(f"Yahoo fetch stock info failed for {code}: {e}")
            return None

    async def fetch_financial_report(
        self,
        code,
        auto_convert_symbol=True,
    ):
        """
        获取最新财务报告数据

        Args:
            code: 股票代码
            auto_convert_symbol: 是否自动转换 symbol 为 Yahoo 格式

        Returns:
            财务数据字典
        """
        if not self._is_available:
            return None

        try:
            from data_layer.crawlers.yahoo.utils import convert_symbol

            yahoo_code = code
            if auto_convert_symbol:
                yahoo_code = convert_symbol(code, source="akshare")

            financials = self.crawler_adapter.fundamental.get_financials(yahoo_code)

            if financials:
                latest_date = sorted(financials.keys(), reverse=True)[0]
                latest_financial = financials[latest_date]

                result = latest_financial.to_dict()
                result["original_code"] = code

                logger.info(f"Yahoo fetched financial report for {code}")
                return result

            return None

        except Exception as e:
            logger.error(f"Yahoo fetch financial failed for {code}: {e}")
            return None

    async def fetch_news(
        self,
        code,
        limit=10,
        auto_convert_symbol=True,
    ):
        """
        获取个股相关新闻

        Args:
            code: 股票代码
            limit: 新闻数量上限
            auto_convert_symbol: 是否自动转换 symbol 为 Yahoo 格式

        Returns:
            新闻列表
        """
        if not self._is_available:
            return None

        try:
            from data_layer.crawlers.yahoo.utils import convert_symbol

            yahoo_code = code
            if auto_convert_symbol:
                yahoo_code = convert_symbol(code, source="akshare")

            news_data_list = self.crawler_adapter.news.get_news(yahoo_code, limit=limit)

            result = []
            for nd in news_data_list:
                result.append(
                    {
                        "title": nd.title,
                        "content": nd.content,
                        "publish_time": nd.publish_time.isoformat() if nd.publish_time else None,
                        "source": nd.source,
                        "url": nd.url,
                        "summary": nd.summary,
                        "symbols": nd.symbols,
                    }
                )

            logger.info(f"Yahoo fetched {len(result)} news for {code}")
            return result

        except Exception as e:
            logger.error(f"Yahoo fetch news failed for {code}: {e}")
            return []

    async def fetch_dividends(
        self,
        code,
        auto_convert_symbol=True,
    ):
        """
        获取分红历史

        Args:
            code: 股票代码
            auto_convert_symbol: 是否自动转换 symbol 为 Yahoo 格式

        Returns:
            分红历史列表
        """
        if not self._is_available:
            return None

        try:
            from data_layer.crawlers.yahoo.utils import convert_symbol

            yahoo_code = code
            if auto_convert_symbol:
                yahoo_code = convert_symbol(code, source="akshare")

            dividends = self.crawler_adapter.fundamental.get_dividends(yahoo_code)

            result = []
            if not dividends.empty:
                for idx, value in dividends.items():
                    result.append(
                        {
                            "date": idx.strftime("%Y-%m-%d"),
                            "dividend": float(value),
                            "code": code,
                            "yahoo_code": yahoo_code,
                        }
                    )

            logger.info(f"Yahoo fetched {len(result)} dividends for {code}")
            return result

        except Exception as e:
            logger.error(f"Yahoo fetch dividends failed for {code}: {e}")
            return []

    def health_check(self):
        """健康检查"""
        return self.crawler_adapter.health_check()

    def fetch(self, source, **kwargs):
        raise NotImplementedError(
            "YahooAdapter doesn't support document fetching, use for market data only"
        )

    def parse(self, source, **kwargs):
        raise NotImplementedError(
            "YahooAdapter doesn't support document parsing, use for market data only"
        )
