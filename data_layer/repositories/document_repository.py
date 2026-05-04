from typing import List, Optional

from core.contracts import DocumentEnvelope
from core.interfaces import DocumentRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import SourceDocument as SourceDocumentModel

logger = get_logger(__name__)


class DocumentRepositoryImpl(BaseRepository, DocumentRepository):
    """文档仓储实现"""

    def _to_domain(self, model: SourceDocumentModel) -> DocumentEnvelope:
        """转换为领域模型"""
        return DocumentEnvelope(
            doc_id=model.doc_id,
            source_type=model.source_type,
            title=model.title or "",
            published_at=model.published_at,
            source_name=model.source_name,
            language=model.metadata.get("language", "zh"),
            metadata=model.metadata,
            raw_text=model.metadata.get("raw_text", ""),
            canonical_text=model.metadata.get("canonical_text", ""),
        )

    def _to_model(self, domain: DocumentEnvelope) -> SourceDocumentModel:
        """转换为数据库模型"""
        return SourceDocumentModel(
            doc_id=domain.doc_id,
            source_type=domain.source_type,
            title=domain.title,
            published_at=domain.published_at,
            source_name=domain.source_name,
            content_hash=domain.metadata.get("content_hash", ""),
            parser_version=domain.metadata.get("parser_version", "1.0"),
            object_uri=domain.metadata.get("object_uri", ""),
            metadata={
                **domain.metadata,
                "language": domain.language,
                "raw_text": domain.raw_text,
                "canonical_text": domain.canonical_text,
            },
        )

    def save(self, entity: DocumentEnvelope) -> DocumentEnvelope:
        """保存文档"""
        model = self.db.query(SourceDocumentModel).filter_by(doc_id=entity.doc_id).first()
        if model:
            model.source_type = entity.source_type
            model.title = entity.title
            model.published_at = entity.published_at
            model.source_name = entity.source_name
            model.metadata = {
                **entity.metadata,
                "language": entity.language,
                "raw_text": entity.raw_text,
                "canonical_text": entity.canonical_text,
            }
        else:
            model = self._to_model(entity)
            self.db.add(model)
        self.db.flush()
        logger.debug("document saved", doc_id=entity.doc_id)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[DocumentEnvelope]:
        """根据 ID 获取文档"""
        model = self.db.query(SourceDocumentModel).filter_by(doc_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[DocumentEnvelope]:
        """列出文档"""
        models = self.db.query(SourceDocumentModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除文档"""
        count = self.db.query(SourceDocumentModel).filter_by(doc_id=id).delete()
        return count > 0

    def get_by_source(self, source_type: str, source_name: str) -> List[DocumentEnvelope]:
        """根据来源获取文档"""
        models = (
            self.db.query(SourceDocumentModel)
            .filter_by(source_type=source_type, source_name=source_name)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def vector_search(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[DocumentEnvelope]:
        """向量搜索文档"""
        # 简单实现，实际使用需要 pgvector 的向量搜索
        models = self.db.query(SourceDocumentModel).limit(limit).all()
        return [self._to_domain(m) for m in models]
