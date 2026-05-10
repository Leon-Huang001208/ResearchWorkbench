"""
知识加工管道 - 深模块

对外只暴露一个主要接口：process(doc)
内部步骤是私有实现细节，不对外暴露
"""
from dataclasses import dataclass
from typing import List, Optional

from core.contracts import (
    CanonicalEvent,
    DocumentChunkV1,
    DocumentClassification,
    DocumentEnvelope,
    DocumentTagV1,
    DocumentV1,
)
from core.observability import get_logger
from core.services.document_chunker import DocumentChunker
from core.services.document_classifier import DocumentClassifier
from core.services.deduplication_service import DeduplicationService
from core.services.entity_extractor import EntityExtractor
from core.services.event_extractor import EventExtractor
from data_layer.repositories.event_repository import EventRepositoryImpl

logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """知识加工管道配置"""

    enable_chunker: bool = True
    enable_classifier: bool = True
    enable_entity_extraction: bool = True
    enable_event_extraction: bool = True
    enable_deduplication: bool = True
    auto_save: bool = True


@dataclass
class PipelineResult:
    """知识加工管道结果"""

    document: DocumentV1
    chunks: List[DocumentChunkV1]
    classification: Optional[DocumentClassification]
    tags: List[DocumentTagV1]
    entities: List[dict]
    events: List[CanonicalEvent]
    is_duplicate: bool = False


class KnowledgePipeline:
    """
    知识加工管道 - 深模块

    对外只暴露 process() 这一个主要方法
    内部步骤是私有实现细节：
        分块 → 分类 → 实体提取 → 事件提取 → 丰富 → 去重 → 保存
    """

    def __init__(
        self,
        event_repo: Optional[EventRepositoryImpl] = None,
        config: Optional[PipelineConfig] = None,
    ):
        self.config = config or PipelineConfig()
        self.event_repo = event_repo

        # 内部处理器（私有）
        self._chunker = DocumentChunker()
        self._classifier = DocumentClassifier()
        self._entity_extractor = EntityExtractor()
        self._event_extractor = EventExtractor()
        self._deduplicator = DeduplicationService()

    def process(self, doc: DocumentV1) -> PipelineResult:
        """
        处理单个文档，运行完整知识加工管道

        这是对外暴露的唯一主要方法

        Args:
            doc: 要处理的文档

        Returns:
            PipelineResult: 包含所有处理结果的对象
        """
        logger.info(f"Starting knowledge pipeline for document: {doc.doc_id}")

        chunks: List[DocumentChunkV1] = []
        classification: Optional[DocumentClassification] = None
        tags: List[DocumentTagV1] = []
        entities: List[dict] = []
        events: List[CanonicalEvent] = []
        is_duplicate = False

        # 步骤1: 文档分块
        if self.config.enable_chunker:
            chunks = self._chunker.chunk_document(doc)
            logger.debug(f"Document chunked into {len(chunks)} chunks")

        # 步骤2: 文档分类
        if self.config.enable_classifier:
            classification, tags = self._classifier.classify(doc)
            logger.debug(f"Document classified with {len(tags)} tags")

        # 步骤3: 实体提取
        if self.config.enable_entity_extraction:
            entities = self._entity_extractor.extract_entities(doc.content)
            logger.debug(f"Extracted {len(entities)} entities")

        # 步骤4: 事件提取
        if self.config.enable_event_extraction:
            events = self._event_extractor.extract_from_document(doc)
            logger.debug(f"Extracted {len(events)} events")

        # 步骤5: 去重检测
        if self.config.enable_deduplication:
            is_duplicate = self._deduplicator.is_duplicate(doc)
            if is_duplicate:
                logger.info(f"Document {doc.doc_id} is duplicate, skipping save")

        # 步骤6: 自动保存（如果启用且非重复）
        if self.config.auto_save and not is_duplicate and self.event_repo:
            for event in events:
                try:
                    self.event_repo.save(event)
                    logger.debug(f"Saved event: {event.event_id}")
                except Exception as e:
                    logger.error(f"Failed to save event {event.event_id}: {e}")

        result = PipelineResult(
            document=doc,
            chunks=chunks,
            classification=classification,
            tags=tags,
            entities=entities,
            events=events,
            is_duplicate=is_duplicate,
        )

        logger.info(f"Knowledge pipeline completed for {doc.doc_id}, "
                   f"extracted {len(events)} events, "
                   f"duplicate: {is_duplicate}")

        return result

    def process_envelope(self, envelope: DocumentEnvelope) -> PipelineResult:
        """
        处理文档信封（方便方法）

        Args:
            envelope: DocumentEnvelope 对象

        Returns:
            PipelineResult: 处理结果
        """
        return self.process(envelope.document)
