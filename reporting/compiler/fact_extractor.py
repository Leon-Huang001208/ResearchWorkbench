"""
事实抽取器 - 报告编译器第一阶段.

从 EvidencePackage 提取结构化 FactRecord，每个 fact 绑定 Provenance（doc_id/
chunk_id/source_type/source_tier/citation_anchor）。对应 deep-research-report.md
"证据抽取器" 技能。

区别于既有 FactCardBuilder（只输出 List[str] 无 provenance），本模块输出结构化
FactRecord，是报告编译器的最小证据单元。所有进入正文/表格/图表的数字与结论，
必须先落到 FactRecord。

使用 model_gateway.structured_output 保证 JSON 可靠（依赖第一阶段 provider 改造）。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from core.contracts import (
    Assertion,
    ClaimType,
    EvidenceDocument,
    EvidencePackage,
    FactRecord,
    Provenance,
    SourceReliabilityLevel,
    reliability_to_tier,
)
from core.interfaces import ModelGateway
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class _FactExtractionItem(BaseModel):
    """LLM 事实抽取的单条输出 schema."""

    claim_text: str = Field(description="事实声明文本")
    claim_type: ClaimType = Field(default=ClaimType.METRIC, description="声明类型")
    entities: list[str] = Field(default_factory=list, description="关联实体")
    period: Optional[str] = Field(default=None, description="期间")
    value: Optional[float] = Field(default=None, description="数值")
    unit: Optional[str] = Field(default=None, description="单位")
    evidence_span: str = Field(default="", description="原文证据片段")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")


class _FactExtractionResult(BaseModel):
    """LLM 事实抽取的整体输出 schema."""

    claims: list[_FactExtractionItem] = Field(default_factory=list, description="抽取的事实列表")


class FactExtractor:
    """事实抽取器.

    从 EvidencePackage 的每个 chunk 提取结构化事实，绑定完整 Provenance。
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self.model_gateway = model_gateway

    def extract(
        self,
        packages: list[EvidencePackage],
    ) -> list[FactRecord]:
        """从多个 EvidencePackage 提取事实.

        Args:
            packages: 证据检索器产出的证据包列表

        Returns:
            去重后的 FactRecord 列表
        """
        all_facts: list[FactRecord] = []
        for package in packages:
            for doc in package.documents:
                facts = self._extract_from_doc(doc)
                all_facts.extend(facts)

        deduped = self._deduplicate(all_facts)
        logger.info(
            "Fact extraction complete",
            packages=len(packages),
            raw_facts=len(all_facts),
            deduped_facts=len(deduped),
        )
        return deduped

    def extract_from_assertions(
        self,
        assertions: list[Assertion],
        source_reliability_map: dict[str, SourceReliabilityLevel] | None = None,
    ) -> list[FactRecord]:
        """直接从已结构化的 Assertion 复用为 FactRecord（跳过 LLM 抽取）.

        第二阶段"检索统一"：assertion 已是结构化事实（predicate/object_value/
        confidence/source_span 齐全），无需再过 LLM。本方法把它们转成 FactRecord，
        供 AssertionRetriever 路径使用，显著降低 LLM 成本。

        Args:
            assertions: AssertionSearchService 检索到的断言列表
            source_reliability_map: 可选的 source_doc_id → reliability 映射，
                缺失时 reliability 取 UNKNOWN（tier_d）

        Returns:
            去重后的 FactRecord 列表
        """
        reliability_map = source_reliability_map or {}
        all_facts: list[FactRecord] = []
        for assertion in assertions:
            fact = self._assertion_to_fact(assertion, reliability_map)
            if fact is not None:
                all_facts.append(fact)
        deduped = self._deduplicate(all_facts)
        logger.info(
            "Assertion-to-fact conversion complete",
            assertions=len(assertions),
            facts=len(deduped),
        )
        return deduped

    def _assertion_to_fact(
        self,
        assertion: Assertion,
        reliability_map: dict[str, SourceReliabilityLevel],
    ) -> FactRecord | None:
        """单个 Assertion → FactRecord（不调 LLM）."""
        try:
            obj = assertion.object_value or {}
            object_text = obj.get("text") or obj.get("value") if isinstance(obj, dict) else None
            value = obj.get("value") if isinstance(obj, dict) else None
            # 尝试把 value 转为 float（数值型 fact）
            numeric_value: float | None = None
            if value is not None:
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    numeric_value = None

            span = assertion.source_span or {}
            evidence_span = span.get("chunk_text") or (str(object_text) if object_text else "")
            claim_text = (
                f"{assertion.predicate}: {object_text}".strip(": ").strip() or assertion.predicate
            )

            reliability = reliability_map.get(
                assertion.source_doc_id or "", SourceReliabilityLevel.UNKNOWN
            )
            tier = reliability_to_tier(reliability)
            provenance = Provenance(
                doc_id=assertion.source_doc_id or "",
                chunk_id=None,
                source_type=None,
                source_name=assertion.source_doc_id or "",
                source_url=None,
                published_at=assertion.observed_at,
                source_reliability=reliability,
                source_tier=tier,
                citation_anchor=None,
            )
            return FactRecord(
                fact_id=generate_id(prefix="fact"),
                claim_text=claim_text,
                claim_type=self._infer_claim_type(assertion.predicate),
                entities=[assertion.subject_entity_id] if assertion.subject_entity_id else [],
                period=None,
                value=numeric_value,
                unit=self._infer_unit(object_text),
                evidence_span=evidence_span,
                confidence=float(assertion.confidence),
                provenance=provenance,
            )
        except Exception as e:
            logger.warning(
                "Assertion to FactRecord conversion failed",
                assertion_id=assertion.assertion_id,
                error=str(e),
            )
            return None

    @staticmethod
    def _infer_claim_type(predicate: str) -> ClaimType:
        """从 predicate 关键词推断声明类型（启发式）."""
        p = (predicate or "").lower()
        if any(k in p for k in ("event", "order", "订单", "投产", "人事", "launch")):
            return ClaimType.EVENT
        if any(k in p for k in ("risk", "风险")):
            return ClaimType.RISK
        if any(k in p for k in ("guidance", "指引", "展望", "forecast")):
            return ClaimType.GUIDANCE
        if any(k in p for k in ("spec", "规格", "rate", "速率", "功耗")):
            return ClaimType.SPEC
        return ClaimType.METRIC

    @staticmethod
    def _infer_unit(object_text: Any) -> str | None:
        """从 object 文本启发式提取单位."""
        if not object_text:
            return None
        text = str(object_text)
        for unit in ("亿元", "百万元", "万元", "Gbps", "Tbps", "%", "百分点", "倍"):
            if unit in text:
                return unit
        return None

    def _extract_from_doc(self, doc: EvidenceDocument) -> list[FactRecord]:
        """从单个文档的 chunks 提取事实."""
        if not doc.chunks:
            # 无 chunk 时退化为用 summary
            if doc.summary:
                return self._extract_chunk(
                    chunk_text=doc.summary,
                    doc=doc,
                    chunk_id=None,
                    chunk_index=0,
                )
            return []

        facts: list[FactRecord] = []
        for chunk in doc.chunks:
            facts.extend(
                self._extract_chunk(
                    chunk_text=chunk.content,
                    doc=doc,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                )
            )
        return facts

    def _extract_chunk(
        self,
        chunk_text: str,
        doc: EvidenceDocument,
        chunk_id: Optional[str],
        chunk_index: int,
    ) -> list[FactRecord]:
        """从单个 chunk 提取事实并绑定 Provenance."""
        if not chunk_text or not chunk_text.strip():
            return []

        if not self.model_gateway:
            # 无 LLM 时做规则抽取（数字+单位）
            return self._extract_rule_based(chunk_text, doc, chunk_id, chunk_index)

        try:
            result = self.model_gateway.structured_output(
                messages=self._build_messages(chunk_text, doc),
                output_schema=_FactExtractionResult,
                temperature=0.1,
            )
            return [
                self._to_fact_record(item, doc, chunk_id, chunk_index)
                for item in result.claims
                if item.claim_text
            ]
        except Exception as e:
            logger.error(
                "LLM fact extraction failed, falling back to rule-based",
                doc_id=doc.doc_id,
                error=str(e),
                exc_info=True,
            )
            return self._extract_rule_based(chunk_text, doc, chunk_id, chunk_index)

    def _build_messages(self, chunk_text: str, doc: EvidenceDocument) -> list[dict[str, str]]:
        """构建事实抽取 prompt（参考 deep-research-report.md 证据抽取器 prompt）."""
        system_msg = (
            "你是事实抽取器。你只做规范化，不做评论。"
            "如果文档里没有明确数字或结论，不要补全。"
            "只输出 JSON：claims 列表，每条含 claim_text/claim_type/entities/"
            "period/value/unit/evidence_span/confidence。"
        )
        user_msg = f"文档块:\n{chunk_text}\n\n来源: {doc.source_name or doc.source_type.value}"
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _to_fact_record(
        self,
        item: _FactExtractionItem,
        doc: EvidenceDocument,
        chunk_id: Optional[str],
        chunk_index: int,
    ) -> FactRecord:
        """把 LLM 抽取项转为 FactRecord，绑定 Provenance."""
        tier = reliability_to_tier(doc.source_reliability)
        provenance = Provenance(
            doc_id=doc.doc_id,
            chunk_id=chunk_id,
            source_type=doc.source_type,
            source_name=doc.source_name or doc.source_type.value,
            source_url=doc.source_url,
            published_at=doc.publish_time,
            source_reliability=doc.source_reliability,
            source_tier=tier,
            citation_anchor=None,  # 第二阶段精确化 offset
        )
        return FactRecord(
            fact_id=generate_id(prefix="fact"),
            claim_text=item.claim_text,
            claim_type=item.claim_type,
            entities=item.entities,
            period=item.period,
            value=item.value,
            unit=item.unit,
            evidence_span=item.evidence_span or item.claim_text,
            confidence=item.confidence,
            provenance=provenance,
        )

    def _extract_rule_based(
        self,
        chunk_text: str,
        doc: EvidenceDocument,
        chunk_id: Optional[str],
        chunk_index: int,
    ) -> list[FactRecord]:
        """规则抽取 - 无 LLM 时的兜底，提取数字+单位."""
        import re

        # 匹配"数字+单位"模式，如 100亿元 / 800G / 45%
        pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(亿元|百万元|万元|Gbps|Tbps|km|米|%|个百分点|倍)")
        facts: list[FactRecord] = []
        tier = reliability_to_tier(doc.source_reliability)
        provenance = Provenance(
            doc_id=doc.doc_id,
            chunk_id=chunk_id,
            source_type=doc.source_type,
            source_name=doc.source_name or doc.source_type.value,
            source_url=doc.source_url,
            published_at=doc.publish_time,
            source_reliability=doc.source_reliability,
            source_tier=tier,
        )
        for match in pattern.finditer(chunk_text):
            value = float(match.group(1))
            unit = match.group(2)
            span = match.group(0)
            facts.append(
                FactRecord(
                    fact_id=generate_id(prefix="fact"),
                    claim_text=span,
                    claim_type=ClaimType.METRIC,
                    value=value,
                    unit=unit,
                    evidence_span=span,
                    confidence=0.4,  # 规则抽取置信度低
                    provenance=provenance,
                )
            )
        return facts

    def _deduplicate(self, facts: list[FactRecord]) -> list[FactRecord]:
        """按 (claim_text, value, unit, doc_id) 去重."""
        seen: set[tuple[str, Optional[float], Optional[str], str]] = set()
        unique: list[FactRecord] = []
        for f in facts:
            key = (f.claim_text.strip(), f.value, f.unit, f.provenance.doc_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        return unique
