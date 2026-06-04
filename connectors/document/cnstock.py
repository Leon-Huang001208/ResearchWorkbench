"""CNStock (中国证券网) DocumentConnector — 将现有 CNStockAdapter 包装为 DocumentConnector.

Wrapper-first 策略：内部委托给 data_layer/adapters/cnstock_adapter.py 和
data_layer/crawlers/cnstock/，不立即重写内部逻辑。

支持的 datasets:
- news: 中国证券网新闻（支持按频道过滤，默认 "证券"）
- flash: 快讯频道新闻（内部委托为 channel="快讯" 的 news 抓取）

Usage:
    connector = CNStockDocumentConnector()
    result = connector.run(dataset="news", start_date="2026-01-01",
                           end_date="2026-01-31", channel="证券")
    result = connector.run(dataset="flash", start_date="2026-01-01",
                           end_date="2026-01-31")
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from core.connectors.base import DiscoveryItem, DocumentConnector, ParsedDocument, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    NewsPayload,
)
from core.observability import get_logger

logger = get_logger(__name__)

# cnstock 支持的频道
CNSTOCK_CHANNELS = {
    "快讯": "10004",
    "时政": "10005",
    "公司": "10006",
    "产经": "10007",
    "金融": "10011",
    "证券": "10232",
}


class CNStockDocumentConnector(DocumentConnector):
    """中国证券网新闻文档连接器.

    包装 CNStockAdapter + CnstockCrawler，提供统一的 DocumentConnector 接口。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 CNStock 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - output_dir: 输出目录（默认 ./data/crawlers/cnstock）
                - default_channel: 默认频道（默认 "证券"）
                - all_channels: 是否抓取所有频道（默认 False）
                - max_pages: 最大翻页数（默认 10）
                - fetch_content: 是否抓取正文内容（默认 False）
        """
        super().__init__(config)
        self._output_dir = self.config.get("output_dir", "./data/crawlers/cnstock")
        self._default_channel = self.config.get("default_channel", "证券")
        self._all_channels = self.config.get("all_channels", False)
        self._max_pages = self.config.get("max_pages", 10)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return str(self.config.get("source_type", "cnstock"))

    @property
    def datasets(self) -> List[str]:
        return ["news", "flash"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 CNStock 数据源是否可用.

        尝试导入 CnstockCrawler 和 requests 库。
        """
        try:
            from data_layer.crawlers.cnstock.cnstock import CnstockCrawler

            _ = CnstockCrawler
            self._health = HealthStatus.HEALTHY
            return HealthStatus.HEALTHY
        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("cnstock_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("cnstock_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的新闻时间范围.

        Args:
            dataset: 数据集标识（news）.
            **params:
                - start_date: 开始日期 (YYYY-MM-DD)
                - end_date: 结束日期 (YYYY-MM-DD)
                - channel: 频道名称（默认 "证券"）
                - all_channels: 是否抓取所有频道

        Returns:
            List[DiscoveryItem]: 发现的待抓取日期范围.
        """
        if dataset not in ("news", "flash"):
            logger.warning(
                "cnstock_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        # flash 数据集默认使用 "快讯" 频道
        if dataset == "flash":
            channel = "快讯"
        else:
            channel = params.get("channel", self._default_channel)
        all_channels = params.get("all_channels", self._all_channels)

        if all_channels:
            desc = f"cnstock {dataset}: all channels ({start_date} → {end_date})"
            item_id = f"cnstock_all_{start_date}_{end_date}"
        else:
            desc = f"cnstock {dataset}: {channel} ({start_date} → {end_date})"
            item_id = f"cnstock_{channel}_{start_date}_{end_date}"

        return [
            DiscoveryItem(
                item_id=item_id,
                item_type="news",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "channel": channel,
                    "all_channels": all_channels,
                },
                description=desc,
            )
        ]

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取中国证券网新闻原始数据.

        委托给 CNStockAdapter.fetch()，获取 DocumentEnvelope 列表后序列化为 JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始新闻数据（JSON 序列化的 DocumentEnvelope 列表）.
        """
        if dataset not in ("news", "flash"):
            raise ValueError(
                f"Unknown dataset '{dataset}' for CNStock connector. " f"Supported: news, flash"
            )

        from data_layer.adapters.cnstock_adapter import CNStockAdapter

        adapter = CNStockAdapter()

        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")
        # flash 数据集默认使用 "快讯" 频道
        if dataset == "flash":
            channel = "快讯"
        else:
            channel = item.params.get("channel") or params.get("channel", self._default_channel)
        all_channels = item.params.get("all_channels") or params.get("all_channels", False)
        max_pages = params.get("max_pages", self._max_pages)

        envelopes = adapter.fetch(
            start_date=start_date,
            end_date=end_date,
            channel=channel,
            output_dir=self._output_dir,
            all_channels=all_channels,
            max_pages=max_pages,
            skip_existing=params.get("skip_existing", True),
            verbose=params.get("verbose", False),
            fetch_content=params.get("fetch_content", False),
            stop_on_known=params.get("stop_on_known", True),
        )

        serialized = json.dumps(
            [e.model_dump() for e in envelopes],
            ensure_ascii=False,
            default=str,
        )

        source_uri = f"cnstock://news/{start_date}_to_{end_date}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "item_type": "news",
                "item_count": len(envelopes),
                "start_date": start_date,
                "end_date": end_date,
                "channel": channel,
                "all_channels": all_channels,
            },
        )

    def parse_document(self, raw: RawObject) -> ParsedDocument:
        """解析原始 JSON 为结构化文档.

        从 DocumentEnvelope JSON 列表中提取文本内容。

        Args:
            raw: fetch() 返回的原始 JSON 数据.

        Returns:
            ParsedDocument: 解析后的文档.
        """
        if isinstance(raw.data, bytes):
            text = raw.data.decode("utf-8")
        else:
            text = raw.data

        envelopes: List[Dict[str, Any]] = json.loads(text)

        if not envelopes:
            return ParsedDocument(
                title=f"中国证券网 {raw.metadata.get('start_date', 'unknown')}",
                text="",
                file_type="json",
                metadata=raw.metadata,
            )

        full_text_parts: List[str] = []
        titles: List[str] = []

        for env in envelopes:
            content = env.get("raw_text") or env.get("canonical_text", "")
            title = env.get("title", "")
            if title:
                titles.append(title)
            if content:
                full_text_parts.append(content)

        full_text = "\n\n---\n\n".join(full_text_parts)
        channel = raw.metadata.get("channel", "")
        channel_label = f" [{channel}]" if channel else ""

        doc_title = (
            f"中国证券网{channel_label} {raw.metadata.get('start_date', '')} " f"({len(envelopes)} 条)"
        ).strip()

        return ParsedDocument(
            title=doc_title,
            text=full_text,
            pages=len(envelopes),
            file_type="json",
            metadata={
                **raw.metadata,
                "individual_titles": titles[:20],
                "article_count": len(envelopes),
            },
        )

    def normalize_metadata(
        self,
        dataset: str,
        parsed: ParsedDocument,
        raw_uri: str,
        content_hash: str,
    ) -> IngestionRecord:
        """将解析后的文档转为 IngestionRecord.

        Args:
            dataset: 数据集标识.
            parsed: parse_document() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            IngestionRecord: 统一摄入记录（含 NewsPayload）.
        """
        article_count = parsed.metadata.get("article_count", 1)
        individual_titles = parsed.metadata.get("individual_titles", [])
        channel = parsed.metadata.get("channel", "证券")

        news_payload = NewsPayload(
            title=parsed.title,
            content=parsed.text,
            summary=(
                f"中国证券网{channel}频道 {article_count} 条新闻，" f"标题: {'; '.join(individual_titles[:5])}"
                if individual_titles
                else None
            ),
            source_name="中国证券网",
            tags=["cnstock", channel, "新闻"],
        )

        return IngestionRecord(
            source=self.source,
            dataset=dataset,
            asset_type=AssetType.NEWS,
            entity_type=EntityType.UNKNOWN,
            published_at=datetime.utcnow(),
            raw_uri=raw_uri,
            content_hash=content_hash,
            payload=news_payload.model_dump(),
        )

    # persist() 由 DocumentConnector 基类提供（IngestionQueue 入队）
