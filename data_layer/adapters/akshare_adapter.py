"""AKShare 开源数据适配器 - macOS 降级数据源"""

from datetime import datetime
from typing import List, Optional

import pandas as pd

from core.observability import get_logger
from data_layer.adapters.akshare.akshare_client import AkShareClient
from data_layer.adapters.base import BaseDataAdapter

# Use the new crawler modules
from data_layer.crawlers.akshare import AkShareAdapter as CrawlerAkShareAdapter
from data_layer.crawlers.akshare import AkShareConfig

logger = get_logger(__name__)


class AKShareAdapter(BaseDataAdapter):
    """
    AKShare 开源数据适配器
    为 macOS 提供免费公开数据源，在 iFinD 不可用时自动降级使用
    """

    def __init__(self):
        super().__init__(source_type="akshare")
        self.config = AkShareConfig()
        self.crawler_adapter = CrawlerAkShareAdapter(self.config)
        self._is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """检查 AKShare 是否可用"""
        try:
            import akshare  # noqa: F401

            return True
        except ImportError:
            logger.warning("AKShare not available")
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
                symbol=code, start_date=start_dt, end_date=end_dt, period="daily"
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
                        "turnover": md.turnover,
                    }
                )

            logger.info(f"AKShare fetched {len(result)} quotes for {code}")
            return result
        except Exception as e:
            logger.error(f"AKShare fetch quotes failed for {code}: {e}")
            return []

    async def fetch_financial_report(self, code: str) -> Optional[dict]:
        """获取最新财务报告数据"""
        if not self._is_available:
            return None
        try:
            financial_abstract = self.crawler_adapter.financial.get_financial_abstract(code)

            result = {
                "code": code,
                "eps": None,
                "roe": None,
                "net_profit": None,
                "revenue": None,
                "gross_margin": None,
                "debt_ratio": None,
                "current_ratio": None,
            }

            if financial_abstract:
                result["eps"] = financial_abstract.get("基本每股收益") or financial_abstract.get("每股收益")
                result["roe"] = financial_abstract.get("净资产收益率")
                result["net_profit"] = financial_abstract.get("净利润")
                result["revenue"] = financial_abstract.get("营业总收入")
                result["gross_margin"] = financial_abstract.get("销售毛利率")
                result["debt_ratio"] = financial_abstract.get("资产负债率")

            logger.info(f"AKShare fetched financial report for {code}")
            return result
        except Exception as e:
            logger.error(f"AKShare fetch financial failed for {code}: {e}")
            return None

    async def fetch_shareholders(self, code: str) -> Optional[List[dict]]:
        """获取股东信息"""
        return await self.fetch_top_shareholders(code)

    async def fetch_top_shareholders(self, code: str) -> Optional[List[dict]]:
        """获取前十大股东信息

        使用 AKShare stock_gdfx_top_10_em 接口获取真实前十大股东数据。
        失败时返回空列表让调用方降级。

        Returns:
            list[dict] — 每个元素包含 name, share_ratio, shares, holder_type, rank
        """
        if not self._is_available:
            return None
        try:
            client = AkShareClient()
            # get_stock_gdfx_top_10_em 接受裸代码（如 "600519"）并自动加 sh/sz 前缀
            bare_code = self._clean_symbol(code)
            df = client.get_stock_gdfx_top_10_em(bare_code)

            if df is None or df.empty:
                logger.info(f"AKShare top 10 shareholders empty for {code}")
                return []

            shareholders = []
            # AKShare 返回的典型列名：股东名称, 持股数量, 持股比例, 股东类型, 序号
            for _, row in df.iterrows():
                shareholders.append(
                    {
                        "name": str(row.get("股东名称", "")),
                        "share_ratio": (
                            float(row.get("持股比例", 0))
                            if row.get("持股比例") is not None and not pd.isna(row.get("持股比例"))
                            else 0.0
                        ),
                        "shares": (
                            float(row.get("持股数量", 0))
                            if row.get("持股数量") is not None and not pd.isna(row.get("持股数量"))
                            else 0.0
                        ),
                        "holder_type": str(row.get("股东类型", "")),
                        "rank": (
                            int(row.get("序号", 0))
                            if row.get("序号") is not None and not pd.isna(row.get("序号"))
                            else 0
                        ),
                    }
                )

            logger.info(f"AKShare fetched {len(shareholders)} top 10 shareholders for {code}")
            return shareholders
        except Exception as e:
            logger.error(f"AKShare fetch top shareholders failed for {code}: {e}")
            return []

    async def fetch_news(self, code: str, limit: int = 10) -> Optional[List[dict]]:
        """获取个股相关新闻"""
        if not self._is_available:
            return None
        try:
            news_data_list = self.crawler_adapter.news.fetch_stock_news(
                symbol=code, days=30, limit=limit
            )

            result = []
            for nd in news_data_list:
                result.append(
                    {
                        "title": nd.title,
                        "content": nd.content,
                        "publish_time": nd.publish_time,
                        "source": nd.source,
                        "url": nd.url,
                    }
                )

            logger.info(f"AKShare fetched {len(result)} news for {code}")
            return result
        except Exception as e:
            logger.error(f"AKShare fetch news failed for {code}: {e}")
            return []

    def _clean_symbol(self, symbol: str) -> str:
        """清理股票代码"""
        symbol = symbol.strip()
        if "." in symbol:
            return symbol.split(".")[0]
        return symbol

    # Required abstract method from DataAdapter (not used for market data)
    def fetch(self, source, **kwargs):
        raise NotImplementedError(
            "AKShareAdapter doesn't support document fetching, use for market data only"
        )

    # Required abstract method from DataAdapter (not used for market data)
    def parse(self, source, **kwargs):
        raise NotImplementedError(
            "AKShareAdapter doesn't support document parsing, use for market data only"
        )
