"""
统一数据源连接器基类 — BaseConnector → DocumentConnector / MarketDataConnector.

设计原则（改进.md + 改进2.md）：
- 统一接入接口和生命周期（discover → fetch → save_raw → parse → normalize → validate → persist）
- 不统一业务数据 schema（通过 IngestionRecord 外壳 + 分型 payload 实现）
- DocumentConnector 负责非结构化数据（公告、研报、新闻等）
- MarketDataConnector 负责结构化时间序列（行情、估值、成分股等）
- connector 止于数据获取和基础解析，LLM 提取归 KnowledgePipeline
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast

from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    IngestionResult,
    IngestionStats,
    IngestionStatus,
    RawObjectSummary,
    ValidationReport,
)
from core.observability import get_logger

logger = get_logger(__name__)


# =============================================================================
# 基础数据结构
# =============================================================================


@dataclass
class DiscoveryItem:
    """发现的可抓取对象 — discover() 的返回类型.

    Attributes:
        item_id: 对象唯一标识.
        item_type: 对象类型（如 "announcement", "trading_day", "index_member"）.
        params: 传给 fetch() 的参数.
        description: 可读描述.
    """

    item_id: str
    item_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass
class RawObject:
    """原始数据对象 — fetch() 的返回类型.

    Attributes:
        data: 原始数据内容（bytes / str）.
        content_type: MIME 类型或格式（如 "application/pdf", "text/html", "application/json"）.
        source_uri: 数据来源 URI.
        content_hash: SHA256 哈希.
        fetched_at: 抓取时间.
        metadata: 额外元信息（文件大小、编码等）.
    """

    data: bytes | str
    content_type: str
    source_uri: str
    content_hash: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """解析后的文档 — DocumentConnector.parse_document() 的返回类型.

    Attributes:
        title: 文档标题.
        text: 解析后的文本内容.
        pages: 页数.
        file_type: 文件格式.
        metadata: 从原始数据中提取的元信息.
    """

    title: str
    text: str
    pages: Optional[int] = None
    file_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTable:
    """解析后的表格数据 — MarketDataConnector.parse_table() 的返回类型.

    Attributes:
        columns: 列名列表.
        rows: 数据行列表（每行为 dict）.
        table_name: 表名/标识.
        metadata: 从原始数据中提取的元信息.
    """

    columns: List[str]
    rows: List[Dict[str, Any]]
    table_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# BaseConnector ABC
# =============================================================================


class BaseConnector(ABC):
    """数据源连接器抽象基类 — 统一生命周期.

    所有数据源连接器必须继承此类，实现统一的生命周期方法。
    子类分型（DocumentConnector / MarketDataConnector）提供特定于数据类型的额外方法。

    生命周期: discover → fetch → save_raw → parse → normalize → validate → persist

    Usage:
        connector = MyConnector(config)
        result = connector.run(dataset="stock_daily", start_date="2026-01-01")
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化连接器.

        Args:
            config: 连接器配置字典（可选）。从 config.yaml 或环境变量加载。
        """
        self.config = config or {}
        self._health: HealthStatus = HealthStatus.UNKNOWN

    # ------------------------------------------------------------------
    # 元信息（属性 — 由子类覆盖）
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def source(self) -> str:
        """数据源标识，如 "akshare", "cninfo", "cls"."""
        ...

    @property
    @abstractmethod
    def datasets(self) -> List[str]:
        """该连接器支持的数据集列表，如 ["stock_daily", "stock_master"]."""
        ...

    @property
    def asset_type(self) -> str:
        """默认数据资产类型（子类可覆盖）。"""
        return "other"

    # ------------------------------------------------------------------
    # 生命周期方法（子类必须实现）
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """检查数据源是否可用.

        Returns:
            HealthStatus: 健康状态（healthy / degraded / unavailable）.

        Implementation notes:
            - 应该实际尝试连接数据源（而不是只返回缓存的健康状态）
            - 失败时记录详细错误日志
            - 更新 self._health
        """
        ...

    @abstractmethod
    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的数据对象.

        Args:
            dataset: 数据集标识（如 "announcements", "stock_daily"）.
            **params: 发现参数（如 start_date, end_date, symbol）.

        Returns:
            List[DiscoveryItem]: 发现的待抓取对象列表。

        Implementation notes:
            - 对于公告源：返回当天或时间范围内的公告列表
            - 对于行情源：返回交易日列表（用于逐日抓取）
            - 对于指数源：返回指数成员列表进行更新
        """
        ...

    @abstractmethod
    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取单个原始数据对象.

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始数据对象（含内容、类型、来源、哈希）.

        Implementation notes:
            - 应在此层处理速率限制和重试
            - 计算并填充 content_hash（SHA256）
            - 记录 source_uri（用于溯源）
        """
        ...

    # ------------------------------------------------------------------
    # 内置方法（子类可覆盖）
    # ------------------------------------------------------------------

    def save_raw(self, raw: RawObject) -> str:
        """保存原始数据，返回存储 URI.

        默认实现：委托给 RawStorageService（services/raw_storage_service.py）。
        子类可覆盖以自定义存储行为。

        Args:
            raw: fetch() 返回的原始数据对象.

        Returns:
            str: 原始数据存储 URI（如 "data/raw/cninfo/2026/06/02/xxx.json"）.
        """
        from services.raw_storage_service import RawStorageService

        service = RawStorageService()
        file_info = service.save_raw_data(
            source_type=self.source,
            data=raw.data,
            metadata=raw.metadata,
        )
        return cast(str, file_info.file_path)

    def get_metadata(self, raw: RawObject) -> Dict[str, Any]:
        """从原始数据中提取通用元信息.

        默认实现：提取基本元信息（大小、类型、抓取时间）。
        子类可覆盖以添加源特定的元信息。

        Args:
            raw: 原始数据对象.

        Returns:
            Dict[str, Any]: 元信息字典（与 raw.metadata 合并）.
        """
        base_meta = {
            "content_type": raw.content_type,
            "source_uri": raw.source_uri,
            "content_hash": raw.content_hash,
            "fetched_at": raw.fetched_at.isoformat() if raw.fetched_at else None,
            "size_bytes": len(raw.data) if isinstance(raw.data, (bytes, str)) else None,
        }
        base_meta.update(raw.metadata)
        return base_meta

    def validate_existing(self, dataset: str, **params: Any) -> ValidationReport:
        """校验已有数据.

        默认实现：返回空报告。子类可覆盖以实现数据集特定的校验逻辑
        （如检查行情连续性、缺失日、异常值等）。

        Args:
            dataset: 数据集标识.
            **params: 校验参数.

        Returns:
            ValidationReport: 校验报告.
        """
        return ValidationReport(source=self.source, dataset=dataset)

    # ------------------------------------------------------------------
    # 模版方法：run() — CLI / MCP / 调度的统一入口
    # ------------------------------------------------------------------

    def run(
        self,
        dataset: str,
        **params: Any,
    ) -> IngestionResult:
        """执行完整摄入流程.

        模版方法：编排 discover → fetch → save_raw → parse → normalize → validate → persist.
        子类通常不需要覆盖此方法；而是实现各个生命周期方法。

        Args:
            dataset: 数据集标识.
            **params: 发现/抓取参数（如 start_date, end_date, symbol, max_items）.

        Returns:
            IngestionResult: 摄入结果（状态、统计、记录）.
        """
        import uuid
        from datetime import datetime

        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()
        stats = IngestionStats()
        records = []
        raw_objects = []

        logger.info(
            "connector_run_start",
            extra={
                "source": self.source,
                "dataset": dataset,
                "run_id": run_id,
                "params": params,
            },
        )

        try:
            # Step 1: 健康检查
            health = self.health_check()
            if health == HealthStatus.UNAVAILABLE:
                return IngestionResult(
                    source=self.source,
                    dataset=dataset,
                    status=IngestionStatus.FAILED,
                    run_id=run_id,
                    started_at=started_at,
                    finished_at=datetime.utcnow(),
                    error_message=f"Data source {self.source} is unavailable",
                )

            # Step 2: 发现
            items = self.discover(dataset, **params)
            stats.discovered = len(items)
            logger.debug(
                "connector_discover_done",
                extra={"source": self.source, "dataset": dataset, "count": len(items)},
            )

            # Step 3-6: 逐 item 处理
            for item in items:
                try:
                    raw = self._fetch_with_retry(dataset, item, **params)
                    stats.fetched += 1

                    raw.content_hash = self._compute_hash(raw.data)
                    raw_uri = self.save_raw(raw)

                    raw_objects.append(
                        RawObjectSummary(
                            source_uri=raw_uri,
                            content_hash=raw.content_hash,
                            content_type=raw.content_type,
                            fetched_at=raw.fetched_at,
                            size_bytes=(
                                len(raw.data) if isinstance(raw.data, (bytes, str)) else None
                            ),
                        )
                    )

                    item_records = self._process_item(dataset, item, raw, raw_uri)
                    records.extend(item_records)
                    processed_count = len(item_records) or 1
                    stats.parsed += processed_count
                    stats.validated += processed_count
                    stats.persisted += len(item_records)

                except Exception as item_error:
                    stats.failed += 1
                    stats.errors.append(
                        {
                            "item_id": item.item_id,
                            "error": str(item_error),
                        }
                    )
                    logger.warning(
                        "connector_item_failed",
                        extra={
                            "source": self.source,
                            "dataset": dataset,
                            "item_id": item.item_id,
                            "error": str(item_error),
                        },
                    )

            status = "completed"
            if stats.failed > 0 and stats.persisted > 0:
                status = "partial"
            elif stats.failed > 0 and stats.persisted == 0:
                status = "failed"

            logger.info(
                "connector_run_done",
                extra={
                    "source": self.source,
                    "dataset": dataset,
                    "run_id": run_id,
                    "status": status,
                    "discovered": stats.discovered,
                    "persisted": stats.persisted,
                    "failed": stats.failed,
                },
            )

        except Exception as e:
            logger.error(
                "connector_run_failed",
                extra={
                    "source": self.source,
                    "dataset": dataset,
                    "run_id": run_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return IngestionResult(
                source=self.source,
                dataset=dataset,
                status=IngestionStatus.FAILED,
                stats=stats,
                run_id=run_id,
                started_at=started_at,
                finished_at=datetime.utcnow(),
                error_message=str(e),
            )

        return IngestionResult(
            source=self.source,
            dataset=dataset,
            status=IngestionStatus(status),
            stats=stats,
            records=records,
            raw_objects=raw_objects,
            run_id=run_id,
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """带重试的数据获取（内部方法）."""
        retry_config = self.config.get("retry", {})
        max_retries = retry_config.get("max_retries", 3)
        base_delay = retry_config.get("base_delay", 1.0)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.fetch(dataset, item, **params)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import time

                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "connector_fetch_retry",
                        extra={
                            "source": self.source,
                            "dataset": dataset,
                            "item_id": item.item_id,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                        },
                    )
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]

    def _process_item(
        self,
        dataset: str,
        item: DiscoveryItem,
        raw: RawObject,
        raw_uri: str,
    ) -> List[IngestionRecord]:
        """处理单个 raw item 为 IngestionRecord（内部方法）.

        子类应覆盖此方法以实现特定于数据类型的处理逻辑。
        默认实现：创建最小 IngestionRecord。
        """
        return [
            IngestionRecord(
                source=self.source,
                dataset=dataset,
                asset_type=AssetType.OTHER,
                raw_uri=raw_uri,
                content_hash=raw.content_hash,
                schema_version="v1",
            )
        ]

    @staticmethod
    def _compute_hash(data: bytes | str) -> str:
        """计算 SHA256 内容哈希."""
        from hashlib import sha256

        content_bytes = data.encode("utf-8") if isinstance(data, str) else data
        return sha256(content_bytes).hexdigest()


# =============================================================================
# DocumentConnector — 非结构化文档连接器
# =============================================================================


class DocumentConnector(BaseConnector, ABC):
    """文档型数据源连接器 — 处理非结构化内容（公告、研报、新闻等）.

    职责边界：
    - ✅ 数据获取、基础解析、元信息提取、原始数据保存
    - ❌ LLM 分块、实体提取、嵌入 — 属于 KnowledgePipeline
    - connector 产出 IngestionRecord → IngestionQueue → KnowledgeWorker → KnowledgePipeline

    子类需实现: health_check, discover, fetch, parse_document, normalize_metadata, persist
    """

    @property
    def asset_type(self) -> str:
        return "document"

    @abstractmethod
    def parse_document(self, raw: RawObject) -> ParsedDocument:
        """解析原始数据为结构化文档.

        Args:
            raw: fetch() 返回的原始数据对象.

        Returns:
            ParsedDocument: 解析后的文档（标题、正文、页数、格式）.

        Implementation notes:
            - PDF 用 pdfplumber / MarkItDown 提取文本
            - HTML 用 BeautifulSoup 提取正文
            - JSON API 响应提取关键字段
        """
        ...

    @abstractmethod
    def normalize_metadata(
        self, dataset: str, parsed: ParsedDocument, raw_uri: str, content_hash: str
    ) -> IngestionRecord:
        """将解析后的文档转为统一的 IngestionRecord.

        Args:
            dataset: 数据集标识.
            parsed: parse_document() 的输出.
            raw_uri: save_raw() 返回的原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            IngestionRecord: 统一摄入记录（含 DocumentPayload）.
        """
        ...

    def persist(self, records: List[IngestionRecord]) -> int:
        """持久化摄入记录 — 入队到 IngestionQueue.

        将 IngestionRecord 转换为 EnqueueRequest 并入队到 IngestionQueue，
        由 KnowledgeWorker 消费后进入 KnowledgePipeline 进行 LLM 提取。

        子类通常不需要覆盖此方法；如有特殊的入队逻辑，
        可覆盖 _enqueue_record() 钩子。

        Args:
            records: 要持久化的摄入记录列表.

        Returns:
            int: 成功入队的数量.
        """
        if not records:
            return 0

        try:
            from data_layer.repositories.base import db_session
            from data_layer.repositories.ingestion_repository import IngestionQueueRepository
            from services.ingestion_queue_service import IngestionQueueService

            enqueued = 0

            with db_session() as db:
                repo = IngestionQueueRepository(db=db)
                queue_service = IngestionQueueService(repository=repo)

                for record in records:
                    try:
                        from core.contracts.ingestion import EnqueueRequest

                        payload = record.payload or {}
                        title = payload.get("title", "")
                        content = payload.get("content", "") or payload.get("text", "")

                        request = EnqueueRequest(
                            source_type=record.source,
                            source_id=record.entity_id or record.content_hash,
                            raw_content=content,
                            title=title,
                            url=payload.get("url"),
                            priority=0,
                            published_at=(
                                record.published_at.isoformat() if record.published_at else None
                            ),
                        )
                        result = queue_service.enqueue(request)
                        if not result.get("was_duplicate", False):
                            enqueued += 1
                    except Exception as item_error:
                        logger.warning(
                            f"{self.source}_persist_item_failed",
                            extra={
                                "source": record.source,
                                "entity_id": record.entity_id,
                                "error": str(item_error),
                            },
                        )

            logger.info(
                f"{self.source}_persist_done",
                extra={"total": len(records), "enqueued": enqueued},
            )
            return enqueued

        except Exception as e:
            logger.error(
                f"{self.source}_persist_failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # 覆盖模版方法
    # ------------------------------------------------------------------

    def _process_item(
        self,
        dataset: str,
        item: DiscoveryItem,
        raw: RawObject,
        raw_uri: str,
    ) -> List[IngestionRecord]:
        """DocumentConnector 的默认处理逻辑."""
        envelope_records = self._process_envelope_json(dataset, raw, raw_uri)
        if envelope_records is not None:
            self.persist(envelope_records)
            return envelope_records

        parsed = self.parse_document(raw)
        record = self.normalize_metadata(
            dataset=dataset,
            parsed=parsed,
            raw_uri=raw_uri,
            content_hash=raw.content_hash or "",
        )
        self.persist([record])
        return [record]

    def _process_envelope_json(
        self,
        dataset: str,
        raw: RawObject,
        raw_uri: str,
    ) -> Optional[List[IngestionRecord]]:
        """Convert a JSON list of DocumentEnvelope-like dicts into per-document records."""
        if raw.content_type != "application/json":
            return None

        try:
            import json
            from datetime import datetime

            data = raw.data.decode("utf-8") if isinstance(raw.data, bytes) else raw.data
            items = json.loads(data)
        except Exception:
            return None

        if not isinstance(items, list):
            return None

        records: List[IngestionRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            content = item.get("canonical_text") or item.get("raw_text") or ""
            title = item.get("title") or ""
            metadata = item.get("metadata") or {}
            doc_id = item.get("doc_id") or metadata.get("source_doc_id")
            if not doc_id:
                doc_id = self._compute_hash(f"{title}\n{content}")

            published_at = item.get("published_at")
            if isinstance(published_at, str) and published_at:
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except ValueError:
                    published_at = None
            elif not isinstance(published_at, datetime):
                published_at = None

            content_hash = self._compute_hash(content or title or doc_id)
            payload = {
                "title": title,
                "content": content,
                "summary": item.get("summary"),
                "url": metadata.get("url") or item.get("url"),
                "source_name": item.get("source_name") or self.source,
                "tags": [self.source, dataset],
                "metadata": metadata,
                "raw_uri": raw_uri,
            }

            asset_type = (
                AssetType.DOCUMENT if dataset in {"announcements", "report"} else AssetType.NEWS
            )
            records.append(
                IngestionRecord(
                    source=self.source,
                    dataset=dataset,
                    asset_type=asset_type,
                    entity_type=EntityType.UNKNOWN,
                    entity_id=str(doc_id),
                    published_at=published_at,
                    raw_uri=f"{raw_uri}#{doc_id}",
                    content_hash=content_hash,
                    payload=payload,
                )
            )

        return records


# =============================================================================
# MarketDataConnector — 结构化市场数据连接器
# =============================================================================


class MarketDataConnector(BaseConnector, ABC):
    """市场数据连接器 — 处理结构化时间序列（行情、估值、成分股等）.

    子类需实现: health_check, discover, fetch, parse_table, normalize_bars.
    persist() 已有默认实现（模板方法），子类通过覆盖钩子方法自定义行为:
    - _daily_bar_datasets() → 返回日线数据集的 dataset 名称元组
    - _persist_extra_records() → 处理非日线数据（如 stock_master）
    """

    @property
    def asset_type(self) -> str:
        return "market"

    @abstractmethod
    def parse_table(self, raw: RawObject) -> ParsedTable:
        """解析原始数据为结构化表格.

        Args:
            raw: fetch() 返回的原始 API 响应.

        Returns:
            ParsedTable: 解析后的表格（列名 + 行数据）.

        Implementation notes:
            - JSON API → 直接映射列/行
            - CSV/Parquet → pandas 读取后转换
            - Excel → 特定 sheet 读取
        """
        ...

    @abstractmethod
    def normalize_bars(
        self, dataset: str, table: ParsedTable, raw_uri: str, content_hash: str
    ) -> List[IngestionRecord]:
        """将表格数据转为统一的 IngestionRecord 列表.

        每行数据生成一个 IngestionRecord（含 MarketBarPayload 或其他结构化 payload）。

        Args:
            dataset: 数据集标识.
            table: parse_table() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            List[IngestionRecord]: 统一摄入记录列表.
        """
        ...

    # ------------------------------------------------------------------
    # persist() 模板方法 + 钩子
    # ------------------------------------------------------------------

    def _daily_bar_datasets(self) -> tuple[str, ...]:
        """返回日线数据的 dataset 名称元组（子类必须覆盖）.

        用于 persist() 中识别哪些记录应走 upsert_daily_bars() 路径。
        默认返回空元组（所有记录走 _persist_extra_records）。

        Returns:
            tuple[str, ...]: dataset 名称元组.
        """
        return ()

    def _build_daily_bar_row(self, record: IngestionRecord) -> Dict[str, Any]:
        """从 IngestionRecord 构建 daily_bar 数据库行（子类可覆盖）.

        默认处理 OHLCV + amount + turnover 字段。

        Args:
            record: 摄入记录.

        Returns:
            Dict[str, Any]: 数据库行字典.
        """
        p = record.payload
        return {
            "symbol": record.entity_id,
            "trade_date": p.get("trade_date"),
            "open": self._to_decimal(p.get("open")),
            "high": self._to_decimal(p.get("high")),
            "low": self._to_decimal(p.get("low")),
            "close": self._to_decimal(p.get("close")),
            "volume": self._to_decimal(p.get("volume")),
            "amount": self._to_decimal(p.get("amount")),
            "turnover": self._to_decimal(p.get("turnover")),
            "source": self.source,
            "raw_payload": p,
        }

    def _persist_extra_records(
        self,
        records: List[IngestionRecord],
        repo: Any,
    ) -> int:
        """处理非日线数据的持久化（子类可覆盖）.

        默认实现：无额外处理，返回 0。
        子类（如 akshare）可覆盖此方法处理 stock_master 等额外数据集。

        Args:
            records: 所有摄入记录列表.
            repo: MarketDataRepository 实例.

        Returns:
            int: 额外持久化的数量.
        """
        return 0

    def persist(self, records: List[IngestionRecord]) -> int:
        """持久化摄入记录到数据库（模板方法）.

        按 _daily_bar_datasets() 识别的日线数据走 upsert_daily_bars()，
        其他数据走 _persist_extra_records() 钩子。

        Args:
            records: 要持久化的摄入记录列表.

        Returns:
            int: 成功持久化的数量.
        """
        if not records:
            return 0

        try:
            from data_layer.repositories.base import db_session
            from data_layer.repositories.market_data_repository import MarketDataRepository

            daily_datasets = self._daily_bar_datasets()
            daily_records = [r for r in records if r.dataset in daily_datasets]
            persisted = 0

            with db_session() as db:
                repo = MarketDataRepository(db)

                if daily_records:
                    rows = [self._build_daily_bar_row(rec) for rec in daily_records]
                    persisted += repo.upsert_daily_bars(rows)

                # 额外数据集处理（如 stock_master）
                persisted += self._persist_extra_records(records, repo)

            logger.info(
                f"{self.source}_persist_done",
                extra={
                    "dataset": records[0].dataset if records else "unknown",
                    "total": len(records),
                    "daily_bars": len(daily_records),
                    "persisted": persisted,
                },
            )
            return persisted

        except Exception as e:
            logger.error(
                f"{self.source}_persist_failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # 共享的静态辅助方法（由 wind / yahoo / akshare 的重复代码提取而来）
    # ------------------------------------------------------------------

    @staticmethod
    def _format_date(value: Any) -> str:
        """将日期值格式化为 YYYY-MM-DD 字符串.

        支持 date, datetime, pd.Timestamp, 字符串等类型。
        """
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            val = value.strftime("%Y-%m-%d")
            return str(val)
        return str(value)[:10]

    @staticmethod
    def _to_decimal(value: Any) -> Any:
        """安全转换为 Decimal 类型."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return value

    @staticmethod
    def _parse_date(value: Any) -> Optional[date_type]:
        """解析日期参数为 date 对象."""
        if value is None:
            return None
        if isinstance(value, date_type):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date_type.fromisoformat(value)
        return None

    def validate_time_series(self, records: List[IngestionRecord]) -> ValidationReport:
        """校验时间序列数据的完整性和正确性.

        默认实现：检查基本的非空和范围合理性。
        子类可覆盖以添加特定于数据集的校验（如 OHLC 逻辑关系、日期连续性等）。

        Args:
            records: 要校验的记录列表.

        Returns:
            ValidationReport: 校验报告.
        """
        issues = []
        for i, record in enumerate(records):
            payload = record.payload
            # OHLC 基本逻辑校验
            if all(k in payload for k in ("open", "high", "low", "close")):
                op_val = payload.get("open")
                hi_val = payload.get("high")
                lo_val = payload.get("low")
                cl_val = payload.get("close")
                if (
                    op_val is not None
                    and hi_val is not None
                    and lo_val is not None
                    and cl_val is not None
                ):
                    if hi_val < lo_val:  # type: ignore[operator]
                        issues.append(
                            {
                                "index": i,
                                "issue": "high < low",
                                "values": {
                                    "open": op_val,
                                    "high": hi_val,
                                    "low": lo_val,
                                    "close": cl_val,
                                },
                            }
                        )
                    if hi_val < max(op_val, cl_val) or lo_val > min(op_val, cl_val):  # type: ignore[operator]
                        issues.append(
                            {
                                "index": i,
                                "issue": "OHLC range mismatch",
                                "values": {
                                    "open": op_val,
                                    "high": hi_val,
                                    "low": lo_val,
                                    "close": cl_val,
                                },
                            }
                        )

        return ValidationReport(
            source=self.source,
            dataset="",
            total_checked=len(records),
            passed=len(records) - len(issues),
            failed=len(issues),
            issues=issues,
        )

    def _process_item(
        self,
        dataset: str,
        item: DiscoveryItem,
        raw: RawObject,
        raw_uri: str,
    ) -> List[IngestionRecord]:
        """MarketDataConnector 的默认处理逻辑."""
        table = self.parse_table(raw)
        records = self.normalize_bars(
            dataset=dataset,
            table=table,
            raw_uri=raw_uri,
            content_hash=raw.content_hash or "",
        )
        self.persist(records)
        return records
