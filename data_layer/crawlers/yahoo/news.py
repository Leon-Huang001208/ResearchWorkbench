
"""
Yahoo Finance 新闻数据获取器

注意：Yahoo 的新闻质量一般，适合作为辅助信息源。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from .base import BaseYahooFetcher, YahooConfig

logger = get_logger("yahoo_news")


@dataclass
class YahooNewsData:
    """Yahoo 新闻数据结构"""

    title: str
    content: str = ""
    publish_time: Optional[datetime] = None
    source: str = "yahoo"
    url: Optional[str] = None
    summary: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "source": self.source,
            "url": self.url,
            "summary": self.summary,
            "symbols": self.symbols,
            "topics": self.topics,
            "extra": self.extra,
        }


class YahooNewsFetcher(BaseYahooFetcher):
    """Yahoo 新闻数据获取器"""

    def __init__(self, config: Optional[YahooConfig] = None):
        super(YahooNewsFetcher, self).__init__(config)

    def get_news(self, symbol: str, limit: int = 10) -> List[YahooNewsData]:
        """
        获取个股相关新闻

        Args:
            symbol: Yahoo 格式的代码
            limit: 获取新闻数量上限

        Returns:
            YahooNewsData 列表
        """
        self._smart_delay(is_heavy_request=False)

        try:
            ticker = self.yf.Ticker(symbol)
            news = ticker.news

            self._record_success()

            if not news:
                logger.warning("No news found for %s", symbol)
                return []

            news = news[:limit]
            result = []

            for item in news:
                publish_time = None
                if "providerPublishTime" in item:
                    try:
                        publish_time = datetime.fromtimestamp(item["providerPublishTime"])
                    except (ValueError, TypeError):
                        pass

                related_symbols = []
                if "relatedTickers" in item:
                    related_symbols = item["relatedTickers"]

                summary = None
                if "summary" in item:
                    summary = item["summary"]
                elif "content" in item and isinstance(item["content"], str):
                    summary = item["content"][:200] + "..."

                news_data = YahooNewsData(
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    publish_time=publish_time,
                    url=item.get("link", item.get("url")),
                    summary=summary,
                    symbols=related_symbols,
                    extra=item,
                )
                result.append(news_data)

            logger.info("Fetched %d news items for %s", len(result), symbol)
            return result

        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch news for %s: %s", symbol, e)
            return []

    def get_market_news(self, limit: int = 20) -> List[YahooNewsData]:
        """
        获取市场新闻（通过获取主要指数的新闻）

        Args:
            limit: 获取新闻数量上限

        Returns:
            YahooNewsData 列表
        """
        market_indices = ["^GSPC", "^DJI", "^IXIC"]
        all_news = []

        for index in market_indices:
            try:
                news = self.get_news(index, limit=limit // len(market_indices))
                all_news.extend(news)
            except Exception as e:
                logger.warning("Failed to fetch news for %s: %s", index, e)
                continue

        all_news.sort(
            key=lambda x: x.publish_time or datetime.min,
            reverse=True,
        )

        seen_urls = set()
        unique_news = []
        for item in all_news:
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_news.append(item)
            elif not item.url:
                unique_news.append(item)

        return unique_news[:limit]

