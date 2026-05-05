"""
摄入服务 - 文档摄入流程
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.contracts import Assertion, DocumentEnvelope
from core.interfaces import DocumentRepository, ModelGateway
from core.observability import get_logger
from knowledge_layer.assertions import AssertionExtractor, AssertionValidator, QualityGate
from knowledge_layer.events import EventExtractor, EventQualityGate
from knowledge_layer.retrieval import InMemoryVectorStore, VectorStore

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

logger = get_logger(__name__)


class IngestService:
    """摄入服务"""

    def __init__(
        self,
        document_repo: Optional[DocumentRepository] = None,
        model_gateway: Optional[ModelGateway] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self._document_repo = document_repo
        self._model_gateway = model_gateway
        self._vector_store = vector_store or InMemoryVectorStore(model_gateway)
        self._assertion_extractor = AssertionExtractor(model_gateway)
        self._assertion_validator = AssertionValidator()
        self._assertion_quality_gate = QualityGate(self._assertion_validator)
        self._event_extractor = EventExtractor(model_gateway)
        self._event_quality_gate = EventQualityGate()

    def ingest_file(
        self,
        file_path: Path,
        source_type: str = "report",
        source_name: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        摄入文件

        Args:
            file_path: 文件路径
            source_type: 来源类型
            source_name: 来源名称
            title: 标题

        Returns:
            摄入结果
        """
        logger.info(f"Ingesting file: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 读取文件
        raw_text = self._read_file(file_path)
        canonical_text = self._normalize_text(raw_text)

        # 创建文档信封
        doc_id = str(uuid.uuid4())
        doc = DocumentEnvelope(
            doc_id=doc_id,
            source_type=source_type,
            title=title or file_path.name,
            published_at=datetime.utcnow(),
            source_name=source_name or "unknown",
            language="zh",
            metadata={"file_path": str(file_path)},
            raw_text=raw_text,
            canonical_text=canonical_text,
        )

        # 提取断言
        assertions = self._assertion_extractor.extract(canonical_text, doc_id)

        # 质量门
        approved_assertions, pending_assertions = self._assertion_quality_gate.process_batch(
            assertions
        )

        # 提取事件
        events = self._event_extractor.extract(canonical_text, doc_id)

        # 质量门
        approved_events, pending_events = self._event_quality_gate.process_batch(events)

        # 索引文档
        self._vector_store.add_document(
            doc_id=doc_id,
            text=canonical_text,
            metadata={"source_type": source_type, "source_name": source_name},
        )

        # 保存文档
        if self._document_repo:
            self._document_repo.save(doc)

        result = {
            "doc_id": doc_id,
            "title": doc.title,
            "assertions_extracted": len(assertions),
            "assertions_approved": len(approved_assertions),
            "assertions_pending": len(pending_assertions),
            "events_extracted": len(events),
            "events_approved": len(approved_events),
            "events_pending": len(pending_events),
        }

        logger.info(f"Ingest completed: {result}")
        return result

    def ingest_text(
        self,
        text: str,
        source_type: str = "report",
        source_name: str = "unknown",
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        摄入文本

        Args:
            text: 文本内容
            source_type: 来源类型
            source_name: 来源名称
            title: 标题

        Returns:
            摄入结果
        """
        logger.info(f"Ingesting text from source: {source_name}, title: {title or 'Untitled'}")

        try:
            # 创建临时文件或者直接处理
            doc_id = str(uuid.uuid4())
            canonical_text = self._normalize_text(text)

            logger.debug(f"Normalized text length: {len(canonical_text)}")

            # 创建文档信封
            doc = DocumentEnvelope(
                doc_id=doc_id,
                source_type=source_type,
                title=title or "Untitled",
                published_at=datetime.utcnow(),
                source_name=source_name,
                language="zh",
                metadata={},
                raw_text=text,
                canonical_text=canonical_text,
            )

            # 提取断言
            logger.debug("Extracting assertions...")
            assertions = self._assertion_extractor.extract(canonical_text, doc_id)
            logger.debug(f"Extracted {len(assertions)} assertions")

            approved_assertions, pending_assertions = self._assertion_quality_gate.process_batch(
                assertions
            )

            # 提取事件
            logger.debug("Extracting events...")
            events = self._event_extractor.extract(canonical_text, doc_id)
            logger.debug(f"Extracted {len(events)} events")

            approved_events, pending_events = self._event_quality_gate.process_batch(events)

            # 索引文档
            logger.debug("Indexing document in vector store...")
            self._vector_store.add_document(
                doc_id=doc_id,
                text=canonical_text,
                metadata={"source_type": source_type, "source_name": source_name},
            )

            # 保存文档
            if self._document_repo:
                try:
                    self._document_repo.save(doc)
                    logger.debug(f"Document saved to repository: {doc_id}")
                except Exception as e:
                    logger.warning(f"Failed to save document to repository: {e}", exc_info=True)

            result = {
                "doc_id": doc_id,
                "title": doc.title,
                "assertions_extracted": len(assertions),
                "assertions_approved": len(approved_assertions),
                "assertions_pending": len(pending_assertions),
                "events_extracted": len(events),
                "events_approved": len(approved_events),
                "events_pending": len(pending_events),
            }

            logger.info(f"Ingest completed successfully: {result}")
            return result

        except Exception as e:
            logger.error(f"Ingest failed: {e}", exc_info=True)
            raise

    def _read_file(self, file_path: Path) -> str:
        """读取文件内容"""
        if file_path.suffix.lower() == ".pdf":
            # 简单 PDF 读取（使用 pdfplumber）
            if pdfplumber is not None:
                with pdfplumber.open(file_path) as pdf:
                    text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                    return text
            else:
                logger.warning("pdfplumber not available, reading as text")
        elif file_path.suffix.lower() in [".txt", ".md"]:
            return file_path.read_text(encoding="utf-8")

        # 默认尝试文本读取
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="gbk", errors="replace")

    def _normalize_text(self, text: str) -> str:
        """规范化文本"""
        # 简单的规范化
        text = text.strip()
        # 去除多余空白行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)
