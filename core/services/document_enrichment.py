"""
文档富集流水线 - Issue #44

整合所有富集步骤：
1. 文档解析
2. 分块
3. 分类
4. 实体提取
5. 事件提取
6. 总结生成
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from core.contracts import (
    DocumentChunkV1,
    DocumentEventV1,
    DocumentProcessingMeta,
    DocumentProcessingStatus,
    DocumentSummaryV1,
    DocumentTagV1,
    DocumentV1,
    EntityMentionV1,
)
from core.observability import get_logger
from core.services.document_chunker import ChunkingOptions, DocumentChunker
from core.services.document_classifier import DocumentClassifier
from core.services.entity_extractor import EntityExtractor
from core.services.event_extractor import EventExtractor
from core.services.summary_generator import SummaryGenerator
from core.services.taxonomy_service import TaxonomyService

logger = get_logger(__name__)


@dataclass
class EnrichmentResult:
    """富集结果"""

    doc: DocumentV1
    chunks: List[DocumentChunkV1]
    tags: List[DocumentTagV1]
    summary: Optional[DocumentSummaryV1]
    entities: List[EntityMentionV1]
    events: List[DocumentEventV1]
    success: bool = True
    errors: List[str] = None


@dataclass
class EnrichmentConfig:
    """富集配置"""

    # 开关
    do_chunking: bool = True
    do_classification: bool = True
    do_entity_extraction: bool = True
    do_event_extraction: bool = True
    do_summary: bool = True

    # 选项
    chunk_options: Optional[ChunkingOptions] = None


class DocumentEnrichmentPipeline:
    """文档富集流水线"""

    def __init__(
        self,
        config: Optional[EnrichmentConfig] = None,
        chunker: Optional[DocumentChunker] = None,
        classifier: Optional[DocumentClassifier] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        event_extractor: Optional[EventExtractor] = None,
        summary_generator: Optional[SummaryGenerator] = None,
        taxonomy: Optional[TaxonomyService] = None,
    ):
        self.config = config or EnrichmentConfig()
        self.taxonomy = taxonomy or TaxonomyService()
        self.chunker = chunker or DocumentChunker(self.config.chunk_options)
        self.classifier = classifier or DocumentClassifier(self.taxonomy)
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.event_extractor = event_extractor
        self.summary_generator = summary_generator or SummaryGenerator()

    def enrich(self, doc: DocumentV1, update_doc: bool = True) -> EnrichmentResult:
        """
        执行完整的富集流程

        Args:
            doc: 文档
            update_doc: 是否更新文档对象

        Returns:
            富集结果
        """
        logger.info(f"Starting enrichment for document: {doc.doc_id}")

        result = EnrichmentResult(
            doc=doc,
            chunks=[],
            tags=[],
            summary=None,
            entities=[],
            events=[],
            errors=[],
        )

        # 更新处理状态
        if update_doc:
            if not doc.processing:
                doc.processing = DocumentProcessingMeta()
            doc.processing.status = DocumentProcessingStatus.PARSED
            doc.processing.processing_started_at = datetime.utcnow()

        # 1. 分块
        if self.config.do_chunking:
            try:
                result.chunks = self.chunker.chunk_document(doc)
                if update_doc:
                    doc.processing.status = DocumentProcessingStatus.CHUNKED
                    doc.processing.chunker_version = "v1.0"
                logger.info(f"Chunked into {len(result.chunks)} chunks")
            except Exception as e:
                logger.error(f"Chunking failed: {e}")
                result.errors.append(f"Chunking failed: {e}")

        # 2. 分类
        if self.config.do_classification:
            try:
                classification, tags = self.classifier.classify(doc, update_doc=update_doc)
                result.tags = tags

                # 同时分析质量和证据概况
                self.classifier.analyze_quality(doc, update_doc=update_doc)
                self.classifier.analyze_evidence(doc, update_doc=update_doc)

                if update_doc:
                    doc.processing.status = DocumentProcessingStatus.CLASSIFIED
                    doc.processing.classifier_version = "v1.0"

                logger.info(f"Classified with {len(tags)} tags")
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                result.errors.append(f"Classification failed: {e}")

        # 3. 实体提取
        if self.config.do_entity_extraction:
            try:
                result.entities = self.entity_extractor.extract(doc)
                logger.info(f"Extracted {len(result.entities)} entities")
            except Exception as e:
                logger.error(f"Entity extraction failed: {e}")
                result.errors.append(f"Entity extraction failed: {e}")

        # 4. 事件提取
        if self.config.do_event_extraction and self.event_extractor:
            try:
                # 这里我们从事件提取器转换到 DocumentEventV1
                # 注意：当前的 EventExtractor 是为了提取 AlphaSignal 参数设计的
                # 我们需要做一些适配

                # 简单的事件提取适配
                # 实际项目中应该有专门的 DocumentEvent 提取器
                text_for_extraction = doc.title + "\n" + doc.content
                extracted = self.event_extractor.extract(text_for_extraction)

                # 转换为 DocumentEventV1
                event = DocumentEventV1(
                    event_id=doc.doc_id + "_event",
                    doc_id=doc.doc_id,
                    canonical_event_id=None,
                    event_type=extracted.event_type,
                    event_time=doc.timeliness.event_time if doc.timeliness else None,
                    subject_entity=extracted.subject_ids[0] if extracted.subject_ids else None,
                    object_entity=None,
                    event_summary=extracted.thesis,
                    impact_direction=extracted.impact_path[0] if extracted.impact_path else None,
                    evidence_text=doc.content[:500],
                    confidence=extracted.confidence,
                    extra={
                        "bullish_companies": extracted.bullish_companies,
                        "bearish_companies": extracted.bearish_companies,
                        "industry_impacts": extracted.industry_impacts,
                    },
                )
                result.events = [event]

                logger.info(f"Extracted {len(result.events)} events")
            except Exception as e:
                logger.error(f"Event extraction failed: {e}")
                result.errors.append(f"Event extraction failed: {e}")

        # 5. 总结生成
        if self.config.do_summary:
            try:
                result.summary = self.summary_generator.generate_document_summary(doc)

                if update_doc and not doc.summary:
                    doc.summary = result.summary.summary

                if update_doc:
                    doc.processing.status = DocumentProcessingStatus.ENRICHED

                logger.info("Generated summary")
            except Exception as e:
                logger.error(f"Summary generation failed: {e}")
                result.errors.append(f"Summary generation failed: {e}")

        # 完成
        if update_doc:
            if not doc.processing:
                doc.processing = DocumentProcessingMeta()
            doc.processing.status = DocumentProcessingStatus.COMPLETE
            doc.processing.processing_completed_at = datetime.utcnow()

        result.success = len(result.errors) == 0

        logger.info(
            f"Enrichment complete for {doc.doc_id}: "
            f"{len(result.chunks)} chunks, "
            f"{len(result.tags)} tags, "
            f"{len(result.entities)} entities"
        )

        return result

    def enrich_batch(self, docs: List[DocumentV1]) -> Dict[str, EnrichmentResult]:
        """
        批量富集

        Args:
            docs: 文档列表

        Returns:
            {doc_id: EnrichmentResult}
        """
        results: Dict[str, EnrichmentResult] = {}

        for doc in docs:
            results[doc.doc_id] = self.enrich(doc)

        success_count = sum(1 for r in results.values() if r.success)
        logger.info(f"Batch enrichment complete: {success_count}/{len(docs)} successful")

        return results
