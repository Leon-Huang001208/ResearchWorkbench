"""
摄入服务 - 文档摄入流程
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from core.contracts import Assertion, CanonicalEvent, DocumentEnvelope
from core.interfaces import DocumentRepository, ModelGateway
from core.observability import get_logger
from core.settings.config import settings
from knowledge_layer.assertions import AssertionExtractor, AssertionValidator, QualityGate
from knowledge_layer.events import EventExtractor, EventQualityGate
from knowledge_layer.extraction import ConcurrentLLMExtractor, split_text
from knowledge_layer.retrieval import InMemoryVectorStore, VectorStore

if TYPE_CHECKING:
    from core.interfaces.repository import AssertionRepository, EventRepository

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
        assertion_repo: Optional["AssertionRepository"] = None,
        event_repo: Optional["EventRepository"] = None,
    ):
        self._document_repo = document_repo
        # 自动注入 model_gateway（如果未提供且非测试环境）
        if model_gateway is None:
            import os

            _in_test = bool(os.getenv("PYTEST_CURRENT_TEST"))
            if not _in_test:
                try:
                    from core.model_gateway.gateway import ModelGatewayImpl

                    model_gateway = ModelGatewayImpl()
                    logger.info("Auto-initialized ModelGateway for IngestService")
                except Exception as e:
                    logger.warning(f"Failed to auto-init ModelGateway: {e}, using None")
                    model_gateway = None
        self._model_gateway = model_gateway
        self._vector_store = vector_store or InMemoryVectorStore(model_gateway)
        self._assertion_repo = assertion_repo
        self._event_repo = event_repo
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
        """摄入文件 —— 统一走 ingest_envelope() 管道"""
        logger.info(f"Ingesting file: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        raw_text = self._read_file(file_path)
        canonical_text = self._normalize_text(raw_text)

        envelope = DocumentEnvelope(
            doc_id=str(uuid.uuid4()),
            source_type=source_type,
            title=title or file_path.name,
            published_at=datetime.utcnow(),
            source_name=source_name or "unknown",
            language="zh",
            metadata={"file_path": str(file_path)},
            raw_text=raw_text,
            canonical_text=canonical_text,
        )

        return self.ingest_envelope(envelope)

    def ingest_text(
        self,
        text: str,
        source_type: str = "report",
        source_name: str = "unknown",
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """摄入文本 —— 统一走 ingest_envelope() 管道"""
        logger.info(f"Ingesting text from source: {source_name}, title: {title or 'Untitled'}")

        canonical_text = self._normalize_text(text)

        envelope = DocumentEnvelope(
            doc_id=str(uuid.uuid4()),
            source_type=source_type,
            title=title or "Untitled",
            published_at=datetime.utcnow(),
            source_name=source_name,
            language="zh",
            metadata={},
            raw_text=text,
            canonical_text=canonical_text,
        )

        return self.ingest_envelope(envelope)

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

    def ingest_envelope(self, envelope: DocumentEnvelope) -> Dict[str, Any]:
        """
        摄入文档信封

        Args:
            envelope: DocumentEnvelope 对象

        Returns:
            摄入结果
        """
        logger.info(f"Ingesting envelope: doc_id={envelope.doc_id}, title={envelope.title}")

        # 规范化文本
        canonical_text = self._normalize_text(envelope.canonical_text or envelope.raw_text)

        # 根据文本长度选择提取策略
        if self._model_gateway:
            threshold = settings.LLM_EXTRACT_LONG_TEXT_THRESHOLD
            if len(canonical_text) > threshold:
                # 长文本：chunk + 并发 LLM
                combined = self._extract_combined_concurrent(canonical_text, envelope.doc_id)
                assertions = combined.get("assertions", [])
                events = combined.get("events", [])
                extract_stats = combined.get("stats", {})
            else:
                # 短文本：一次 combined LLM
                combined = self._extract_combined(canonical_text, envelope.doc_id)
                assertions = combined.get("assertions", [])
                events = combined.get("events", [])
                extract_stats = {"mode": "combined_single_shot"}
        else:
            # 无 LLM：规则 fallback
            assertions = self._assertion_extractor.extract(canonical_text, envelope.doc_id)
            events = self._event_extractor.extract(canonical_text, envelope.doc_id)
            extract_stats = {"mode": "rule_fallback"}

        # 质量门
        approved_assertions, pending_assertions = self._assertion_quality_gate.process_batch(
            assertions
        )

        # 质量门
        approved_events, pending_events = self._event_quality_gate.process_batch(events)

        # 保存文档到 source_document (FIRST — FK constraints on assertion/event reference this)
        if self._document_repo:
            try:
                self._document_repo.save(envelope)
            except Exception as e:
                logger.warning(f"Failed to save document {envelope.doc_id}: {e}")

        # 保存断言到仓储
        if self._assertion_repo:
            for a in approved_assertions + pending_assertions:
                try:
                    self._assertion_repo.save(a)
                except Exception as e:
                    logger.warning(f"Failed to save assertion {a.assertion_id}: {e}")

        # 保存事件到仓储
        if self._event_repo:
            for ev in approved_events + pending_events:
                try:
                    self._event_repo.save(ev)
                except Exception as e:
                    logger.warning(f"Failed to save event {ev.event_id}: {e}")

        # 索引文档
        self._vector_store.add_document(
            doc_id=envelope.doc_id,
            text=canonical_text,
            metadata={"source_type": envelope.source_type, "source_name": envelope.source_name},
        )

        result = {
            "doc_id": envelope.doc_id,
            "title": envelope.title,
            "assertions_extracted": len(assertions),
            "assertions_approved": len(approved_assertions),
            "assertions_pending": len(pending_assertions),
            "events_extracted": len(events),
            "events_approved": len(approved_events),
            "events_pending": len(pending_events),
            "extract_stats": extract_stats,
        }

        logger.info(f"Ingest envelope completed: {result}")
        return result

    def _extract_combined(
        self,
        text: str,
        doc_id: str,
    ) -> Dict[str, Any]:
        """
        合并提取断言和事件（1次LLM调用）

        Args:
            text: 规范化文本
            doc_id: 文档 ID

        Returns:
            {"assertions": [Assertion, ...], "events": [CanonicalEvent, ...]}
        """
        from knowledge_layer.assertions.prompts import AssertionPrompts

        model_gateway = self._model_gateway
        if model_gateway is None:
            return {"assertions": [], "events": [], "mode": "no_model_gateway"}

        try:
            system_prompt = AssertionPrompts.COMBINED_EXTRACT_SYSTEM_ZH
            user_prompt = AssertionPrompts.COMBINED_EXTRACT_USER_ZH.format(text=text)

            response = model_gateway.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                task="extraction",
            )

            # 解析 LLM 响应
            raw_data = self._parse_combined_response(response.content)

            # 构建断言对象
            assertions = []
            for a_data in raw_data.get("assertions", []):
                assertion = self._build_combined_assertion(a_data, doc_id)
                if assertion:
                    assertions.append(assertion)

            # 构建事件对象
            events = []
            for e_data in raw_data.get("events", []):
                event = self._build_combined_event(e_data, doc_id)
                if event:
                    events.append(event)

            logger.debug(f"Combined extraction: {len(assertions)} assertions, {len(events)} events")
            return {"assertions": assertions, "events": events}

        except Exception as e:
            logger.error(
                f"Combined extraction failed, falling back to separate: {e}", exc_info=True
            )
            # 回退到分步提取
            assertions = self._assertion_extractor.extract(text, doc_id)
            events = self._event_extractor.extract(text, doc_id)
            return {"assertions": assertions, "events": events}

    def _extract_combined_concurrent(
        self,
        text: str,
        doc_id: str,
        max_workers: int | None = None,
    ) -> Dict[str, Any]:
        """并发 chunk + LLM 提取（长文本用）

        Args:
            text: 规范化文本
            doc_id: 文档 ID
            max_workers: 并发数，默认从 settings 读取

        Returns:
            {"assertions": [...], "events": [...], "stats": {...}}
        """
        model_gateway = self._model_gateway
        if model_gateway is None:
            return {"assertions": [], "events": [], "stats": {"mode": "no_model_gateway"}}

        if max_workers is None:
            max_workers = settings.LLM_EXTRACT_MAX_WORKERS

        chunks = split_text(
            text,
            chunk_size=settings.LLM_EXTRACT_CHUNK_SIZE,
            overlap=settings.LLM_EXTRACT_CHUNK_OVERLAP,
        )

        extractor = ConcurrentLLMExtractor(
            model_gateway=cast(Any, model_gateway),
            build_assertion_fn=self._build_combined_assertion,
            build_event_fn=self._build_combined_event,
            parse_response_fn=self._parse_combined_response,
            max_workers=max_workers,
            max_retries=settings.LLM_EXTRACT_MAX_RETRIES,
            model=None,  # use task routing instead
            task="extraction",
        )

        assertions, events, stats = extractor.extract_chunks(chunks, doc_id)

        assertions = self._deduplicate_assertions(assertions)
        events = self._deduplicate_events(events)

        stats["mode"] = "combined_concurrent"

        logger.info(
            "concurrent combined extraction completed",
            doc_id=doc_id,
            stats=stats,
            final_assertions=len(assertions),
            final_events=len(events),
        )

        return {"assertions": assertions, "events": events, "stats": stats}

    def _parse_combined_response(self, content: str) -> Dict:
        """解析合并提取的 LLM 响应"""
        import json as _json

        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            return {"assertions": [], "events": []}
        json_str = content[json_start:json_end]
        return _json.loads(json_str)

    @staticmethod
    def _normalize_dedup_value(value: Any) -> str:
        """规范化去重 key 值：JSON 化 dict + 去空白 + 全角半角归一化"""
        if value is None:
            return ""
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = str(value).lower().strip()
        text = re.sub(r"\s+", "", text)
        text = text.replace("％", "%")
        return text

    def _deduplicate_assertions(self, assertions: list[Assertion]) -> list[Assertion]:
        """对并发 chunk 提取的断言去重（基于 subject + predicate + object_value + source_doc_id）"""
        seen: set[tuple[str, str, str, str]] = set()
        unique: list[Assertion] = []

        for a in assertions:
            key = (
                a.subject_entity_id or "",
                self._normalize_dedup_value(a.predicate),
                self._normalize_dedup_value(a.object_value),
                a.source_doc_id,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(a)

        return unique

    def _deduplicate_events(self, events: list[CanonicalEvent]) -> list[CanonicalEvent]:
        """对并发 chunk 提取的事件去重（基于 event_type + summary[:80] + source_doc_id）"""
        seen: set[tuple[str, str, str]] = set()
        unique: list[CanonicalEvent] = []

        for e in events:
            key = (
                e.event_type,
                (e.summary or "").strip()[:80],
                getattr(e, "source_doc_id", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)

        return unique

    def _build_combined_assertion(
        self, data: Dict, doc_id: str, chunk_index: int | None = None
    ) -> Optional[Assertion]:
        """从合并提取的数据构建 Assertion"""
        try:
            from knowledge_layer.entity_resolution import EntityType

            subject = data.get("subject", "")
            resolver = self._assertion_extractor._entity_resolver

            subject_entity_id = None
            if resolver:
                resolved = resolver.resolve(subject, EntityType.COMPANY)
                if resolved:
                    subject_entity_id = resolved.canonical_id

            observed_at = None
            observed_at_str = data.get("observed_at")
            if observed_at_str:
                try:
                    observed_at = datetime.fromisoformat(observed_at_str)
                except ValueError:
                    pass

            source_span: dict = {"extracted": data}
            if chunk_index is not None:
                source_span["chunk_index"] = chunk_index

            return Assertion(
                assertion_id=str(uuid.uuid4()),
                subject_entity_id=subject_entity_id,
                predicate=data.get("predicate", ""),
                object_entity_id=None,
                object_value={"text": data.get("object"), "value": data.get("value")},
                observed_at=observed_at,
                confidence=float(data.get("confidence", 0.7)),
                source_doc_id=doc_id,
                source_span=source_span,
                extractor_version="combined_v1.0",
                reviewer_status="draft",
            )
        except Exception as e:
            logger.error(f"Failed to build combined assertion: {e}", exc_info=True)
            return None

    def _build_combined_event(
        self, data: Dict, doc_id: str, chunk_index: int | None = None
    ) -> Optional[CanonicalEvent]:
        """从合并提取的数据构建 CanonicalEvent"""
        try:
            from knowledge_layer.events.types import EventType

            event_type_str = data.get("event_type", "other")
            mapping = {
                "earnings": EventType.EARNINGS.value,
                "merger_acquisition": EventType.MERGER_ACQUISITION.value,
                "dividend": EventType.DIVIDEND.value,
                "regulation": EventType.REGULATION.value,
                "product_launch": EventType.PRODUCT_LAUNCH.value,
            }
            event_type = mapping.get(event_type_str, EventType.OTHER.value)

            entities_raw = data.get("entities", [])
            entity_dicts = []
            if isinstance(entities_raw, list):
                for e in entities_raw:
                    if isinstance(e, str):
                        entity_dicts.append({"text": e, "type": "unknown", "confidence": 0.8})
                    elif isinstance(e, dict):
                        entity_dicts.append(e)

            # 提取事件时间
            evidence = data.get("evidence", "")
            event_time = self._event_extractor._extract_event_time(evidence) if evidence else None

            evidence_spans: list[dict] = [{"text": evidence[:300]}]
            if chunk_index is not None:
                evidence_spans[0]["chunk_index"] = chunk_index

            return CanonicalEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                source_type="document",
                source_name=doc_id,
                title=data.get("summary", "")[:200] or event_type,
                summary=data.get("summary", "")[:200],
                event_time=event_time,
                impact_direction=data.get("impact_direction", "unknown"),
                confidence=float(data.get("confidence", 0.7)),
                needs_review=data.get("confidence", 0.7) < 0.8,
                entities=entity_dicts,
                assertions=[],
                evidence_spans=evidence_spans,
                source_doc_id=doc_id,
            )
        except Exception as e:
            logger.error(f"Failed to build combined event: {e}", exc_info=True)
            return None

    def _normalize_text(self, text: str) -> str:
        """规范化文本"""
        # 简单的规范化
        text = text.strip()
        # 去除多余空白行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)
