"""Cninfo (巨潮资讯网) DocumentConnector — 上市公司公告数据源.

巨潮资讯网是中国证监会指定的上市公司信息披露平台，提供沪深京三市
上市公司公告、年报、半年报、招股书等官方披露文件。

Wrapper-first 策略：内部委托给 data_layer/adapters/cninfo_adapter.py 和
data_layer/crawlers/cninfo/cninfo.py，不立即重写内部逻辑。

支持的 datasets:
- announcements: 上市公司公告（支持按日期范围、板块过滤）

Usage:
    connector = CninfoDocumentConnector()
    result = connector.run(dataset="announcements", start_date="2026-01-01",
                           end_date="2026-06-02", plate="szse")
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
from data_layer.crawlers.cninfo.cninfo import CNINFO_CATEGORIES, CNINFO_PLATES

logger = get_logger(__name__)


class CninfoDocumentConnector(DocumentConnector):
    """巨潮资讯网公告连接器.

    包装 CninfoAdapter + CninfoCrawler，提供统一的 DocumentConnector 接口。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 cninfo 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - output_dir: 输出目录（默认 ./data/crawlers/cninfo）
                - plate: 默认板块（szse / sse / bjse / all，默认 all）
                - page_size: 每页公告数（默认 30）
                - max_pages: 最大翻页数（默认 5）
                - delay: 请求延迟秒数（默认 0.5）
        """
        super().__init__(config)
        self._output_dir = self.config.get("output_dir", "./data/crawlers/cninfo")
        self._default_plate = self.config.get("plate", "")
        self._default_page_size = self.config.get("page_size", 30)
        self._default_max_pages = self.config.get("max_pages", 5)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "cninfo"

    @property
    def datasets(self) -> List[str]:
        return ["announcements"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 cninfo 数据源是否可用.

        尝试导入依赖并验证 CninfoCrawler 可实例化。
        轻量级检查，不实际发起网络请求。
        """
        try:
            from data_layer.crawlers.cninfo.cninfo import HAS_DEPENDENCIES, CninfoCrawler

            if not HAS_DEPENDENCIES:
                self._health = HealthStatus.UNAVAILABLE
                return HealthStatus.UNAVAILABLE

            _ = CninfoCrawler
            self._health = HealthStatus.HEALTHY
            return HealthStatus.HEALTHY

        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("cninfo_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("cninfo_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的公告时间范围.

        Args:
            dataset: 数据集标识（announcements）.
            **params:
                - start_date: 开始日期 (YYYY-MM-DD)
                - end_date: 结束日期 (YYYY-MM-DD)
                - plate: 板块过滤（szse / sse / bjse / all）
                - category: 公告类别过滤（默认 all）
                - stock: 股票代码过滤（可选）

        Returns:
            List[DiscoveryItem]: 发现的待抓取日期范围.
        """
        if dataset != "announcements":
            logger.warning(
                "cninfo_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        plate = params.get("plate", self._default_plate)
        category = params.get("category", "all")
        stock = params.get("stock", "")

        column = CNINFO_PLATES.get(plate, plate) if plate else ""
        category_code = CNINFO_CATEGORIES.get(category, "") if category != "all" else ""
        plate_label = plate or "all"
        cat_label = category if category != "all" else "all types"
        stock_suffix = f" [{stock}]" if stock else ""

        desc = (
            f"cninfo announcements: {plate_label} {cat_label}"
            f" ({start_date} → {end_date}){stock_suffix}"
        )
        item_id = f"cninfo_{plate}_{category}_{start_date}_{end_date}"

        return [
            DiscoveryItem(
                item_id=item_id,
                item_type="announcements",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "plate": plate,
                    "column": column,
                    "category": category_code,
                    "stock": stock,
                },
                description=desc,
            )
        ]

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取公告原始数据.

        委托给 CninfoAdapter.fetch()，获取 DocumentEnvelope 列表后序列化为 JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始公告数据（JSON 序列化的 DocumentEnvelope 列表）.
        """
        if dataset != "announcements":
            raise ValueError(
                f"Unknown dataset '{dataset}' for cninfo connector. " f"Supported: announcements"
            )

        from data_layer.adapters.cninfo_adapter import CninfoAdapter

        adapter = CninfoAdapter()

        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")
        plate = item.params.get("plate") or params.get("plate", self._default_plate)
        column = item.params.get("column", "")
        category = item.params.get("category", "")
        stock = item.params.get("stock", "")

        envelopes = adapter.fetch(
            start_date=start_date,
            end_date=end_date,
            plate=plate,
            column=column,
            category=category,
            stock=stock,
            output_dir=self._output_dir,
            max_pages=params.get("max_pages", self._default_max_pages),
            page_size=params.get("page_size", self._default_page_size),
            delay=params.get("delay", 0.5),
            timeout=params.get("timeout", 30),
            verbose=params.get("verbose", False),
        )

        # 序列化 DocumentEnvelope 列表为 JSON
        serialized = json.dumps(
            [e.model_dump() for e in envelopes],
            ensure_ascii=False,
            default=str,
        )

        source_uri = f"cninfo://announcements/{column or 'all'}/{start_date}_to_{end_date}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "item_type": "announcements",
                "item_count": len(envelopes),
                "start_date": start_date,
                "end_date": end_date,
                "plate": plate,
                "category": item.params.get("category", ""),
                "column": column,
            },
        )

    def parse_document(self, raw: RawObject) -> ParsedDocument:
        """解析原始 JSON 为结构化文档.

        从 DocumentEnvelope JSON 列表中提取文本内容。
        如果原始数据包含多条公告，将其合并为一个文档。

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
                title=f"巨潮资讯网公告 {raw.metadata.get('start_date', 'unknown')}",
                text="",
                file_type="json",
                metadata=raw.metadata,
            )

        full_text_parts: List[str] = []
        titles: List[str] = []

        for env in envelopes:
            title = env.get("title", "")
            content = env.get("raw_text") or env.get("canonical_text", "")
            if title:
                titles.append(title)
            if content:
                full_text_parts.append(content)

        full_text = "\n\n".join(full_text_parts)
        plate = raw.metadata.get("plate", "")
        plate_label = f" [{plate}]" if plate else ""

        doc_title = (
            f"巨潮资讯网{plate_label}公告 {raw.metadata.get('start_date', '')}"
            f" → {raw.metadata.get('end_date', '')} ({len(envelopes)} 条)"
        ).strip()

        return ParsedDocument(
            title=doc_title,
            text=full_text,
            pages=len(envelopes),
            file_type="json",
            metadata={
                **raw.metadata,
                "individual_titles": titles[:20],
                "announcement_count": len(envelopes),
            },
        )

    def normalize_metadata(
        self,
        dataset: str,
        parsed: ParsedDocument,
        raw_uri: str,
        content_hash: str,
    ) -> IngestionRecord:
        """将解析后的公告转为 IngestionRecord.

        Args:
            dataset: 数据集标识.
            parsed: parse_document() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            IngestionRecord: 统一摄入记录（含 NewsPayload）.
        """
        announcement_count = parsed.metadata.get("announcement_count", 0)
        individual_titles = parsed.metadata.get("individual_titles", [])
        plate = parsed.metadata.get("plate", "")

        news_payload = NewsPayload(
            title=parsed.title,
            content=parsed.text,
            summary=(
                f"{announcement_count} 条公告"
                + (f"（{plate}）" if plate else "")
                + (f"，标题: {'; '.join(individual_titles[:5])}" if individual_titles else "")
            ),
            source_name=f"巨潮资讯网{' - ' + plate if plate else ''}",
            tags=["cninfo", "filing", "公告"],
        )

        return IngestionRecord(
            source=self.source,
            dataset=dataset,
            asset_type=AssetType.DOCUMENT,
            entity_type=EntityType.STOCK,
            published_at=datetime.utcnow(),
            raw_uri=raw_uri,
            content_hash=content_hash,
            payload=news_payload.model_dump(),
        )

    # persist() 由 DocumentConnector 基类提供（IngestionQueue 入队）
