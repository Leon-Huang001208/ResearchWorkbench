"""
PDF 转换服务 —— 核心编排逻辑.

负责管理 PDF 到 Markdown/文本的转换流程，包括策略选择、状态流转和结果持久化。
"""
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.contracts.documents_v1 import (
    DocType,
    DocumentProcessingMeta,
    DocumentProcessingStatus,
    DocumentV1,
    SourceType,
)
from core.contracts.pdf_conversion import ConversionResult, ConversionStatus, StrategyType
from core.observability import get_logger
from data_layer.repositories import pdf_artifact_repository as pdf_repo
from data_layer.repositories.documents_v1 import DocumentChunkV1Repository, DocumentV1Repository
from data_layer.repositories.models import PDFArtifactV1DB, PDFConversionV1DB
from ingestion.converters.base import PDFConversionStrategy
from ingestion.converters.markitdown import MarkItDownStrategy
from ingestion.converters.mineru import MinerUStrategy
from ingestion.converters.persistence import persist_markdown, persist_raw_text, should_inline
from ingestion.converters.raw_text import RawTextStrategy
from services.document_chunker import DocumentChunker

logger = get_logger(__name__)


class PDFConversionService:
    """PDF 转换预案服务

    负责：
    - 策略自动选择（mineru → markitdown → raw_text）
    - 状态流转（pending → running → success/error）
    - 结果持久化到 pdf_conversion_v1 表
    - PDFArtifact.parse_status 同步
    - 转换后自动创建 DocumentV1 和分块
    """

    # 策略优先级（从高到低）
    STRATEGY_PRIORITY: List[StrategyType] = [
        StrategyType.MINERU,
        StrategyType.MARKITDOWN,
        StrategyType.RAW_TEXT,
    ]

    def __init__(self, db: Session, create_document: bool = True):
        self._db = db
        self._strategies: Dict[str, PDFConversionStrategy] = {}
        self._create_document = create_document
        self._chunker = DocumentChunker() if create_document else None
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """注册所有可用的转换策略"""
        strategies: list[PDFConversionStrategy] = [
            MinerUStrategy(),
            MarkItDownStrategy(),
            RawTextStrategy(),
        ]
        for s in strategies:
            self._strategies[s.name] = s
            logger.debug(f"注册 PDF 转换策略: {s.name} (可用: {s.is_available()})")

    def get_available_strategies(self) -> list[str]:
        """获取当前可用的策略列表"""
        return [name for name, s in self._strategies.items() if s.is_available()]

    def _select_strategy(
        self, preferred: Optional[StrategyType] = None
    ) -> Optional[PDFConversionStrategy]:
        """选择转换策略

        优先使用 preferred，不可用时按优先级列表自动选择。
        """
        if preferred and preferred != StrategyType.AUTO:
            strategy = self._strategies.get(preferred.value)
            if strategy and strategy.is_available():
                return strategy
            logger.warning(f"首选策略不可用: {preferred.value}，自动选择")

        # 按优先级尝试
        for st in self.STRATEGY_PRIORITY:
            strategy = self._strategies.get(st.value)
            if strategy and strategy.is_available():
                return strategy

        return None

    def _ordered_strategies(
        self, preferred: Optional[StrategyType] = None
    ) -> List[PDFConversionStrategy]:
        """按降级顺序返回可用策略。

        AUTO 模式会按优先级逐个尝试；显式指定策略时只尝试指定策略。
        """
        if preferred and preferred != StrategyType.AUTO:
            strategy_name = preferred.value if hasattr(preferred, "value") else str(preferred)
            strategy = self._strategies.get(strategy_name)
            if strategy and strategy.is_available():
                return [strategy]
            logger.warning(f"首选策略不可用: {strategy_name}")
            return []

        ordered: List[PDFConversionStrategy] = []
        seen: set[str] = set()
        for st in self.STRATEGY_PRIORITY:
            strategy = self._strategies.get(st.value)
            if strategy and strategy.name not in seen and strategy.is_available():
                ordered.append(strategy)
                seen.add(strategy.name)
        return ordered

    def convert_pdf(
        self,
        pdf_id: str,
        preferred_strategy: Optional[StrategyType] = None,
    ) -> ConversionResult:
        """转换单个 PDF

        Args:
            pdf_id: PDF 制品 ID
            preferred_strategy: 首选策略（None 或 AUTO 则自动选择）

        Returns:
            ConversionResult: 转换结果
        """
        # 1. 查找 PDF artifact
        artifact = pdf_repo.get_pdf_by_id(self._db, pdf_id)
        if not artifact:
            return ConversionResult(
                success=False,
                strategy_used="",
                error_message=f"PDF artifact 不存在: {pdf_id}",
            )

        # 2. 选择策略；AUTO 模式下按优先级降级尝试。
        strategies = self._ordered_strategies(preferred_strategy)
        if not strategies:
            return ConversionResult(
                success=False,
                strategy_used="",
                error_message="没有可用的转换策略",
            )

        last_result: Optional[ConversionResult] = None
        errors: list[str] = []

        for strategy in strategies:
            # 3. 创建转换记录并标记为 running
            conversion = PDFConversionV1DB(
                conversion_id=f"conv_{uuid.uuid4().hex[:12]}",
                pdf_id=pdf_id,
                conversion_strategy=strategy.name,
                status=ConversionStatus.RUNNING.value,
                created_at=datetime.now(timezone.utc),
            )
            pdf_repo.add_conversion(self._db, conversion)

            # 同步 PDF artifact 状态
            artifact.parse_status = ConversionStatus.RUNNING.value
            self._db.commit()

            # 4. 执行转换
            start_time = time.time()
            try:
                result = strategy.convert(str(artifact.file_path))
            except Exception as e:
                result = ConversionResult(
                    success=False,
                    strategy_used=strategy.name,
                    error_message=str(e),
                )

            duration_ms = int((time.time() - start_time) * 1000)
            has_content = bool((result.markdown or result.raw_text or "").strip())
            if result.success and not has_content:
                result = ConversionResult(
                    success=False,
                    strategy_used=strategy.name,
                    error_message=f"{strategy.name} 输出为空",
                )
            last_result = result

            # 5. 持久化输出到磁盘
            if result.success:
                if result.markdown:
                    conversion.markdown_path = persist_markdown(pdf_id, result.markdown)
                    if should_inline(result.markdown):
                        conversion.markdown_content = result.markdown
                if result.raw_text:
                    conversion.raw_text_path = persist_raw_text(pdf_id, result.raw_text)
                    if should_inline(result.raw_text):
                        conversion.raw_text_content = result.raw_text

            # 更新为错误状态
            conversion.status = (
                ConversionStatus.SUCCESS.value if result.success else ConversionStatus.ERROR.value
            )
            conversion.page_count = result.page_count
            conversion.token_count = result.token_count
            conversion.quality_score = result.quality_score
            conversion.has_tables = result.has_tables
            conversion.has_images = result.has_images
            conversion.has_code_blocks = result.has_code_blocks
            conversion.conversion_duration_ms = duration_ms
            if not result.success:
                conversion.error_log = result.error_message
            conversion.completed_at = datetime.now(timezone.utc)

            # 同步 artifact 状态
            artifact.parse_status = conversion.status
            artifact.parsed_at = conversion.completed_at
            if result.metadata:
                existing_meta = dict(artifact.pdf_metadata or {})
                existing_meta.update(result.metadata)
                artifact.pdf_metadata = existing_meta

            self._db.commit()

            logger.info(
                f"PDF 转换完成: {pdf_id} -> {strategy.name} "
                f"(success={result.success}, duration={duration_ms}ms)"
            )

            if not result.success:
                errors.append(f"{strategy.name}: {result.error_message}")
                logger.warning(
                    "PDF 转换策略失败，尝试下一个可用策略",
                    extra={
                        "pdf_id": pdf_id,
                        "strategy": strategy.name,
                        "error": result.error_message,
                    },
                )
                continue

            # 7. 转换成功后自动创建 DocumentV1 和分块
            if self._create_document:
                try:
                    self._create_document_from_conversion(artifact, conversion, result)
                except Exception as e:
                    logger.error(
                        f"创建 DocumentV1 失败 (pdf_id={pdf_id}): {e}",
                        exc_info=True,
                    )
                    # 记录到 conversion，使运维可发现
                    conversion.error_log = (
                        f"PDF conversion succeeded but DocumentV1 creation failed: {e}"
                    )
                    self._db.commit()

            return result

        if last_result:
            last_result.error_message = "; ".join(errors) or last_result.error_message
            return last_result

        return ConversionResult(
            success=False,
            strategy_used="",
            error_message="没有可用的转换策略",
        )

    def _create_document_from_conversion(
        self,
        artifact: PDFArtifactV1DB,
        conversion: PDFConversionV1DB,
        result: ConversionResult,
    ) -> None:
        """从转换结果创建 DocumentV1 和分块

        仅在转换成功时调用。
        """
        content = result.markdown or result.raw_text
        if not content:
            return

        doc_repo = DocumentV1Repository(self._db)
        chunk_repo = DocumentChunkV1Repository(self._db)

        # 计算内容哈希用于去重
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # 检查是否已存在
        existing = doc_repo.get_by_content_hash(content_hash)
        if existing:
            logger.info(f"DocumentV1 已存在 (content_hash={content_hash[:12]}), 跳过创建")
            return

        # 确定文档类型
        doc_type = DocType.REPORT
        source_type = _map_source_type(str(artifact.source_type))

        # 创建 DocumentV1
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        title = artifact.file_name or f"PDF Document {artifact.pdf_id}"

        # 从 artifact metadata 提取标题
        if artifact.pdf_metadata:
            meta_title = artifact.pdf_metadata.get("title") or artifact.pdf_metadata.get("Title")
            if meta_title:
                title = str(meta_title)

        doc = DocumentV1(
            doc_id=doc_id,
            doc_type=doc_type,
            source_type=source_type,
            title=title,
            content=content,
            doc_metadata={
                "pdf_id": artifact.pdf_id,
                "conversion_id": conversion.conversion_id,
                "conversion_strategy": conversion.conversion_strategy,
                "page_count": result.page_count,
                "quality_score": result.quality_score,
                "has_tables": result.has_tables,
                "has_images": result.has_images,
                "file_path": artifact.file_path,
            },
            source_metadata={
                "source_type": artifact.source_type,
                "source_name": artifact.source_name,
                "source_url": artifact.source_url,
                "source_broker": artifact.source_broker,
                "source_author": artifact.source_author,
            },
            processing=DocumentProcessingMeta(
                status=DocumentProcessingStatus.CHUNKED,
                parse_version=artifact.parse_version or "1.0",
            ),
            source_name=artifact.source_name,
            source_url=artifact.source_url,
            content_hash=content_hash,
        )

        doc_repo.create(doc)
        logger.info(f"DocumentV1 已创建: {doc_id} (pdf_id={artifact.pdf_id})")

        # 送入摄取队列，由 KnowledgePipeline 做 LLM 提取（实体、事件等）
        self._enqueue_document(doc)

        # 创建分块
        assert self._chunker is not None
        chunks = self._chunker.chunk_document(doc)

        # 在 chunk metadata 中添加 PDF 信息
        for chunk in chunks:
            chunk.metadata["pdf_id"] = artifact.pdf_id
            chunk.metadata["conversion_id"] = conversion.conversion_id

        if chunks:
            chunk_repo.bulk_create(chunks)
            logger.info(f"已创建 {len(chunks)} 个分块 (doc_id={doc_id})")

    @staticmethod
    def _enqueue_document(doc: DocumentV1) -> None:
        """将 DocumentV1 送入摄取队列，由 KnowledgePipeline 做 LLM 提取"""
        try:
            from services.crawl_orchestrator import CrawlOrchestrator

            source_type_str = (
                doc.source_type.value if hasattr(doc.source_type, "value") else str(doc.source_type)
            )
            published_at = None
            if doc.timeliness and doc.timeliness.publish_time:
                pt = doc.timeliness.publish_time
                published_at = pt.isoformat() if hasattr(pt, "isoformat") else str(pt)

            CrawlOrchestrator._enqueue_items(
                source_type_str,
                [
                    {
                        "id": doc.doc_id,
                        "title": doc.title,
                        "content": doc.content,
                        "url": doc.source_url,
                        "published_at": published_at,
                        "source_name": doc.source_name,
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Failed to enqueue document {doc.doc_id}: {e}", exc_info=True)

    def convert_pending(self, limit: int = 10) -> List[ConversionResult]:
        """批量转换所有 pending 的 PDF

        Args:
            limit: 每次批量处理的最大数量

        Returns:
            List[ConversionResult]: 每个 PDF 的转换结果列表
        """
        results: List[ConversionResult] = []

        # 查找所有 parse_status=pending 的 PDF artifacts
        pending_artifacts = (
            self._db.query(PDFArtifactV1DB)
            .filter(PDFArtifactV1DB.parse_status == "pending")
            .order_by(PDFArtifactV1DB.created_at.asc())
            .limit(limit)
            .all()
        )

        if not pending_artifacts:
            logger.debug("没有待转换的 PDF")
            return results

        logger.info(f"开始批量转换 {len(pending_artifacts)} 个 PDF")

        for artifact in pending_artifacts:
            try:
                result = self.convert_pdf(str(artifact.pdf_id))
                results.append(result)
            except Exception as e:
                logger.error(f"批量转换中出错: {artifact.pdf_id}: {e}")
                results.append(
                    ConversionResult(
                        success=False,
                        strategy_used="",
                        error_message=str(e),
                    )
                )

        success_count = sum(1 for r in results if r.success)
        logger.info(f"批量转换完成: {success_count}/{len(results)} 成功")

        return results

    def retry_failed(self, limit: int = 10) -> List[ConversionResult]:
        """重试所有失败的转换

        Args:
            limit: 每次重试的最大数量

        Returns:
            List[ConversionResult]: 每个重试结果
        """
        results: List[ConversionResult] = []

        failed_artifacts = (
            self._db.query(PDFArtifactV1DB)
            .filter(PDFArtifactV1DB.parse_status == "error")
            .order_by(PDFArtifactV1DB.created_at.asc())
            .limit(limit)
            .all()
        )

        if not failed_artifacts:
            logger.debug("没有需要重试的 PDF")
            return results

        logger.info(f"开始重试 {len(failed_artifacts)} 个失败的 PDF 转换")

        for artifact in failed_artifacts:
            try:
                # 重置状态为 pending 然后重新转换
                artifact.parse_status = "pending"
                self._db.commit()
                result = self.convert_pdf(str(artifact.pdf_id))
                results.append(result)
            except Exception as e:
                logger.error(f"重试转换时出错: {artifact.pdf_id}: {e}")
                results.append(
                    ConversionResult(
                        success=False,
                        strategy_used="",
                        error_message=str(e),
                    )
                )

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取转换统计信息"""
        return pdf_repo.get_conversion_stats(self._db)

    def get_pending(self, limit: int = 50) -> list[PDFArtifactV1DB]:
        """获取待转换列表"""
        return (
            self._db.query(PDFArtifactV1DB)
            .filter(PDFArtifactV1DB.parse_status == "pending")
            .order_by(PDFArtifactV1DB.created_at.asc())
            .limit(limit)
            .all()
        )


def _map_source_type(source_type: str) -> SourceType:
    """将 artifact 的 source_type 字符串映射到 SourceType 枚举"""
    # 从注册表自动构建映射（SourceType value → SourceType）
    from core.source_registry import get_all as _get_all_specs

    type_map: Dict[str, SourceType] = {}
    for spec in _get_all_specs():
        type_map[spec.source_type.value] = spec.source_type

    # 历史别名（不在注册表中的遗留映射）
    type_map.update(
        {
            "zhiqiu": SourceType.ZHIQIU_REPORTS,
            "east_money": SourceType.EAST_MONEY,
            "sina_finance": SourceType.SINA_FINANCE,
        }
    )
    return type_map.get(source_type, SourceType.OTHER)
