"""
知识加工管道 - 深模块

对外只暴露一个主要接口：process(doc)
内部步骤是私有实现细节，不对外暴露
"""
import json as _json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.contracts import (
    Assertion,
    CanonicalEvent,
    DocumentChunkV1,
    DocumentClassification,
    DocumentEnvelope,
    DocumentTagV1,
    DocumentV1,
)
from core.observability import get_logger
from data_layer.repositories.event_repository import EventRepositoryImpl
from services.deduplication_service import DeduplicationService
from services.document_chunker import DocumentChunker
from services.document_classifier import DocumentClassifier
from services.entity_extractor import EntityExtractor
from services.event_extractor import EventExtractor, ExtractedSignalParams

if TYPE_CHECKING:
    from core.interfaces import ModelGateway

logger = get_logger(__name__)

_LONG_TEXT_THRESHOLD = 10000  # 只有超长文档才走并发路径


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
        分块 → 分类 → 实体提取 → 事件提取 → 去重 → 保存

    长文本（>1000字符）且有 ModelGateway 时自动走并发 chunk 提取路径。
    """

    def __init__(
        self,
        event_repo: Optional[EventRepositoryImpl] = None,
        config: Optional[PipelineConfig] = None,
        model_gateway: Optional["ModelGateway"] = None,
    ):
        self.config = config or PipelineConfig()
        self.event_repo = event_repo
        self._model_gateway = model_gateway

        # 内部处理器（私有，无状态，可跨 item 复用）
        self._chunker = DocumentChunker()
        self._classifier = DocumentClassifier()
        self._entity_extractor = EntityExtractor()
        self._event_extractor = EventExtractor(model_gateway)
        self._deduplicator = DeduplicationService()

    async def process(self, doc: DocumentV1) -> PipelineResult:
        """
        处理单个文档，运行完整知识加工管道

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

        # 判断是否走长文本并发提取路径
        use_concurrent = (
            self._model_gateway is not None
            and self.config.enable_event_extraction
            and len(doc.content) > _LONG_TEXT_THRESHOLD
        )

        if use_concurrent:
            # 长文本路径：并发 chunk 提取断言+事件
            logger.info(
                "Using concurrent extraction for long document",
                doc_id=doc.doc_id,
                content_length=len(doc.content),
            )
            text_chunks = [c.content for c in chunks] if chunks else [doc.content]
            events = self._extract_concurrent(text_chunks, doc.doc_id)
            # 并发提取已包含实体信息，跳过独立实体提取
            if self.config.enable_entity_extraction:
                entity_mentions = self._entity_extractor.extract(doc)
                entities = [e.model_dump() for e in entity_mentions]
        else:
            # 短文本路径：原有流程
            # 步骤3: 实体提取
            if self.config.enable_entity_extraction:
                entity_mentions = self._entity_extractor.extract(doc)
                entities = [e.model_dump() for e in entity_mentions]
                logger.debug(f"Extracted {len(entities)} entities")

            # 步骤4: 事件提取（单次 LLM 或关键词 fallback）
            if self.config.enable_event_extraction:
                params = await self._event_extractor.extract(doc.content)
                event = self._params_to_event(params, doc)
                events = [event]
                logger.debug(f"Extracted event: {event.event_id}")

        # 步骤5: 去重检测
        if self.config.enable_deduplication:
            dedup_result = self._deduplicator.check_duplicate(doc)
            is_duplicate = dedup_result.is_duplicate
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

        logger.info(
            f"Knowledge pipeline completed for {doc.doc_id}, "
            f"extracted {len(events)} events, "
            f"duplicate: {is_duplicate}"
        )

        return result

    def _extract_concurrent(
        self,
        text_chunks: List[str],
        doc_id: str,
    ) -> List[CanonicalEvent]:
        """长文本并发提取：对 chunk 列表并发调用 LLM 提取事件"""
        from core.settings.config import settings
        from knowledge_layer.extraction import ConcurrentLLMExtractor, split_text

        # 如果只有1个chunk且够短，不要再次 split
        if len(text_chunks) == 1 and len(text_chunks[0]) <= settings.LLM_EXTRACT_CHUNK_SIZE:
            final_chunks = text_chunks
        elif len(text_chunks) == 1:
            final_chunks = split_text(
                text_chunks[0],
                chunk_size=settings.LLM_EXTRACT_CHUNK_SIZE,
                overlap=settings.LLM_EXTRACT_CHUNK_OVERLAP,
            )
        else:
            final_chunks = text_chunks

        extractor = ConcurrentLLMExtractor(
            model_gateway=self._model_gateway,
            build_assertion_fn=self._build_concurrent_assertion,
            build_event_fn=self._build_concurrent_event,
            parse_response_fn=self._parse_concurrent_response,
            max_workers=settings.LLM_EXTRACT_MAX_WORKERS,
            max_retries=settings.LLM_EXTRACT_MAX_RETRIES,
            task="extraction",
        )

        _assertions, events, stats = extractor.extract_chunks(final_chunks, doc_id)

        logger.info(
            "Concurrent extraction completed",
            doc_id=doc_id,
            chunk_count=len(final_chunks),
            event_count=len(events),
            stats=stats,
        )

        return events

    # ── concurrent extraction helpers ──────────────────────────

    @staticmethod
    def _parse_concurrent_response(content: str) -> Dict[str, Any]:
        """解析 LLM JSON 响应"""
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            return {"assertions": [], "events": []}
        return _json.loads(content[json_start:json_end])

    @staticmethod
    def _build_concurrent_assertion(
        data: Dict[str, Any],
        doc_id: str,
        chunk_index: int | None = None,
    ) -> Optional[Any]:
        """从并发提取数据构建 Assertion（轻量版）"""
        try:
            source_span: dict = {"extracted": data}
            if chunk_index is not None:
                source_span["chunk_index"] = chunk_index

            return Assertion(
                assertion_id=str(uuid.uuid4()),
                subject_entity_id=None,
                predicate=data.get("predicate", ""),
                object_entity_id=None,
                object_value={"text": data.get("object"), "value": data.get("value")},
                observed_at=None,
                confidence=float(data.get("confidence", 0.7)),
                source_doc_id=doc_id,
                source_span=source_span,
                extractor_version="concurrent_v1.0",
                reviewer_status="draft",
            )
        except Exception:
            return None

    @staticmethod
    def _build_concurrent_event(
        data: Dict[str, Any],
        doc_id: str,
        chunk_index: int | None = None,
    ) -> Optional[CanonicalEvent]:
        """从并发提取数据构建 CanonicalEvent（轻量版）"""
        try:
            evidence_spans: list[dict] = [{"text": data.get("evidence", "")[:300]}]
            if chunk_index is not None:
                evidence_spans[0]["chunk_index"] = chunk_index

            return CanonicalEvent(
                event_id=str(uuid.uuid4()),
                event_type=data.get("event_type", "other"),
                summary=(data.get("summary") or "")[:200],
                event_time=None,
                impact_direction=data.get("impact_direction", "unknown"),
                confidence=float(data.get("confidence", 0.7)),
                needs_review=data.get("confidence", 0.7) < 0.8,
                entities=[],
                assertions=[],
                evidence_spans=evidence_spans,
                source_doc_id=doc_id,
            )
        except Exception:
            return None

    def _params_to_event(self, params: ExtractedSignalParams, doc: DocumentV1) -> CanonicalEvent:
        """将 ExtractedSignalParams 转换为 CanonicalEvent"""
        return CanonicalEvent(
            event_id=str(uuid.uuid4()),
            event_type=params.event_type,
            event_time=doc.timeliness.publish_time if doc.timeliness else None,
            source_type=doc.source_type.value
            if hasattr(doc.source_type, "value")
            else str(doc.source_type),
            source_name=doc.source_name or "unknown",
            title=doc.title or "",
            raw_text=doc.content,
            impacted_symbols=params.subject_ids,
            confidence=params.confidence,
            summary=params.thesis,
            source_doc_id=doc.doc_id,
        )

    async def process_envelope(self, envelope: DocumentEnvelope) -> PipelineResult:
        """
        处理文档信封（方便方法）

        Args:
            envelope: DocumentEnvelope 对象

        Returns:
            PipelineResult: 处理结果
        """
        return await self.process(envelope.document)
