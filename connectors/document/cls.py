"""CLS (财联社) DocumentConnector — 将现有 CLSAdapter 包装为 DocumentConnector.

Wrapper-first 策略：内部委托给 data_layer/adapters/cls_adapter.py 和
data_layer/crawlers/cls/cls.py，不立即重写内部逻辑。

支持的 datasets:
- telegram: 财联社电报快讯

Usage:
    connector = CLSDocumentConnector()
    result = connector.run(dataset="telegram", days=2, use_incremental=True)

    # 历史回填
    result = connector.run(dataset="telegram", start_date="2026-01-01",
                           end_date="2026-01-31", use_incremental=False, max_pages=50)
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


class CLSDocumentConnector(DocumentConnector):
    """财联社电报文档连接器.

    包装 CLSAdapter + CLSTelegramCrawler，提供统一的 DocumentConnector 接口。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 CLS 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - output_dir: 输出目录（默认 ./data/crawlers/cls）
                - state_path: 去重状态文件路径
                - use_incremental: 默认是否增量模式（默认 True）
                - max_pages: 最大翻页数（默认 50）
                - delay: 请求延迟秒数（默认 1.5）
                - retry: 重试配置字典（max_retries, base_delay）
        """
        super().__init__(config)
        self._output_dir = self.config.get("output_dir", "./data/crawlers/cls")
        self._state_path = self.config.get("state_path", "./data/crawlers/cls/.dedup_state.json")
        self._default_use_incremental = self.config.get("use_incremental", True)
        self._default_max_pages = self.config.get("max_pages", 50)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return str(self.config.get("source_type", "cls"))

    @property
    def datasets(self) -> List[str]:
        return ["telegram"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 CLS 数据源是否可用.

        尝试导入依赖并验证 CLSTelegramCrawler 可实例化。
        轻量级检查，不实际发起网络请求。
        """
        try:
            from data_layer.crawlers.cls.cls import HAS_DEPENDENCIES, CLSTelegramCrawler

            if not HAS_DEPENDENCIES:
                self._health = HealthStatus.UNAVAILABLE
                return HealthStatus.UNAVAILABLE

            # 尝试实例化 crawler（不会发起网络请求）
            _ = CLSTelegramCrawler
            self._health = HealthStatus.HEALTHY
            return HealthStatus.HEALTHY

        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("cls_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("cls_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的电报时间范围.

        Args:
            dataset: 数据集标识（telegram）.
            **params:
                - start_date: 开始日期 (YYYY-MM-DD)
                - end_date: 结束日期 (YYYY-MM-DD)
                - days: 天数（用于 end_date = today, start_date = today - days）

        Returns:
            List[DiscoveryItem]: 发现的待抓取日期范围.
        """
        if dataset != "telegram":
            logger.warning(
                "cls_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        days = params.get("days")

        # 构建日期范围描述
        if start_date and end_date:
            desc = f"telegrams: {start_date} → {end_date}"
            item_id = f"telegram_{start_date}_{end_date}"
        elif days:
            desc = f"telegrams: last {days} days"
            item_id = f"telegram_last_{days}d"
        elif start_date:
            desc = f"telegrams: since {start_date}"
            item_id = f"telegram_{start_date}_to_today"
        else:
            desc = "telegrams: incremental (latest)"
            item_id = "telegram_incremental"

        return [
            DiscoveryItem(
                item_id=item_id,
                item_type="telegram",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": days,
                },
                description=desc,
            )
        ]

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取财联社电报原始数据.

        委托给 CLSAdapter.fetch()，获取 DocumentEnvelope 列表后序列化为 JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始电报数据（JSON 序列化的 DocumentEnvelope 列表）.
        """
        if dataset != "telegram":
            raise ValueError(
                f"Unknown dataset '{dataset}' for CLS connector. " f"Supported: telegram"
            )

        from data_layer.adapters.cls_adapter import CLSAdapter

        adapter = CLSAdapter()

        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")
        days = item.params.get("days") or params.get("days", 2)
        use_incremental = params.get("use_incremental", self._default_use_incremental)
        max_pages = params.get("max_pages", self._default_max_pages)

        envelopes = adapter.fetch(
            start_date=start_date,
            end_date=end_date,
            days=days,
            output_dir=self._output_dir,
            use_incremental=use_incremental,
            max_pages=max_pages,
            state_path=self._state_path,
            skip_existing=params.get("skip_existing", True),
            verbose=params.get("verbose", False),
        )

        # 序列化 DocumentEnvelope 列表为 JSON
        serialized = json.dumps(
            [e.model_dump() for e in envelopes],
            ensure_ascii=False,
            default=str,
        )

        source_uri = f"cls://telegram/{start_date or 'incremental'}"
        if end_date:
            source_uri += f"_to_{end_date}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "item_type": "telegram",
                "item_count": len(envelopes),
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
                "use_incremental": use_incremental,
            },
        )

    def parse_document(self, raw: RawObject) -> ParsedDocument:
        """解析原始 JSON 为结构化文档.

        从 DocumentEnvelope JSON 列表中提取文本内容。
        如果原始数据包含多条电报，将其合并为一个文档。

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
                title=f"CLS Telegram {raw.metadata.get('start_date', 'incremental')}",
                text="",
                file_type="json",
                metadata=raw.metadata,
            )

        # 多条电报合并为一个文档（knowledge pipeline 会做分块）
        hasher = ""
        full_text_parts: List[str] = []
        titles: List[str] = []

        for env in envelopes:
            content = env.get("raw_text") or env.get("canonical_text", "")
            title = env.get("title", "")
            if title:
                titles.append(title)
            if content:
                full_text_parts.append(content)
                hasher += content[:100]

        full_text = "\n\n---\n\n".join(full_text_parts)
        doc_title = (
            f"财联社电报 {raw.metadata.get('start_date', '')} " f"({len(envelopes)} 条)"
        ).strip()

        return ParsedDocument(
            title=doc_title,
            text=full_text,
            pages=len(envelopes),
            file_type="json",
            metadata={
                **raw.metadata,
                "individual_titles": titles[:20],  # 最多保留 20 个标题
                "telegram_count": len(envelopes),
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
        telegram_count = parsed.metadata.get("telegram_count", 1)
        individual_titles = parsed.metadata.get("individual_titles", [])

        news_payload = NewsPayload(
            title=parsed.title,
            content=parsed.text,
            summary=(
                f"财联社电报 {telegram_count} 条，" f"标题: {'; '.join(individual_titles[:5])}"
                if individual_titles
                else None
            ),
            source_name="财联社",
            tags=["telegram", "快讯"],
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
