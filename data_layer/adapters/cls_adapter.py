"""财联社数据适配器"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.crawlers.cls.cls import CLSConfig, CLSTelegramCrawler

logger = get_logger(__name__)


class CLSAdapter(BaseDataAdapter):
    """财联社电报适配器"""

    def __init__(self):
        super().__init__(source_type="news")

    def fetch(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int = 2,
        output_dir: str = "./data/crawlers/cls",
        **kwargs,
    ) -> list[DocumentEnvelope]:
        """爬取财联社电报,返回 DocumentEnvelope 列表"""
        logger.info(
            f"Fetching CLS telegrams: start_date={start_date}, end_date={end_date}, days={days}, output_dir={output_dir}"
        )

        # 创建配置和爬虫实例
        config = CLSConfig(
            start_date=start_date,
            end_date=end_date,
            days=days,
            output_dir=output_dir,
            state_path=kwargs.get("state_path"),
            skip_existing=kwargs.get("skip_existing", True),
            verbose=kwargs.get("verbose", True),
            max_pages=kwargs.get("max_pages", 50),
        )

        crawler = CLSTelegramCrawler(config)
        result = crawler.execute()

        if not result.get("success"):
            logger.error(f"CLS crawl failed: {result.get('message')}")
            return []

        # 读取输出 JSON 文件
        output_file = result.get("output_file")
        if not output_file:
            logger.warning("No output file from CLS crawler")
            return []

        envelopes = []
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            telegrams = data.get("telegrams", [])
            for t in telegrams:
                envelope = self.parse(t)
                envelopes.append(envelope)
            logger.info(f"Fetched {len(envelopes)} CLS telegrams")
        except Exception as e:
            logger.error(f"Failed to read CLS output file {output_file}: {e}", exc_info=True)

        return envelopes

    def parse(self, source: Any, **kwargs) -> DocumentEnvelope:
        """解析单条电报 JSON (dict)"""
        if isinstance(source, dict):
            # Parse from dict
            t_id = source.get("id", "")
            content = source.get("content", "")
            date_str = (
                source.get("date") or source.get("publish_time", "") or source.get("created_at", "")
            )
            published_at = None
            if date_str:
                date_str = date_str.strip()
                # 尝试多种格式解析，确保精确到秒
                parse_formats = [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                ]
                for fmt in parse_formats:
                    try:
                        published_at = datetime.strptime(date_str, fmt)
                        # 只有日期的话补00:00:00
                        if fmt == "%Y-%m-%d":
                            published_at = published_at.replace(
                                hour=0, minute=0, second=0, microsecond=0
                            )
                        break
                    except ValueError:
                        continue
                # 还解析失败的话尝试fromisoformat
                if not published_at:
                    try:
                        published_at = datetime.fromisoformat(date_str)
                    except ValueError:
                        pass

            return DocumentEnvelope(
                doc_id=self._generate_idempotency_key(f"cls-{t_id}"),
                source_type="news",
                title=f"财联社电报 {t_id}",
                published_at=published_at,
                source_name="财联社",
                language="zh",
                metadata={"telegram_id": t_id},
                raw_text=content,
                canonical_text=content,
            )
        elif isinstance(source, (str, Path)):
            # Parse from file path
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            # If it's a list, take first item? Or expect single item?
            if isinstance(data, list):
                return self.parse(data[0], **kwargs)
            elif isinstance(data, dict) and "telegrams" in data:
                return self.parse(data["telegrams"][0], **kwargs)
            else:
                return self.parse(data, **kwargs)
        else:
            raise ValueError(f"Unsupported source type for CLS adapter: {type(source)}")
