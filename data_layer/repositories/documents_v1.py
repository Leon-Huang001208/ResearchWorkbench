"""
AlphaFoundry v1 文档 Repository.

实现 Issue #42 要求的数据库操作，包括：
- document_v1 表的 CRUD 操作
- document_chunk_v1 表的 CRUD 操作
- document_tag_v1 表的 CRUD 操作
- document_summary_v1 表的 CRUD 操作
- document_entity_mention_v1 表的 CRUD 操作
- document_event_v1 表的 CRUD 操作
- crawl_run_v1 表的 CRUD 操作
- source_cursor_v1 表的 CRUD 操作
- report_run_v1 表的 CRUD 操作
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from core.contracts import (
    CrawlRunV1,
    DocType,
    DocumentChunkV1,
    DocumentEventV1,
    DocumentSummaryV1,
    DocumentTagV1,
    DocumentV1,
    EntityMentionV1,
    ReportRunV1,
    SourceCursorV1,
    SourceType,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id

from .base import BaseRepository
from .models import (
    CrawlRunV1DB,
    DocumentChunkV1DB,
    DocumentEventV1DB,
    DocumentSummaryV1DB,
    DocumentTagV1DB,
    DocumentV1DB,
    EntityMentionV1DB,
    ReportRunV1DB,
    SourceCursorV1DB,
)

logger = get_logger(__name__)


# =============================================================================
# Document Repository
# =============================================================================


class DocumentV1Repository(BaseRepository):
    """文档 Repository - 统一文档 v1"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, doc: DocumentV1) -> DocumentV1:
        """创建新文档"""
        db_doc = DocumentV1DB.from_contract(doc)
        self.db.add(db_doc)
        self.db.commit()
        self.db.refresh(db_doc)
        logger.info(f"Created document: {doc.doc_id}")
        return db_doc.to_contract()

    def get(self, doc_id: str) -> Optional[DocumentV1]:
        """根据 ID 获取文档"""
        db_doc = self.db.get(DocumentV1DB, doc_id)
        if db_doc:
            return db_doc.to_contract()
        return None

    def get_by_content_hash(self, content_hash: str) -> Optional[DocumentV1]:
        """根据内容哈希获取文档（用于去重）"""
        stmt = select(DocumentV1DB).where(DocumentV1DB.content_hash == content_hash)
        result = self.db.execute(stmt).scalar_one_or_none()
        if result:
            return result.to_contract()
        return None

    def update(self, doc: DocumentV1) -> Optional[DocumentV1]:
        """更新文档"""
        db_doc = self.db.get(DocumentV1DB, doc.doc_id)
        if not db_doc:
            return None

        # 更新字段
        db_doc.title = doc.title
        db_doc.summary = doc.summary
        db_doc.content = doc.content
        db_doc.doc_metadata = doc.doc_metadata
        db_doc.source_metadata = doc.source_metadata
        db_doc.classification = doc.classification.model_dump() if doc.classification else {}
        db_doc.quality = doc.quality.model_dump() if doc.quality else {}
        db_doc.evidence_profile = doc.evidence_profile.model_dump() if doc.evidence_profile else {}
        db_doc.timeliness = doc.timeliness.model_dump() if doc.timeliness else {}
        db_doc.processing = doc.processing.model_dump() if doc.processing else {}
        db_doc.review = doc.review.model_dump() if doc.review else {}
        db_doc.extra = doc.extra
        db_doc.source_name = doc.source_name
        db_doc.source_url = doc.source_url
        db_doc.language = doc.language
        db_doc.content_hash = doc.content_hash
        db_doc.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(db_doc)
        logger.info(f"Updated document: {doc.doc_id}")
        return db_doc.to_contract()

    def delete(self, doc_id: str) -> bool:
        """删除文档"""
        db_doc = self.db.get(DocumentV1DB, doc_id)
        if db_doc:
            self.db.delete(db_doc)
            self.db.commit()
            logger.info(f"Deleted document: {doc_id}")
            return True
        return False

    def list(
        self,
        source_type: Optional[SourceType] = None,
        doc_type: Optional[DocType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DocumentV1]:
        """列出文档，支持过滤"""
        stmt = select(DocumentV1DB).order_by(desc(DocumentV1DB.created_at))

        if source_type:
            stmt = stmt.where(DocumentV1DB.source_type == source_type.value)
        if doc_type:
            stmt = stmt.where(DocumentV1DB.doc_type == doc_type.value)

        stmt = stmt.limit(limit).offset(offset)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def search_by_keyword(
        self,
        keyword: str,
        limit: int = 50,
    ) -> List[DocumentV1]:
        """按关键词搜索文档"""
        stmt = (
            select(DocumentV1DB)
            .where(
                or_(
                    DocumentV1DB.title.ilike(f"%{keyword}%"),
                    DocumentV1DB.content.ilike(f"%{keyword}%"),
                )
            )
            .order_by(desc(DocumentV1DB.created_at))
            .limit(limit)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def count(self) -> int:
        """统计文档总数"""
        from sqlalchemy import func

        stmt = select(func.count(DocumentV1DB.doc_id))
        return self.db.execute(stmt).scalar_one()

    def get_existing_source_ids(
        self,
        source_type: SourceType,
        source_doc_ids: List[str],
    ) -> Dict[str, str]:
        """
        批量检查已存在的 source_doc_id

        Args:
            source_type: 来源类型
            source_doc_ids: 来源文档ID列表

        Returns:
            {source_doc_id -> doc_id 映射
        """
        if not source_doc_ids:
            return {}

        # 查询 source_metadata->source_doc_id
        stmt = select(DocumentV1DB.doc_id, DocumentV1DB.source_metadata).where(
            and_(
                DocumentV1DB.source_type == source_type.value,
            )
        )
        results = self.db.execute(stmt).all()

        existing: Dict[str, str] = {}
        for doc_id, source_meta in results:
            source_meta_dict = source_meta or {}
            source_doc_id = source_meta_dict.get("source_doc_id") or source_meta_dict.get(
                "original_id"
            )
            if source_doc_id and source_doc_id in source_doc_ids:
                existing[source_doc_id] = doc_id

        return existing

    def get_existing_content_hashes(self, content_hashes: List[str]) -> Dict[str, str]:
        """
        批量检查已存在的 content_hash

        Returns:
            {content_hash -> doc_id} 映射
        """
        if not content_hashes:
            return {}

        stmt = select(DocumentV1DB.doc_id, DocumentV1DB.content_hash).where(
            DocumentV1DB.content_hash.in_(content_hashes)
        )
        results = self.db.execute(stmt).all()

        return {h: doc_id for doc_id, h in results if h}

    def list_by_time_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source_type: Optional[SourceType] = None,
        limit: int = 100,
    ) -> List[DocumentV1]:
        """
        按时间范围列出文档（用于回测视角）

        使用 available_time 来确定文档对回测的可见性
        """
        stmt = select(DocumentV1DB)

        conditions = []
        if start_time:
            conditions.append(DocumentV1DB.available_time >= start_time)
        if end_time:
            conditions.append(DocumentV1DB.available_time <= end_time)
        if source_type:
            conditions.append(DocumentV1DB.source_type == source_type.value)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(DocumentV1DB.available_time)).limit(limit)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]


# =============================================================================
# Document Chunk Repository
# =============================================================================


class DocumentChunkV1Repository(BaseRepository):
    """文档分块 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, chunk: DocumentChunkV1) -> DocumentChunkV1:
        """创建分块"""
        db_chunk = DocumentChunkV1DB.from_contract(chunk)
        self.db.add(db_chunk)
        self.db.commit()
        self.db.refresh(db_chunk)
        return db_chunk.to_contract()

    def bulk_create(self, chunks: List[DocumentChunkV1]) -> List[DocumentChunkV1]:
        """批量创建分块"""
        db_chunks = [DocumentChunkV1DB.from_contract(c) for c in chunks]
        self.db.add_all(db_chunks)
        self.db.commit()
        for db_chunk in db_chunks:
            self.db.refresh(db_chunk)
        return [c.to_contract() for c in db_chunks]

    def get(self, chunk_id: str) -> Optional[DocumentChunkV1]:
        """获取分块"""
        db_chunk = self.db.get(DocumentChunkV1DB, chunk_id)
        if db_chunk:
            return db_chunk.to_contract()
        return None

    def get_by_doc_id(self, doc_id: str) -> List[DocumentChunkV1]:
        """获取文档的所有分块"""
        stmt = (
            select(DocumentChunkV1DB)
            .where(DocumentChunkV1DB.doc_id == doc_id)
            .order_by(DocumentChunkV1DB.chunk_index)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def delete_by_doc_id(self, doc_id: str) -> int:
        """删除文档的所有分块，返回删除数量"""
        stmt = select(DocumentChunkV1DB).where(DocumentChunkV1DB.doc_id == doc_id)
        results = self.db.execute(stmt).scalars().all()
        count = len(results)
        for r in results:
            self.db.delete(r)
        self.db.commit()
        return count


# =============================================================================
# Document Tag Repository
# =============================================================================


class DocumentTagV1Repository(BaseRepository):
    """文档标签 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, tag: DocumentTagV1) -> DocumentTagV1:
        """创建标签"""
        db_tag = DocumentTagV1DB.from_contract(tag)
        self.db.add(db_tag)
        self.db.commit()
        self.db.refresh(db_tag)
        return db_tag.to_contract()

    def bulk_create(self, tags: List[DocumentTagV1]) -> List[DocumentTagV1]:
        """批量创建标签"""
        db_tags = [DocumentTagV1DB.from_contract(t) for t in tags]
        self.db.add_all(db_tags)
        self.db.commit()
        for db_tag in db_tags:
            self.db.refresh(db_tag)
        return [t.to_contract() for t in db_tags]

    def get_by_doc_id(self, doc_id: str) -> List[DocumentTagV1]:
        """获取文档的所有标签"""
        stmt = select(DocumentTagV1DB).where(DocumentTagV1DB.doc_id == doc_id)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def get_by_tag(self, tag: str, limit: int = 100) -> List[DocumentTagV1]:
        """按标签搜索"""
        stmt = select(DocumentTagV1DB).where(DocumentTagV1DB.tag == tag).limit(limit)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]


# =============================================================================
# Document Summary Repository
# =============================================================================


class DocumentSummaryV1Repository(BaseRepository):
    """文档摘要 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, summary: DocumentSummaryV1) -> DocumentSummaryV1:
        """创建摘要"""
        db_summary = DocumentSummaryV1DB.from_contract(summary)
        self.db.add(db_summary)
        self.db.commit()
        self.db.refresh(db_summary)
        return db_summary.to_contract()

    def get_by_doc_id(self, doc_id: str) -> List[DocumentSummaryV1]:
        """获取文档的所有摘要"""
        stmt = select(DocumentSummaryV1DB).where(DocumentSummaryV1DB.doc_id == doc_id)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def get_by_doc_and_type(self, doc_id: str, summary_type: str) -> Optional[DocumentSummaryV1]:
        """获取文档的指定类型摘要"""
        stmt = select(DocumentSummaryV1DB).where(
            and_(
                DocumentSummaryV1DB.doc_id == doc_id,
                DocumentSummaryV1DB.summary_type == summary_type,
            )
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        if result:
            return result.to_contract()
        return None


# =============================================================================
# Entity Mention Repository
# =============================================================================


class EntityMentionV1Repository(BaseRepository):
    """实体提及 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, mention: EntityMentionV1) -> EntityMentionV1:
        """创建实体提及"""
        db_mention = EntityMentionV1DB.from_contract(mention)
        self.db.add(db_mention)
        self.db.commit()
        self.db.refresh(db_mention)
        return db_mention.to_contract()

    def bulk_create(self, mentions: List[EntityMentionV1]) -> List[EntityMentionV1]:
        """批量创建实体提及"""
        db_mentions = [EntityMentionV1DB.from_contract(m) for m in mentions]
        self.db.add_all(db_mentions)
        self.db.commit()
        for db_mention in db_mentions:
            self.db.refresh(db_mention)
        return [m.to_contract() for m in db_mentions]

    def get_by_doc_id(self, doc_id: str) -> List[EntityMentionV1]:
        """获取文档的所有实体提及"""
        stmt = select(EntityMentionV1DB).where(EntityMentionV1DB.doc_id == doc_id)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def get_by_entity_type(self, entity_type: str, limit: int = 100) -> List[EntityMentionV1]:
        """按实体类型搜索"""
        stmt = (
            select(EntityMentionV1DB)
            .where(EntityMentionV1DB.entity_type == entity_type)
            .limit(limit)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]


# =============================================================================
# Document Event Repository
# =============================================================================


class DocumentEventV1Repository(BaseRepository):
    """文档事件 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, event: DocumentEventV1) -> DocumentEventV1:
        """创建事件"""
        db_event = DocumentEventV1DB.from_contract(event)
        self.db.add(db_event)
        self.db.commit()
        self.db.refresh(db_event)
        return db_event.to_contract()

    def bulk_create(self, events: List[DocumentEventV1]) -> List[DocumentEventV1]:
        """批量创建事件"""
        db_events = [DocumentEventV1DB.from_contract(e) for e in events]
        self.db.add_all(db_events)
        self.db.commit()
        for db_event in db_events:
            self.db.refresh(db_event)
        return [e.to_contract() for e in db_events]

    def get_by_doc_id(self, doc_id: str) -> List[DocumentEventV1]:
        """获取文档的所有事件"""
        stmt = select(DocumentEventV1DB).where(DocumentEventV1DB.doc_id == doc_id)
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def get_by_event_type(self, event_type: str, limit: int = 100) -> List[DocumentEventV1]:
        """按事件类型搜索"""
        stmt = (
            select(DocumentEventV1DB)
            .where(DocumentEventV1DB.event_type == event_type)
            .order_by(desc(DocumentEventV1DB.event_time))
            .limit(limit)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]


# =============================================================================
# Crawl Run Repository
# =============================================================================


class CrawlRunV1Repository(BaseRepository):
    """抓取运行记录 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, run: CrawlRunV1) -> CrawlRunV1:
        """创建抓取记录"""
        db_run = CrawlRunV1DB.from_contract(run)
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)
        return db_run.to_contract()

    def get(self, run_id: str) -> Optional[CrawlRunV1]:
        """获取抓取记录"""
        db_run = self.db.get(CrawlRunV1DB, run_id)
        if db_run:
            return db_run.to_contract()
        return None

    def update(self, run: CrawlRunV1) -> Optional[CrawlRunV1]:
        """更新抓取记录"""
        db_run = self.db.get(CrawlRunV1DB, run.run_id)
        if not db_run:
            return None

        db_run.status = run.status
        db_run.started_at = run.started_at
        db_run.completed_at = run.completed_at
        db_run.success_count = run.success_count
        db_run.failure_count = run.failure_count
        db_run.skipped_count = run.skipped_count
        db_run.error_log = run.error_log
        db_run.config = run.config

        self.db.commit()
        self.db.refresh(db_run)
        return db_run.to_contract()

    def list_by_source_type(self, source_type: SourceType, limit: int = 50) -> List[CrawlRunV1]:
        """按来源类型列出抓取记录"""
        stmt = (
            select(CrawlRunV1DB)
            .where(CrawlRunV1DB.source_type == source_type.value)
            .order_by(desc(CrawlRunV1DB.created_at))
            .limit(limit)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]

    def get_latest(self, source_type: SourceType) -> Optional[CrawlRunV1]:
        """获取指定来源的最新抓取记录"""
        stmt = (
            select(CrawlRunV1DB)
            .where(CrawlRunV1DB.source_type == source_type.value)
            .order_by(desc(CrawlRunV1DB.created_at))
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        if result:
            return result.to_contract()
        return None


# =============================================================================
# Source Cursor Repository
# =============================================================================


class SourceCursorV1Repository(BaseRepository):
    """来源游标 Repository - 用于增量抓取"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, cursor: SourceCursorV1) -> SourceCursorV1:
        """创建游标"""
        db_cursor = SourceCursorV1DB.from_contract(cursor)
        self.db.add(db_cursor)
        self.db.commit()
        self.db.refresh(db_cursor)
        return db_cursor.to_contract()

    def get(self, cursor_id: str) -> Optional[SourceCursorV1]:
        """获取游标"""
        db_cursor = self.db.get(SourceCursorV1DB, cursor_id)
        if db_cursor:
            return db_cursor.to_contract()
        return None

    def get_by_source_type(self, source_type: SourceType) -> Optional[SourceCursorV1]:
        """按来源类型获取游标"""
        stmt = select(SourceCursorV1DB).where(SourceCursorV1DB.source_type == source_type.value)
        result = self.db.execute(stmt).scalar_one_or_none()
        if result:
            return result.to_contract()
        return None

    def update(self, cursor: SourceCursorV1) -> Optional[SourceCursorV1]:
        """更新游标"""
        db_cursor = self.db.get(SourceCursorV1DB, cursor.cursor_id)
        if not db_cursor:
            return None

        db_cursor.source_name = cursor.source_name
        db_cursor.last_successful_crawl_time = cursor.last_successful_crawl_time
        db_cursor.last_source_doc_id = cursor.last_source_doc_id
        db_cursor.lookback_window_minutes = cursor.lookback_window_minutes
        db_cursor.consecutive_failures = cursor.consecutive_failures
        db_cursor.is_paused = cursor.is_paused
        db_cursor.config = cursor.config
        db_cursor.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(db_cursor)
        return db_cursor.to_contract()

    def get_or_create(
        self, source_type: SourceType, source_name: Optional[str] = None
    ) -> SourceCursorV1:
        """获取或创建游标"""
        existing = self.get_by_source_type(source_type)
        if existing:
            return existing

        # 创建新游标
        new_cursor = SourceCursorV1(
            cursor_id=generate_id(),
            source_type=source_type,
            source_name=source_name,
        )
        return self.create(new_cursor)

    def record_success(self, cursor_id: str, last_doc_id: Optional[str] = None):
        """记录成功抓取"""
        db_cursor = self.db.get(SourceCursorV1DB, cursor_id)
        if db_cursor:
            db_cursor.last_successful_crawl_time = datetime.utcnow()
            if last_doc_id:
                db_cursor.last_source_doc_id = last_doc_id
            db_cursor.consecutive_failures = 0
            db_cursor.updated_at = datetime.utcnow()
            self.db.commit()

    def record_failure(self, cursor_id: str):
        """记录失败抓取"""
        db_cursor = self.db.get(SourceCursorV1DB, cursor_id)
        if db_cursor:
            db_cursor.consecutive_failures += 1
            db_cursor.updated_at = datetime.utcnow()
            self.db.commit()


# =============================================================================
# Report Run Repository
# =============================================================================


class ReportRunV1Repository(BaseRepository):
    """报告运行记录 Repository"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, run: ReportRunV1) -> ReportRunV1:
        """创建报告运行记录"""
        db_run = ReportRunV1DB.from_contract(run)
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)
        return db_run.to_contract()

    def get(self, run_id: str) -> Optional[ReportRunV1]:
        """获取报告运行记录"""
        db_run = self.db.get(ReportRunV1DB, run_id)
        if db_run:
            return db_run.to_contract()
        return None

    def update(self, run: ReportRunV1) -> Optional[ReportRunV1]:
        """更新报告运行记录"""
        db_run = self.db.get(ReportRunV1DB, run.run_id)
        if not db_run:
            return None

        db_run.status = run.status
        db_run.config = run.config
        db_run.document_ids = run.document_ids
        db_run.signal_ids = run.signal_ids
        db_run.output_path = run.output_path
        db_run.error_log = run.error_log
        db_run.started_at = run.started_at
        db_run.completed_at = run.completed_at

        self.db.commit()
        self.db.refresh(db_run)
        return db_run.to_contract()

    def list_by_report_type(self, report_type: str, limit: int = 50) -> List[ReportRunV1]:
        """按报告类型列出运行记录"""
        stmt = (
            select(ReportRunV1DB)
            .where(ReportRunV1DB.report_type == report_type)
            .order_by(desc(ReportRunV1DB.created_at))
            .limit(limit)
        )
        results = self.db.execute(stmt).scalars().all()
        return [r.to_contract() for r in results]


# =============================================================================
# Helper: Get All Repositories
# =============================================================================


def get_v1_document_repositories(db: Session) -> Dict[str, Any]:
    """获取所有 v1 文档相关的 Repository"""
    return {
        "document": DocumentV1Repository(db),
        "chunk": DocumentChunkV1Repository(db),
        "tag": DocumentTagV1Repository(db),
        "summary": DocumentSummaryV1Repository(db),
        "entity_mention": EntityMentionV1Repository(db),
        "document_event": DocumentEventV1Repository(db),
        "crawl_run": CrawlRunV1Repository(db),
        "source_cursor": SourceCursorV1Repository(db),
        "report_run": ReportRunV1Repository(db),
    }
