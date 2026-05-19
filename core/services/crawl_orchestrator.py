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
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import CrawlRunV1, DocumentEnvelope, DocumentV1, SourceCursorV1, SourceType
from core.observability import get_logger
from core.services.deduplication_service import DeduplicationService
from core.services.raw_storage_service import RawStorageService
from core.utils.id_gen import generate_id
from data_layer.repositories.base import get_db
from data_layer.repositories.documents_v1 import (
    CrawlRunV1Repository,
    DocumentV1Repository,
    SourceCursorV1Repository,
)

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
        skip_existing: bool = True,
        enable_backfill: bool = True,
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

            # 4. 执行抓取（委托给适配器）
            docs, raw_files = self._fetch_from_adapter(
                source_type,
                start_time,
                end_time,
                max_docs,
            )

            result.raw_file_paths = [f.file_path for f in raw_files]

            # 5. 去重检查
            if skip_existing:
                docs, duplicates = self._deduplicate_docs(source_type, docs)
                result.skipped_count = len(duplicates)
                result.duplicate_doc_ids = [d.doc_id for d in duplicates]

            # 6. 保存文档
            for doc in docs:
                try:
                    saved_doc = self.doc_repo.create(doc)
                    result.saved_doc_ids.append(saved_doc.doc_id)
                    self.deduplication.mark_seen(saved_doc)
                    result.success_count += 1
                except Exception as e:
                    logger.error(f"Failed to save doc {doc.doc_id}: {e}")
                    result.failure_count += 1

            # 7. 更新游标
            if result.success_count > 0:
                last_doc = None
                if docs:
                    last_doc = docs[-1]
                last_source_doc_id = None
                if last_doc:
                    last_source_doc_id = last_doc.source_metadata.get(
                        "source_doc_id"
                    ) or last_doc.source_metadata.get("original_id")
                self.cursor_repo.record_success(cursor.cursor_id, last_source_doc_id)
            else:
                self.cursor_repo.record_success(cursor.cursor_id, None)

            # 8. 更新抓取记录
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

    def backfill_source(
        self,
        source_type: SourceType,
        lookback_days: int = 7,
        max_docs: Optional[int] = None,
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
            skip_existing=True,
            enable_backfill=False,
        )

    def _calculate_time_window(
        self,
        cursor: SourceCursorV1,
        days: int,
        enable_backfill: bool,
    ) -> Tuple[datetime, datetime]:
        """计算抓取时间窗口"""
        now = datetime.utcnow()
        end_time = now

        # 从游标获取上次成功时间
        if cursor.last_successful_crawl_time:
            start_time = cursor.last_successful_crawl_time
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
    ) -> Tuple[List[DocumentV1], List]:
        """从适配器获取数据并转换为 DocumentV1 列表"""
        envelopes: List[DocumentEnvelope] = []
        raw_files: List[Any] = []

        try:
            if source_type == SourceType.CAILIAN_SHE:
                from data_layer.adapters.cls_adapter import CLSAdapter

                adapter = CLSAdapter()
                envelopes = adapter.fetch(
                    start_date=start_time.strftime("%Y-%m-%d"),
                    end_date=end_time.strftime("%Y-%m-%d"),
                    days=(end_time - start_time).days or 1,
                )
            elif source_type == SourceType.CHINA_SECURITY_JOURNAL:
                from data_layer.adapters.cnstock_adapter import CNStockAdapter

                adapter = CNStockAdapter()
                envelopes = adapter.fetch(
                    start_date=start_time.strftime("%Y-%m-%d"),
                    end_date=end_time.strftime("%Y-%m-%d"),
                )
            elif source_type == SourceType.ZHIQIU_REPORTS:
                from data_layer.adapters.zq_adapter import ZQAdapter

                adapter = ZQAdapter()
                envelopes = adapter.fetch(
                    start_date=start_time.strftime("%Y-%m-%d"),
                    end_date=end_time.strftime("%Y-%m-%d"),
                )
            else:
                logger.warning(f"No adapter for source_type: {source_type}")
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
        from core.contracts.documents_v1 import DocType

        doc_type_map = {
            SourceType.CAILIAN_SHE: DocType.NEWS,
            SourceType.CHINA_SECURITY_JOURNAL: DocType.NEWS,
            SourceType.ZHIQIU_REPORTS: DocType.REPORT,
        }
        return DocumentV1(
            doc_id=envelope.doc_id,
            doc_type=doc_type_map.get(source_type, DocType.NEWS),
            source_type=source_type,
            title=envelope.title,
            content=envelope.canonical_text or envelope.raw_text,
            source_name=envelope.source_name,
            source_url=envelope.metadata.get("url") if envelope.metadata else None,
            doc_metadata=envelope.metadata or {},
            language=envelope.language,
        )

    @staticmethod
    def _enqueue_to_bridge(
        source_type: SourceType,
        envelopes: List[DocumentEnvelope],
    ) -> None:
        """将抓取到的文档通过 CrawlerIngestionBridge 送入摄取队列"""
        try:
            from core.services.crawler_ingestion_bridge import CrawlerIngestionBridge
            from core.services.ingestion_queue_service import IngestionQueueService
            from data_layer.repositories.base import SessionLocal
            from data_layer.repositories.ingestion_repository import IngestionQueueRepository

            db = SessionLocal()
            try:
                repo = IngestionQueueRepository(db)
                queue_service = IngestionQueueService(repository=repo)
                bridge = CrawlerIngestionBridge(queue_service=queue_service)

                source_type_str = (
                    source_type.value if hasattr(source_type, "value") else str(source_type)
                )
                for env in envelopes:
                    item = {
                        "id": env.doc_id,
                        "title": env.title,
                        "content": env.canonical_text or env.raw_text,
                        "url": env.metadata.get("url") if env.metadata else None,
                        "published_at": env.published_at,
                        "source_name": env.source_name,
                    }
                    bridge.submit_crawled_item(source_type_str, item)
                logger.info(f"Enqueued {len(envelopes)} items from {source_type_str}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to enqueue to bridge: {e}", exc_info=True)

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

        for doc in docs:
            source_doc_id = doc.source_metadata.get("source_doc_id") or doc.source_metadata.get(
                "original_id"
            )
            if source_doc_id:
                source_doc_ids.append(source_doc_id)
            if doc.content_hash:
                content_hashes.append(doc.content_hash)

        # 2. 批量查询已存在的
        existing_source_ids = self.doc_repo.get_existing_source_ids(source_type, source_doc_ids)
        existing_content_hashes = self.doc_repo.get_existing_content_hashes(content_hashes)

        # 3. 逐个检查
        kept: List[DocumentV1] = []
        duplicates: List[DocumentV1] = []

        batch_results = self.deduplication.batch_check(
            docs, existing_source_ids, existing_content_hashes
        )

        for doc in docs:
            result = batch_results.get(doc.doc_id)
            if result and result.is_duplicate:
                duplicates.append(doc)
            else:
                kept.append(doc)

        return kept, duplicates

    def get_crawl_status(self, source_type: SourceType) -> Optional[Dict[str, Any]]:
        """获取抓取状态"""
        latest_run = self.crawl_run_repo.get_latest(source_type)
        cursor = self.cursor_repo.get_by_source_type(source_type)

        if not latest_run and not cursor:
            return None

        return {
            "source_type": source_type.value,
            "latest_run": latest_run.model_dump() if latest_run else None,
            "cursor": cursor.model_dump() if cursor else None,
        }
