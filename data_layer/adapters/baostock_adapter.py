"""
BaoStock 数据适配器 - A 股数据源

提供 A 股市场数据，作为 AKShare 的补充或降级数据源。
"""
from datetime import datetime
from typing import List, Optional

from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

# Use the new crawler modules
from data_layer.crawlers.baostock import BaoStockAdapter as CrawlerBaoStockAdapter
from data_layer.crawlers.baostock import BaoStockConfig

logger = get_logger(__name__)


class BaoStockAdapter(BaseDataAdapter):
    """
    BaoStock 数据适配器
    提供 A 股市场数据，作为 AKShare 的补充或降级数据源。
    """

    def __init__(self):
        super().__init__(source_type="baostock")
        self.config = BaoStockConfig()
        self.crawler_adapter = CrawlerBaoStockAdapter(self.config)
        self._is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """检查 BaoStock 是否可用"""
        try:
            import baostock  # noqa: F401

            return True
        except ImportError:
            logger.warning("BaoStock not available")
            return False

    def is_available(self) -> bool:
        return self._is_available

    async def fetch_stock_quotes(self, code: str, start_date: str, end_date: str) -> List[dict]:
        """获取股票历史行情"""
        if not self._is_available:
            return []
        try:
            # Parse start and end dates
            start_dt = (
                datetime.strptime(start_date, "%Y-%m-%d").date()
                if isinstance(start_date, str)
                else start_date
            )
            end_dt = (
                datetime.strptime(end_date, "%Y-%m-%d").date()
                if isinstance(end_date, str)
                else end_date
            )

            market_data_list = self.crawler_adapter.market.get_historical_data(
                symbol=code, start_date=start_dt, end_date=end_dt
            )

            result = []
            for md in market_data_list:
                result.append(
                    {
                        "code": code,
                        "date": md.timestamp.strftime("%Y-%m-%d"),
                        "open": md.open,
                        "high": md.high,
                        "low": md.low,
                        "close": md.close,
                        "volume": md.volume,
                        "amount": md.amount,
                        "turnover": getattr(md, "turnover", None),
                    }
                )

            logger.info(f"BaoStock fetched {len(result)} quotes for {code}")
            return result
        except Exception as e:
            logger.error(f"BaoStock fetch quotes failed for {code}: {e}")
            return []

    async def fetch_financial_report(self, code: str) -> Optional[dict]:
        """获取最新财务报告数据（占位实现）"""
        if not self._is_available:
            return None
        logger.warning(f"BaoStock financial report not implemented for {code}")
        return None

    async def fetch_top_shareholders(self, code: str) -> Optional[List[dict]]:
        """获取前十大股东（占位实现）"""
        if not self._is_available:
            return None
        logger.warning(f"BaoStock top shareholders not implemented for {code}")
        return []

    async def fetch_news(self, code: str, limit: int = 10) -> Optional[List[dict]]:
        """获取个股相关新闻（占位实现）"""
        if not self._is_available:
            return None
        logger.warning(f"BaoStock news not implemented for {code}")
        return []

    def health_check(self):
        """健康检查"""
        return self.crawler_adapter.health_check()

    def fetch(self, source, **kwargs):
        raise NotImplementedError(
            "BaoStockAdapter doesn't support document fetching, use for market data only"
        )

    def parse(self, source, **kwargs):
        raise NotImplementedError(
            "BaoStockAdapter doesn't support document parsing, use for market data only"
        )
