"""
AkShare 新闻数据获取器
"""

from datetime import UTC, datetime
from typing import List, Optional

import pandas as pd

from core.observability import get_logger

from .base import BaseAkShareFetcher, NewsData
from .config import AkShareConfig
from .utils import clean_symbol, parse_datetime

logger = get_logger("akshare_news")


class AkShareNewsFetcher(BaseAkShareFetcher):
    """AkShare 新闻数据获取器"""

    def __init__(self, config: Optional[AkShareConfig] = None):
        super().__init__(config)

    def fetch_sina_news(
        self, limit: Optional[int] = None, keywords: Optional[List[str]] = None
    ) -> List[NewsData]:
        """
        获取新浪财经新闻

        Args:
            limit: 返回数量限制
            keywords: 关键词过滤

        Returns:
            新闻数据列表
        """
        self._initialize()
        limit = limit or self.config.news_limit
        logger.debug(f"Fetching sina news, limit={limit}")

        try:
            # 获取新浪财经滚动新闻
            df = self.ak.news_rolls_sina()

            if df is None or df.empty:
                logger.warning("No sina news returned")
                return []

            result: List[NewsData] = []

            for _, row in df.iterrows():
                if limit and len(result) >= limit:
                    break

                try:
                    title = str(row.get("标题", "") or row.get("title", ""))
                    content = str(row.get("内容", "") or row.get("content", ""))
                    url = str(row.get("链接", "") or row.get("url", ""))

                    # 关键词过滤
                    if keywords and not any(
                        k in title or k in content for k in keywords
                    ):
                        continue

                    publish_time = self._parse_time(row)

                    news_data = NewsData(
                        title=title,
                        content=content or title,
                        publish_time=publish_time,
                        source="sina",
                        url=url,
                        extra=row.to_dict(),
                    )
                    result.append(news_data)
                except Exception as e:
                    logger.debug(f"Error processing news row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} sina news")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch sina news: {e}")
            return []

    def fetch_eastmoney_news(
        self, limit: Optional[int] = None, keywords: Optional[List[str]] = None
    ) -> List[NewsData]:
        """
        获取东方财富新闻

        Args:
            limit: 返回数量限制
            keywords: 关键词过滤

        Returns:
            新闻数据列表
        """
        self._initialize()
        limit = limit or self.config.news_limit
        logger.debug(f"Fetching eastmoney news, limit={limit}")

        try:
            # 尝试获取东方财富新闻
            try:
                df = self.ak.news_10_eastmoney_em()
            except Exception:
                df = None

            if df is None or df.empty:
                logger.warning("No eastmoney news returned")
                return []

            result: List[NewsData] = []

            for _, row in df.iterrows():
                if limit and len(result) >= limit:
                    break

                try:
                    title = str(row.get("标题", "") or row.get("title", ""))
                    content = str(row.get("内容", "") or row.get("content", ""))
                    url = str(row.get("链接", "") or row.get("url", ""))

                    # 关键词过滤
                    if keywords and not any(
                        k in title or k in content for k in keywords
                    ):
                        continue

                    publish_time = self._parse_time(row)

                    news_data = NewsData(
                        title=title,
                        content=content or title,
                        publish_time=publish_time,
                        source="eastmoney",
                        url=url,
                        extra=row.to_dict(),
                    )
                    result.append(news_data)
                except Exception as e:
                    logger.debug(f"Error processing news row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} eastmoney news")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch eastmoney news: {e}")
            return []

    def fetch_caixin_news(
        self, limit: Optional[int] = None, keywords: Optional[List[str]] = None
    ) -> List[NewsData]:
        """Fetch the current AKShare-supported Caixin main news feed.

        AKShare removed the legacy Sina rolling-news entry point in newer
        releases.  This fallback keeps the adapter useful without presenting
        a missing provider as an empty, successful market-news response.
        """
        self._initialize()
        limit = limit or self.config.news_limit
        logger.debug(f"Fetching caixin news, limit={limit}")

        try:
            fetch = getattr(self.ak, "stock_news_main_cx", None)
            if not callable(fetch):
                logger.warning("AKShare Caixin news entry point is unavailable")
                return []
            df = fetch()
            if df is None or df.empty:
                logger.warning("No Caixin news returned")
                return []

            result: List[NewsData] = []
            for _, row in df.iterrows():
                try:
                    tag = str(row.get("tag", "")).strip()
                    content = str(row.get("summary", "")).strip()
                    url = str(row.get("url", "")).strip()
                    title = tag or content
                    if not title or not content:
                        continue
                    if keywords and not any(
                        k in title or k in content for k in keywords
                    ):
                        continue
                    result.append(
                        NewsData(
                            title=title,
                            content=content,
                            publish_time=datetime.now(UTC),
                            source="caixin",
                            url=url,
                            extra=row.to_dict(),
                        )
                    )
                    if len(result) >= limit:
                        break
                except Exception as e:
                    logger.debug(f"Error processing Caixin news row: {e}")
            logger.info(f"Fetched {len(result)} Caixin news items")
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Caixin news: {e}")
            return []

    def fetch_all_news(
        self, limit: Optional[int] = None, keywords: Optional[List[str]] = None
    ) -> List[NewsData]:
        """
        获取所有来源的新闻

        Args:
            limit: 总数量限制
            keywords: 关键词过滤

        Returns:
            新闻数据列表
        """
        all_news: List[NewsData] = []
        limit = limit or self.config.news_limit

        # 按配置的来源顺序获取
        for source in self.config.news_sources:
            if len(all_news) >= limit:
                break

            source_limit = limit - len(all_news)

            if source == "sina":
                source_news = self.fetch_sina_news(limit=source_limit, keywords=keywords)
                all_news.extend(source_news)
            elif source == "eastmoney":
                source_news = self.fetch_eastmoney_news(limit=source_limit, keywords=keywords)
                all_news.extend(source_news)

        if len(all_news) < limit:
            all_news.extend(
                self.fetch_caixin_news(limit=limit - len(all_news), keywords=keywords)
            )

        # 去重（基于标题）
        seen_titles = set()
        unique_news: List[NewsData] = []

        for news_item in all_news:
            if news_item.title not in seen_titles:
                seen_titles.add(news_item.title)
                unique_news.append(news_item)

        logger.info(f"Fetched {len(unique_news)} unique news from all sources")
        return unique_news

    def fetch_stock_news(self, symbol: str, days: int = 30, limit: int = 50) -> List[NewsData]:
        """
        获取个股相关新闻

        Args:
            symbol: 股票代码
            days: 回溯天数
            limit: 数量限制

        Returns:
            新闻数据列表
        """
        # 先获取一般新闻，然后筛选相关的
        clean_symbol = self._clean_symbol(symbol)

        # 获取新闻，使用股票代码作为关键词
        keywords = [clean_symbol]

        all_news = self.fetch_all_news(limit=limit * 2, keywords=keywords)

        # 补充股票名称作为关键词
        stock_name = self._get_stock_name(symbol)
        if stock_name:
            more_news = self.fetch_all_news(limit=limit, keywords=[stock_name])
            all_news.extend(more_news)

        # 去重并标记关联标的
        seen = set()
        result: List[NewsData] = []

        for news in all_news[:limit]:
            if news.title not in seen:
                seen.add(news.title)
                news.symbols = [symbol]
                result.append(news)

        logger.info(f"Fetched {len(result)} news for {symbol}")
        return result

    def _parse_time(self, row: pd.Series) -> datetime:
        """从行数据中解析时间"""
        time_keys = ["时间", "发布时间", "date", "pub_time", "time"]

        for key in time_keys:
            if key in row:
                time_str = str(row[key])
                parsed = self._try_parse_time(time_str)
                if parsed:
                    return parsed

        # 默认返回当前时间
        return datetime.now()

    def _try_parse_time(self, time_str: str) -> Optional[datetime]:
        """尝试解析时间字符串"""
        return parse_datetime(time_str)

    def _clean_symbol(self, symbol: str) -> str:
        """清理股票代码"""
        return clean_symbol(symbol)

    def _get_stock_name(self, symbol: str) -> Optional[str]:
        """获取股票名称（通过行情接口）"""
        try:
            from .market import AkShareMarketFetcher

            market_fetcher = AkShareMarketFetcher(self.config)
            stocks = market_fetcher.get_stock_list(limit=5000)

            clean_symbol = self._clean_symbol(symbol)
            for stock in stocks:
                if self._clean_symbol(stock.symbol) == clean_symbol:
                    return stock.name
        except Exception as e:
            logger.debug(f"Could not get stock name for {symbol}: {e}")

        return None
