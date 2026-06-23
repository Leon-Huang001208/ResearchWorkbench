"""ZQ (知丘/券商中国) DocumentConnector — 将现有 ZQAdapter 包装为 DocumentConnector.

Wrapper-first 策略：内部委托给 data_layer/adapters/zq_adapter.py 和
data_layer/crawlers/zq/，不立即重写内部逻辑。

支持的 datasets:
- report: 知丘研报
- news: 知丘公众号文章
- meeting: 知丘会议纪要

Usage:
    connector = ZQDocumentConnector()
    result = connector.run(dataset="report", start_date="2026-01-01",
                           end_date="2026-01-31", search="新能源")
"""
from __future__ import annotations

import json
import re
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

# dataset → ZQAdapter doc_types 映射
DATASET_TO_DOC_TYPE = {
    "report": "REPORT",
    "news": "NEWS",
    "meeting": "ZQMEETING",
}

# doc_type → 中文标签
DOC_TYPE_LABEL = {
    "REPORT": "知丘研报",
    "NEWS": "知丘公众号",
    "ZQMEETING": "知丘纪要",
}

ZQ_REFERENCE_MARKER_RE = re.compile(r"##\d+\$\$")


def _clean_zq_text(text: str) -> str:
    """清理知丘正文里的引用标记，保留 Markdown 结构。"""
    cleaned = ZQ_REFERENCE_MARKER_RE.sub("", text or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _decode_json_object(text: str) -> Dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _meaningful_text_from_zq_envelope(env: Dict[str, Any]) -> str:
    """从 DocumentEnvelope 中提取真正正文，避免把元数据 JSON 当作内容。"""
    canonical_text = _clean_zq_text(str(env.get("canonical_text") or ""))
    if canonical_text:
        return canonical_text

    raw_text = str(env.get("raw_text") or "")
    raw_json = _decode_json_object(raw_text)
    if raw_json is not None:
        content_fields = (
            "coreViewpoint",
            "viewpoint",
            "core",
            "content",
            "summary",
            "abstract",
        )
        parts = [
            _clean_zq_text(str(raw_json.get(field) or ""))
            for field in content_fields
            if raw_json.get(field)
        ]
        return "\n\n".join(part for part in parts if part)

    return _clean_zq_text(raw_text)


class ZQDocumentConnector(DocumentConnector):
    """知丘文档连接器.

    包装 ZQAdapter，提供统一的 DocumentConnector 接口。
    支持研报 (report)、公众号 (news)、会议纪要 (meeting) 三种文档类型。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 ZQ 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - output_dir: 输出目录（默认 ./data/crawlers/zq）
                - max_pages: 最大翻页数（默认 20）
                - page_size: 每页数量（默认 100）
                - use_homepage_search: 是否使用首页搜索（默认 True）
        """
        super().__init__(config)
        self._output_dir = self.config.get("output_dir", "./data/crawlers/zq")
        self._max_pages = self.config.get("max_pages", 20)
        self._page_size = self.config.get("page_size", 100)
        self._enable_pdf = self.config.get("enable_pdf", False)
        self._enable_viewpoint = self.config.get("enable_viewpoint", False)
        self._enable_core = self.config.get("enable_core", False)
        self._enable_companies = self.config.get("enable_companies", False)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return str(self.config.get("source_type", "zq"))

    @property
    def datasets(self) -> List[str]:
        return ["report", "news", "meeting"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 ZQ 数据源是否可用.

        尝试导入 ZQ 爬虫模块和 requests 库。
        """
        try:
            from data_layer.crawlers.zq.zhiqiu.base_fetcher import BaseFetcher

            _ = BaseFetcher
            self._health = HealthStatus.HEALTHY
            return HealthStatus.HEALTHY
        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("zq_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("zq_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的文档时间范围.

        Args:
            dataset: 数据集标识（report / news / meeting）.
            **params:
                - start_date: 开始日期 (YYYY-MM-DD)
                - end_date: 结束日期 (YYYY-MM-DD)
                - search: 搜索关键词
                - days: 天数（用于 end_date = today, start_date = today - days）

        Returns:
            List[DiscoveryItem]: 发现的待抓取日期范围.
        """
        if dataset not in self.datasets:
            logger.warning(
                "zq_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        search = params.get("search", "")
        days = params.get("days")
        doc_type = DATASET_TO_DOC_TYPE[dataset]
        label = DOC_TYPE_LABEL.get(doc_type, dataset)

        if start_date and end_date:
            desc = f"{label}: {start_date} → {end_date}"
            item_id = f"zq_{dataset}_{start_date}_{end_date}"
        elif days:
            desc = f"{label}: last {days} days"
            item_id = f"zq_{dataset}_last_{days}d"
        elif start_date:
            desc = f"{label}: since {start_date}"
            item_id = f"zq_{dataset}_{start_date}_to_today"
        else:
            desc = f"{label}: incremental (latest)"
            item_id = f"zq_{dataset}_incremental"

        if search:
            desc += f" (search: {search})"
            item_id += f"_search_{search}"

        return [
            DiscoveryItem(
                item_id=item_id,
                item_type=dataset,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": days,
                    "search": search,
                    "doc_type": doc_type,
                },
                description=desc,
            )
        ]

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取知丘文档原始数据.

        委托给 ZQAdapter.fetch()，获取 DocumentEnvelope 列表后序列化为 JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始文档数据（JSON 序列化的 DocumentEnvelope 列表）.
        """
        if dataset not in self.datasets:
            raise ValueError(
                f"Unknown dataset '{dataset}' for ZQ connector. "
                f"Supported: {', '.join(self.datasets)}"
            )

        from data_layer.adapters.zq_adapter import ZQAdapter

        adapter = ZQAdapter()

        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")
        search = item.params.get("search") or params.get("search", "")
        doc_type = item.params.get("doc_type") or DATASET_TO_DOC_TYPE[dataset]
        max_pages = params.get("max_pages", self._max_pages)
        use_homepage_search = params.get(
            "use_homepage_search", self.config.get("use_homepage_search", True)
        )
        enable_pdf = params.get("enable_pdf", self._enable_pdf)
        enable_viewpoint = params.get("enable_viewpoint", self._enable_viewpoint)
        enable_core = params.get("enable_core", self._enable_core)
        enable_companies = params.get("enable_companies", self._enable_companies)

        envelopes = adapter.fetch(
            search=search,
            doc_types=doc_type,
            start_date=start_date,
            end_date=end_date,
            output_dir=self._output_dir,
            max_pages=max_pages,
            page_size=params.get("page_size", self._page_size),
            skip_existing=params.get("skip_existing", True),
            verbose=params.get("verbose", False),
            use_homepage_search=use_homepage_search,
            enable_pdf=enable_pdf,
            enable_viewpoint=enable_viewpoint,
            enable_core=enable_core,
            enable_companies=enable_companies,
        )

        serialized = json.dumps(
            [e.model_dump() for e in envelopes],
            ensure_ascii=False,
            default=str,
        )

        source_uri = f"zq://{dataset}/{start_date or 'incremental'}"
        if end_date:
            source_uri += f"_to_{end_date}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "item_type": dataset,
                "item_count": len(envelopes),
                "start_date": start_date,
                "end_date": end_date,
                "search": search,
                "doc_type": doc_type,
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

        doc_type = raw.metadata.get("item_type", "report")
        label = DOC_TYPE_LABEL.get(DATASET_TO_DOC_TYPE.get(doc_type, ""), "知丘")

        if not envelopes:
            return ParsedDocument(
                title=f"{label} {raw.metadata.get('start_date', 'unknown')}",
                text="",
                file_type="json",
                metadata=raw.metadata,
            )

        full_text_parts: List[str] = []
        titles: List[str] = []
        dropped_empty_documents = 0

        for env in envelopes:
            content = _meaningful_text_from_zq_envelope(env)
            title = env.get("title", "")
            if title:
                titles.append(title)
            if content:
                full_text_parts.append(content)
            else:
                dropped_empty_documents += 1

        full_text = "\n\n---\n\n".join(full_text_parts)

        doc_title = (
            f"{label} {raw.metadata.get('start_date', '')} " f"({len(envelopes)} 篇)"
        ).strip()

        return ParsedDocument(
            title=doc_title,
            text=full_text,
            pages=len(envelopes),
            file_type="json",
            metadata={
                **raw.metadata,
                "individual_titles": titles[:20],
                "document_count": len(envelopes),
                "dropped_empty_documents": dropped_empty_documents,
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
        doc_count = parsed.metadata.get("document_count", 1)
        individual_titles = parsed.metadata.get("individual_titles", [])
        doc_type = parsed.metadata.get("doc_type", "")
        label = DOC_TYPE_LABEL.get(doc_type, "知丘")

        tags = ["zq", dataset]
        if doc_type == "REPORT":
            tags.append("研报")
        elif doc_type == "NEWS":
            tags.append("公众号")
        elif doc_type == "ZQMEETING":
            tags.append("纪要")

        news_payload = NewsPayload(
            title=parsed.title,
            content=parsed.text,
            summary=(
                f"{label} {doc_count} 篇，" f"标题: {'; '.join(individual_titles[:5])}"
                if individual_titles
                else None
            ),
            source_name=label,
            tags=tags,
        )

        return IngestionRecord(
            source=self.source,
            dataset=dataset,
            asset_type=AssetType.NEWS if dataset in ("news", "meeting") else AssetType.DOCUMENT,
            entity_type=EntityType.UNKNOWN,
            published_at=datetime.utcnow(),
            raw_uri=raw_uri,
            content_hash=content_hash,
            payload=news_payload.model_dump(),
        )

    # persist() 由 DocumentConnector 基类提供（IngestionQueue 入队）
