"""中国证券网数据适配器"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.crawlers.cnstock.cnstock import CnstockCrawler, CnstockConfig

logger = get_logger(__name__)


class CNStockAdapter(BaseDataAdapter):
    """中国证券网新闻适配器"""

    def __init__(self):
        super().__init__(source_type="news")

    def fetch(
        self,
        start_date: str,
        end_date: str,
        channel: str = "证券",
        output_dir: str = "./data/crawlers/cnstock",
        **kwargs
    ) -> list[DocumentEnvelope]:
        """爬取中国证券网新闻,返回 DocumentEnvelope 列表"""
        logger.info(
            f"Fetching CNStock news: start_date={start_date}, end_date={end_date}, channel={channel}, output_dir={output_dir}"
        )

        # 创建配置和爬虫实例
        config = CnstockConfig(
            start_date=start_date,
            end_date=end_date,
            channel=channel,
            output_path=output_dir,
            state_path=kwargs.get("state_path"),
            skip_existing=kwargs.get("skip_existing", True),
            verbose=kwargs.get("verbose", True),
            fetch_content=kwargs.get("fetch_content", False),
            max_pages=kwargs.get("max_pages", 5),
        )

        crawler = CnstockCrawler(config)
        result = crawler.execute()

        if not result.get("success"):
            logger.error(f"CNStock crawl failed: {result.get('message')}")
            return []

        # Process news_list - convert NewsItem to dict if needed
        news_list = result.get("news_list", [])
        envelopes = []
        for news_item in news_list:
            # NewsItem is a dataclass, convert to dict
            if hasattr(news_item, '__dataclass_fields__'):
                news_dict = {
                    'title': news_item.title,
                    'url': news_item.url,
                    'publish_time': news_item.publish_time,
                    'source': news_item.source,
                    'summary': news_item.summary,
                    'article_id': news_item.article_id,
                    'content_text': news_item.content_text,
                    'categories': news_item.categories,
                }
            elif isinstance(news_item, dict):
                news_dict = news_item
            else:
                logger.warning(f"Skipping unknown news item type: {type(news_item)}")
                continue
            envelope = self.parse(news_dict)
            envelopes.append(envelope)

        logger.info(f"Fetched {len(envelopes)} CNStock news")
        return envelopes

    def parse(self, source: Any, **kwargs) -> DocumentEnvelope:
        """解析单条新闻 (dict or file path)"""
        if isinstance(source, dict):
            # Parse from dict
            article_id = source.get("article_id", "") or source.get("url", "").split("/")[-1]
            title = source.get("title", "")
            content = source.get("content_text", "") or source.get("content", "") or source.get("summary", "")
            # Try multiple date field names
            published_at_str = source.get("publish_time", "") or source.get("date", "") or source.get("publish_date", "")
            published_at = None
            if published_at_str:
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        published_at = datetime.strptime(published_at_str[:19] if 'T' in published_at_str else published_at_str[:10] if len(published_at_str) == 10 else published_at_str, fmt)
                        break
                    except ValueError:
                        continue

            return DocumentEnvelope(
                doc_id=self._generate_idempotency_key(f"cnstock-{article_id}"),
                source_type="news",
                title=title,
                published_at=published_at,
                source_name=source.get("source", "中国证券网"),
                language="zh",
                metadata={
                    "article_id": article_id,
                    "url": source.get("url", ""),
                    "categories": source.get("categories", []),
                },
                raw_text=content,
                canonical_text=content,
            )
        elif isinstance(source, (str, Path)):
            # Parse from file path
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return self.parse(data[0], **kwargs)
            elif isinstance(data, dict) and "news_list" in data:
                return self.parse(data["news_list"][0], **kwargs)
            else:
                return self.parse(data, **kwargs)
        else:
            raise ValueError(f"Unsupported source type for CNStock adapter: {type(source)}")
