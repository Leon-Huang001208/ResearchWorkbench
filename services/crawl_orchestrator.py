"""
采集编排服务 - Issue #43: 多源采集、增量调度、补漏机制

整合：
- 原始数据存储
- 去重机制
- 增量抓取（SourceCursor）
- 抓取状态（CrawlRun）
- 补漏机制
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

# 触发数据源自动注册
import data_sources  # noqa: F401
from core.contracts import CrawlRunV1, DocumentEnvelope, DocumentV1, SourceCursorV1, SourceType
from core.observability import get_logger
from core.utils.id_gen import generate_id
from data_layer.repositories.base import get_db
from data_layer.repositories.documents_v1 import (
    CrawlRunV1Repository,
    DocumentV1Repository,
    SourceCursorV1Repository,
)
from services.deduplication_service import DeduplicationService
from services.raw_storage_service import RawStorageService

logger = get_logger(__name__)


class CrawlResult:
    """单次抓取结果"""

    def __init__(self):
        self.source_type: SourceType = SourceType.OTHER
        self.started_at: datetime = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.success_count: int = 0
        self.failure_count: int = 0
        self.skipped_count: int = 0
        self.saved_doc_ids: List[str] = []
        self.duplicate_doc_ids: List[str] = []
        self.error_log: Optional[str] = None
        self.raw_file_paths: List[str] = []


class CrawlOrchestrator:
    """采集编排器"""

    def __init__(self, db_session=None):
        self.db = db_session or next(get_db())
        self.deduplication = DeduplicationService()
        self.raw_storage = RawStorageService()
        self.doc_repo = DocumentV1Repository(self.db)
        self.crawl_run_repo = CrawlRunV1Repository(self.db)
        self.cursor_repo = SourceCursorV1Repository(self.db)

    def crawl_source(
        self,
        source_type: SourceType,
        source_name: Optional[str] = None,
        days: int = 1,
        max_docs: Optional[int] = None,
        max_pages: Optional[int] = None,
        skip_existing: bool = True,
        enable_backfill: bool = True,
        use_incremental: bool = True,
    ) -> CrawlResult:
        """
        抓取单个来源

        Args:
            source_type: 来源类型
            source_name: 来源名称
            days: 抓取最近几天的数据
            max_docs: 最大文档数
            skip_existing: 跳过已存在的文档
            enable_backfill: 启用补漏
            use_incremental: CLS 使用 updateTelegraphList 增量抓取（全部电报）

        Returns:
            CrawlResult
        """
        result = CrawlResult()
        result.source_type = source_type

        # 1. 创建/获取游标
        cursor = self.cursor_repo.get_or_create(source_type, source_name)

        # 2. 创建抓取记录
        crawl_run = CrawlRunV1(
            run_id=generate_id(),
            source_type=source_type,
            status="running",
            started_at=datetime.utcnow(),
            config={
                "days": days,
                "max_docs": max_docs,
                "max_pages": max_pages,
                "skip_existing": skip_existing,
                "enable_backfill": enable_backfill,
            },
        )
        crawl_run = self.crawl_run_repo.create(crawl_run)

        try:
            # 3. 计算抓取时间窗口
            start_time, end_time = self._calculate_time_window(
                cursor,
                days,
                enable_backfill,
            )

            logger.info(f"Crawling {source_type.value} from {start_time} to {end_time}")

            if self._source_uses_connector(source_type):
                self._run_connector_source(
                    result=result,
                    crawl_run=crawl_run,
                    cursor_id=cursor.cursor_id,
                    source_type=source_type,
                    start_time=start_time,
                    end_time=end_time,
                    days=days,
                    max_docs=max_docs,
                    max_pages=max_pages,
                    skip_existing=skip_existing,
                    use_incremental=use_incremental,
                )
                return result

            # 4. 同步爬虫级去重文件 — 修剪已被数据库删除的孤儿条目
            self._sync_dedup_state(source_type)

            # 5. 执行抓取（委托给适配器）
            docs, raw_files = self._fetch_from_adapter(
                source_type,
                start_time,
                end_time,
                max_docs,
                use_incremental=use_incremental,
                max_pages=max_pages,
            )

            result.raw_file_paths = [f.file_path for f in raw_files]

            # 6. 去重检查
            if skip_existing:
                docs, duplicates = self._deduplicate_docs(source_type, docs)
                result.skipped_count = len(duplicates)
                result.duplicate_doc_ids = [d.doc_id for d in duplicates]

            # 7. 保存文档
            for doc in docs:
                try:
                    saved_doc = self.doc_repo.create(doc)
                    result.saved_doc_ids.append(saved_doc.doc_id)
                    self.deduplication.mark_seen(saved_doc)
                    result.success_count += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Failed to save doc {doc.doc_id}: {e}")
                    result.failure_count += 1

            # 8. 更新游标（仅在有实际数据入库时更新，防止 0 结果回填补丁污染游标）
            if result.success_count > 0:
                last_doc = docs[-1] if docs else None
                last_source_doc_id = None
                if last_doc:
                    last_source_doc_id = last_doc.source_metadata.get(
                        "source_doc_id"
                    ) or last_doc.source_metadata.get("original_id")
                self.cursor_repo.record_success(cursor.cursor_id, last_source_doc_id)

            # 9. 更新抓取记录
            result.completed_at = datetime.utcnow()
            crawl_run.status = "completed"
            crawl_run.completed_at = result.completed_at
            crawl_run.success_count = result.success_count
            crawl_run.failure_count = result.failure_count
            crawl_run.skipped_count = result.skipped_count
            self.crawl_run_repo.update(crawl_run)

            logger.info(
                f"Crawl {source_type.value} completed: "
                f"{result.success_count} saved, "
                f"{result.skipped_count} skipped, "
                f"{result.failure_count} failed"
            )

        except Exception as e:
            logger.error(f"Crawl {source_type.value} failed: {e}", exc_info=True)
            result.completed_at = datetime.utcnow()
            result.error_log = str(e)
            # 记录失败
            self.cursor_repo.record_failure(cursor.cursor_id)
            crawl_run.status = "failed"
            crawl_run.completed_at = result.completed_at
            crawl_run.error_log = str(e)
            self.crawl_run_repo.update(crawl_run)

        return result

    def _source_uses_connector(self, source_type: SourceType) -> bool:
        """Return True when the registered source points at a BaseConnector."""
        from core.source_registry import get as get_spec

        spec = get_spec(source_type)
        if spec is None:
            return False
        return bool(spec.connector_dataset and spec.connector_class.startswith("connectors."))

    def _run_connector_source(
        self,
        result: CrawlResult,
        crawl_run: CrawlRunV1,
        cursor_id: str,
        source_type: SourceType,
        start_time: datetime,
        end_time: datetime,
        days: int,
        max_docs: Optional[int],
        max_pages: Optional[int],
        skip_existing: bool,
        use_incremental: bool,
    ) -> None:
        """Run a connector-backed source through the unified connector lifecycle."""
        from core.contracts.ingestion_record import IngestionStatus
        from core.source_registry import get as get_spec

        spec = get_spec(source_type)
        if spec is None or not spec.connector_dataset:
            raise ValueError(f"Connector source {source_type.value} is missing connector_dataset")

        module_path, class_name = spec.connector_class.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        connector_cls = getattr(module, class_name)
        connector = connector_cls(config=spec.adapter_kwargs)

        params: Dict[str, Any] = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "days": days,
            "skip_existing": skip_existing,
        }
        if max_pages is not None:
            params["max_pages"] = max_pages
        if max_docs is not None:
            params["max_items"] = max_docs
        if spec.backfill_family == "cls":
            params["use_incremental"] = use_incremental

        ingestion_result = connector.run(spec.connector_dataset, **params)

        result.raw_file_paths = [raw.source_uri for raw in ingestion_result.raw_objects]
        result.success_count = ingestion_result.stats.persisted
        result.failure_count = ingestion_result.stats.failed
        result.skipped_count = ingestion_result.stats.skipped
        result.saved_doc_ids = [
            str(record.entity_id)
            for record in ingestion_result.records[: max_docs or len(ingestion_result.records)]
            if record.entity_id
        ]
        if ingestion_result.error_message:
            result.error_log = ingestion_result.error_message

        if result.success_count > 0:
            last_source_doc_id = result.saved_doc_ids[-1] if result.saved_doc_ids else None
            self.cursor_repo.record_success(cursor_id, last_source_doc_id)

        result.completed_at = datetime.utcnow()
        crawl_run.completed_at = result.completed_at
        crawl_run.success_count = result.success_count
        crawl_run.failure_count = result.failure_count
        crawl_run.skipped_count = result.skipped_count
        crawl_run.error_log = result.error_log
        crawl_run.status = (
            "failed"
            if ingestion_result.status == IngestionStatus.FAILED and result.success_count == 0
            else "completed"
        )
        self.crawl_run_repo.update(crawl_run)

        logger.info(
            "Connector crawl completed",
            source_type=source_type.value,
            dataset=spec.connector_dataset,
            pipeline_kind=spec.pipeline_kind,
            status=ingestion_result.status.value,
            persisted=result.success_count,
            failed=result.failure_count,
        )

    def backfill_source(
        self,
        source_type: SourceType,
        lookback_days: int = 7,
        max_docs: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> CrawlResult:
        """
        补漏：回溯检查是否有遗漏的文档

        与常规抓取的区别：
        - 使用更长的回溯窗口
        - 更宽松的去重（仅检查 source_id）
        - 可以修复之前失败的抓取
        """
        logger.info(f"Starting backfill for {source_type.value}")
        return self.crawl_source(
            source_type=source_type,
            days=lookback_days,
            max_docs=max_docs,
            max_pages=max_pages,
            skip_existing=True,
            enable_backfill=False,
            use_incremental=False,  # backfill 用历史 API
        )

    @staticmethod
    def _naive_utc(dt: datetime) -> datetime:
        """将 timezone-aware datetime 转为 naive UTC，兼容 naive 输入"""
        if dt.tzinfo is not None:
            from datetime import timezone as tz

            return dt.astimezone(tz.utc).replace(tzinfo=None)
        return dt

    def _calculate_time_window(
        self,
        cursor: SourceCursorV1,
        days: int,
        enable_backfill: bool,
    ) -> Tuple[datetime, datetime]:
        """计算抓取时间窗口（所有 datetime 均为 naive UTC）"""
        now = datetime.utcnow()
        end_time = now

        # 从游标获取上次成功时间
        if cursor.last_successful_crawl_time:
            start_time = self._naive_utc(cursor.last_successful_crawl_time)
            # 如果启用补漏，添加回顾窗口
            if enable_backfill and cursor.lookback_window_minutes:
                start_time -= timedelta(minutes=cursor.lookback_window_minutes)
        else:
            # 首次抓取
            start_time = now - timedelta(days=days)

        # 确保不超过最大天数
        max_start = now - timedelta(days=days * 2)
        if start_time < max_start:
            start_time = max_start

        return start_time, end_time

    def _fetch_from_adapter(
        self,
        source_type: SourceType,
        start_time: datetime,
        end_time: datetime,
        max_docs: Optional[int],
        use_incremental: bool = True,
        max_pages: Optional[int] = None,
    ) -> Tuple[List[DocumentV1], List]:
        """从适配器获取数据并转换为 DocumentV1 列表"""
        envelopes: List[DocumentEnvelope] = []
        raw_files: List[Any] = []

        try:
            from core.source_registry import get as get_spec

            spec = get_spec(source_type)
            if spec is None:
                logger.warning(f"No source spec registered for: {source_type}")
                return [], []

            # 动态导入注册类（connector-first；非 connector 时作为 legacy fallback）
            module_path, class_name = spec.connector_class.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            adapter_cls = getattr(module, class_name)
            adapter = adapter_cls()

            # 构建 fetch 参数: spec 中的默认值 + 运行时覆盖
            fetch_kwargs: Dict[str, Any] = {
                "start_date": start_time.strftime("%Y-%m-%d"),
                "end_date": end_time.strftime("%Y-%m-%d"),
                **spec.adapter_kwargs,
            }

            # 动态 max_pages / max_docs
            if max_pages is not None:
                fetch_kwargs["max_pages"] = max_pages
            elif "max_pages" not in fetch_kwargs:
                fetch_kwargs["max_pages"] = 10

            # CLS 特殊: days 和 use_incremental 由调用方控制
            if spec.backfill_family == "cls":
                fetch_kwargs.setdefault("days", (end_time - start_time).days or 1)
                fetch_kwargs["use_incremental"] = use_incremental

            envelopes = adapter.fetch(**fetch_kwargs)
        except Exception as e:
            logger.error(f"Adapter fetch failed for {source_type}: {e}", exc_info=True)

        # Convert DocumentEnvelope → DocumentV1
        docs: List[DocumentV1] = []
        for env in envelopes[:max_docs] if max_docs else envelopes:
            try:
                doc = self._envelope_to_doc_v1(env, source_type)
                docs.append(doc)
            except Exception as e:
                logger.error(f"Failed to convert envelope {env.doc_id}: {e}")

        # Enqueue via CrawlerIngestionBridge for KnowledgePipeline processing
        if envelopes:
            self._enqueue_to_bridge(source_type, envelopes)

        logger.info(f"Fetched {len(docs)} docs from {source_type.value}")
        return docs, raw_files

    @staticmethod
    def _envelope_to_doc_v1(envelope: DocumentEnvelope, source_type: SourceType) -> DocumentV1:
        """将 DocumentEnvelope 转为 DocumentV1"""
        import hashlib

        from core.contracts.documents_v1 import DocType, DocumentTimeliness
        from core.source_registry import get as get_spec

        spec = get_spec(source_type)
        doc_type = spec.doc_type if spec else DocType.NEWS

        metadata = dict(envelope.metadata or {})
        source_doc_id = (
            (str(v) if (v := metadata.get("telegram_id")) else "")
            or (str(v) if (v := metadata.get("obj_id")) else "")
            or envelope.doc_id
        )

        content = envelope.canonical_text or envelope.raw_text
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None

        return DocumentV1(
            doc_id=envelope.doc_id,
            doc_type=doc_type,
            source_type=source_type,
            title=envelope.title,
            content=content,
            source_name=envelope.source_name,
            source_url=envelope.metadata.get("url") if envelope.metadata else None,
            doc_metadata=metadata,
            source_metadata={"source_doc_id": source_doc_id},
            content_hash=content_hash,
            language=envelope.language,
            timeliness=DocumentTimeliness(publish_time=envelope.published_at),
        )

    @staticmethod
    def _enqueue_items(source_type_str: str, items: List[Dict[str, Any]]) -> None:
        """将 item dict 列表通过 CrawlerIngestionBridge 送入摄取队列

        每个 item dict 需包含: id, title, content, 可选 url, published_at, source_name
        """
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.ingestion_repository import IngestionQueueRepository
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge
        from services.ingestion_queue_service import IngestionQueueService

        db = SessionLocal()
        try:
            repo = IngestionQueueRepository(db)
            queue_service = IngestionQueueService(repository=repo)
            bridge = CrawlerIngestionBridge(queue_service=queue_service)
            for item in items:
                bridge.submit_crawled_item(source_type_str, item)
            db.commit()
            logger.info(f"Enqueued {len(items)} items from {source_type_str}")
        except Exception as e:
            logger.error(f"Failed to enqueue items to bridge: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _enqueue_to_bridge(
        source_type: SourceType,
        envelopes: List[DocumentEnvelope],
    ) -> None:
        """将抓取到的 DocumentEnvelope 列表送入摄取队列"""
        source_type_str = source_type.value if hasattr(source_type, "value") else str(source_type)
        items: List[Dict[str, Any]] = []
        for env in envelopes:
            items.append(
                {
                    "id": env.doc_id,
                    "title": env.title,
                    "content": env.canonical_text or env.raw_text,
                    "url": env.metadata.get("url") if env.metadata else None,
                    "published_at": env.published_at,
                    "source_name": env.source_name,
                }
            )
        CrawlOrchestrator._enqueue_items(source_type_str, items)

    def _deduplicate_docs(
        self,
        source_type: SourceType,
        docs: List[DocumentV1],
    ) -> Tuple[List[DocumentV1], List[DocumentV1]]:
        """去重文档"""
        if not docs:
            return [], []

        # 1. 收集需要检查的 ID 和哈希
        source_doc_ids: List[str] = []
        content_hashes: List[str] = []
        doc_ids: List[str] = []

        for doc in docs:
            source_doc_id = doc.source_metadata.get("source_doc_id") or doc.source_metadata.get(
                "original_id"
            )
            if source_doc_id:
                source_doc_ids.append(source_doc_id)
            if doc.content_hash:
                content_hashes.append(doc.content_hash)
            doc_ids.append(doc.doc_id)

        # 2. 批量查询已存在的
        existing_source_ids = self.doc_repo.get_existing_source_ids(source_type, source_doc_ids)
        existing_content_hashes = self.doc_repo.get_existing_content_hashes(content_hashes)
        existing_doc_ids = self.doc_repo.get_existing_doc_ids(doc_ids)

        # 3. 逐个检查
        kept: List[DocumentV1] = []
        duplicates: List[DocumentV1] = []

        batch_results = self.deduplication.batch_check(
            docs, existing_source_ids, existing_content_hashes
        )

        for doc in docs:
            result = batch_results.get(doc.doc_id)
            is_dup_by_meta = result is not None and result.is_duplicate
            is_dup_by_doc_id = doc.doc_id in existing_doc_ids
            if is_dup_by_meta or is_dup_by_doc_id:
                duplicates.append(doc)
            else:
                kept.append(doc)

        return kept, duplicates

    def _sync_dedup_state(self, source_type: SourceType) -> None:
        """同步爬虫级去重文件与数据库状态

        爬虫使用的文件级去重（如 CLS DeduplicationStore）独立于数据库。
        如果文档被从数据库删除但去重文件仍保留条目，则重新爬取时这些项会被永久跳过。
        此方法在每次抓取前将去重文件修剪为仅包含数据库中确实存在的文档 ID。

        Args:
            source_type: 来源类型
        """
        from core.source_registry import get as get_spec
        from data_layer.crawlers.cls.utils.deduplication import DeduplicationStore

        spec = get_spec(source_type)
        if spec is None:
            return

        state_path = (spec.adapter_kwargs or {}).get("state_path")
        if not state_path:
            return

        state_file = Path(state_path)
        if not state_file.exists():
            return

        try:
            src = source_type.value if hasattr(source_type, "value") else str(source_type)
            rows = self.db.execute(
                text(
                    "SELECT source_metadata->>'source_doc_id' FROM document_v1 WHERE source_type = :st"
                ),
                {"st": src},
            ).fetchall()
            valid_ids = {r[0] for r in rows if r[0]}

            store = DeduplicationStore(state_path)
            before = store.get_count()
            removed = store.remove_stale(valid_ids)
            if removed > 0:
                logger.info(
                    f"Dedup state synced for {src}: removed {removed} orphan entries "
                    f"({before} → {store.get_count()})"
                )
        except Exception as e:
            logger.error(f"Failed to sync dedup state for {source_type}: {e}", exc_info=True)

    def deep_backfill_step(
        self,
        batch_size: int = 10,
        state_path: str = "./data/crawlers/cls/.deep_backfill_state.json",
    ) -> CrawlResult:
        """深度历史回补：通过 /detail/{id} 逐条获取一批历史电报

        与常规 crawl_source() 的区别：
        - 不通过适配器的 fetch()，而是用 fetch_deep_backfill_batch()
        - 使用独立 DB 会话
        - 非常低频运行（每 30 分钟一批）
        - 文档保存后送入 IngestionBridge，由 KnowledgePipeline 做 LLM 提取
        """
        from data_layer.adapters.cls_adapter import CLSAdapter
        from data_layer.repositories.base import SessionLocal

        result = CrawlResult()
        result.source_type = SourceType.CLS

        db = SessionLocal()
        try:
            doc_repo = DocumentV1Repository(db)
            adapter = CLSAdapter()

            envelopes = adapter.fetch_deep_backfill_batch(
                batch_size=batch_size,
                state_path=state_path,
            )
            if not envelopes:
                return result

            docs: List[DocumentV1] = []
            for env in envelopes:
                try:
                    doc = self._envelope_to_doc_v1(env, SourceType.CLS)
                    docs.append(doc)
                except Exception as e:
                    logger.error(f"Failed to convert deep backfill envelope {env.doc_id}: {e}")

            # 去重
            new_docs, duplicates = self._deduplicate_docs(SourceType.CLS, docs)
            result.skipped_count = len(duplicates)
            result.duplicate_doc_ids = [d.doc_id for d in duplicates]

            # 保存
            for doc in new_docs:
                try:
                    saved_doc = doc_repo.create(doc)
                    result.saved_doc_ids.append(saved_doc.doc_id)
                    result.success_count += 1
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to save deep backfill doc {doc.doc_id}: {e}")
                    result.failure_count += 1

            db.commit()

            # 送入摄取队列，由 KnowledgePipeline 做 LLM 提取
            if envelopes:
                self._enqueue_to_bridge(SourceType.CLS, envelopes)

            result.completed_at = datetime.utcnow()

            logger.info(
                f"Deep backfill step completed: "
                f"{result.success_count} saved, "
                f"{result.skipped_count} skipped, "
                f"{result.failure_count} failed"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Deep backfill step failed: {e}", exc_info=True)
            result.completed_at = datetime.utcnow()
            result.error_log = str(e)
        finally:
            db.close()

        return result

    def zq_deep_backfill_step(
        self,
        state_path: str = "./data/crawlers/zq/.deep_backfill_state.json",
        window_days: int = 5,
        max_pages: int = 30,
    ) -> CrawlResult:
        """ZQ 滑动窗口深度历史回补

        用 5 天滑动窗口从旧到新逐窗口回补 ZQ 历史数据。
        使用状态文件跟踪进度，每次处理一个窗口。
        """
        import json
        from datetime import timedelta

        result = CrawlResult()
        result.source_type = SourceType.ZHIQIU_REPORTS

        state_file = Path(state_path)
        state: Dict[str, Any] = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                state = {}

        if not state:
            state = {
                "source_order": [
                    "zhiqiu_reports",
                    "zhiqiu_wechat",
                    "zhiqiu_transcript",
                ],
                "current_source_idx": 0,
                "current_window_start": None,
                "completed": False,
                "total_saved": 0,
                "total_skipped": 0,
            }

        if state.get("completed"):
            logger.info("ZQ deep backfill already completed, nothing to do")
            return result

        source_order = state["source_order"]
        current_idx = state.get("current_source_idx", 0)

        if current_idx >= len(source_order):
            state["completed"] = True
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            logger.info("ZQ deep backfill: all sources done")
            return result

        source_type_str = source_order[current_idx]
        source_type = SourceType(source_type_str)
        source_label = source_type_str.replace("zhiqiu_", "ZQ ").title()

        now = datetime.utcnow()
        if state["current_window_start"] is None:
            # 从 30 天前开始
            state["current_window_start"] = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        win_start_str = str(state["current_window_start"])
        win_start = datetime.strptime(win_start_str, "%Y-%m-%d")
        win_end = win_start + timedelta(days=window_days)

        if win_end >= now:
            # 当前来源完成，移到下一个来源
            logger.info(f"ZQ deep backfill: {source_label} done, moving to next source")
            state["current_source_idx"] = current_idx + 1
            state["current_window_start"] = None
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            return self.zq_deep_backfill_step(
                state_path=state_path, window_days=window_days, max_pages=max_pages
            )

        logger.info(
            f"ZQ deep backfill: {source_label} window {win_start_str} → {win_end.strftime('%Y-%m-%d')}"
        )

        try:
            step_result = self.crawl_source(
                source_type=source_type,
                days=window_days,
                max_pages=max_pages,
                skip_existing=True,
                enable_backfill=False,
                use_incremental=False,
            )

            result.success_count = step_result.success_count
            result.skipped_count = step_result.skipped_count
            result.failure_count = step_result.failure_count
            result.saved_doc_ids = step_result.saved_doc_ids

            state["total_saved"] = state.get("total_saved", 0) + result.success_count
            state["total_skipped"] = state.get("total_skipped", 0) + result.skipped_count
            state["current_window_start"] = win_end.strftime("%Y-%m-%d")

            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))

            logger.info(
                f"ZQ deep backfill {source_label}: {result.success_count} saved, "
                f"{result.skipped_count} skipped. "
                f"Total so far: {state['total_saved']} saved, {state['total_skipped']} skipped"
            )
        except Exception as e:
            logger.error(f"ZQ deep backfill step failed: {e}", exc_info=True)
            result.error_log = str(e)
            result.completed_at = datetime.utcnow()

        return result

    def get_latest_document_time(self, source_type: SourceType) -> Optional[datetime]:
        """获取指定来源最近一条文档的 created_at 时间（naive UTC）

        用于双重缺口检测：当 cursor 被手动触发污染时，DB 实际文档时间
        可以揭示真实的数据覆盖缺口。
        """
        from data_layer.repositories.models import DocumentV1DB

        result = (
            self.db.query(DocumentV1DB)
            .filter(DocumentV1DB.source_type == source_type.value)
            .order_by(DocumentV1DB.created_at.desc())
            .first()
        )
        if result and result.created_at:
            return self._naive_utc(result.created_at)
        return None

    def get_crawl_status(self, source_type: SourceType) -> Optional[Dict[str, Any]]:
        """获取抓取状态（使用独立会话避免 PendingRollbackError）"""
        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        try:
            crawl_run_repo = CrawlRunV1Repository(db)
            cursor_repo = SourceCursorV1Repository(db)

            latest_run = crawl_run_repo.get_latest(source_type)
            cursor = cursor_repo.get_by_source_type(source_type)

            if not latest_run and not cursor:
                return None

            return {
                "source_type": source_type.value,
                "latest_run": latest_run.model_dump() if latest_run else None,
                "cursor": cursor.model_dump() if cursor else None,
            }
        finally:
            db.close()
