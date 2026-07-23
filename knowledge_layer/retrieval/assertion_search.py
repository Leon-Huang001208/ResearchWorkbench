"""断言检索服务 - 报告编译器第二阶段.

从 assertion 表按 predicate / object_value 全文匹配检索，关联 source_document
取 source_type / published_at，返回带评分的 ``list[Assertion]``。

对应 deep-research-report.md 第二阶段"检索统一"：让报告编译器除了检索 chunk
（EvidencePackage）之外，还能直接检索已结构化的断言，避免对已有 assertion 重复
跑 LLM 事实抽取（fact_extractor.extract_from_assertions 可直接复用）。
"""

from typing import Any, List, Optional

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.orm import Session

from core.contracts import Assertion, SourceReliabilityLevel
from core.observability import get_logger
from data_layer.repositories.models import Assertion as AssertionModel
from data_layer.repositories.models import (
    DocumentV1DB,
)

logger = get_logger(__name__)


class AssertionSearchService:
    """断言检索服务.

    按 query 关键词匹配 assertion 的 predicate 与 object_value（JSONB 文本），
    关联 document_v1 取来源分级与发布时间，返回按匹配分排序的断言列表。
    """

    def __init__(self, session_factory: Any):
        self._session_factory = session_factory

    def search(
        self,
        query: str,
        top_k: int = 20,
        source_doc_ids: Optional[List[str]] = None,
    ) -> List[Assertion]:
        """检索与 query 相关的断言.

        Args:
            query: 检索文本（按词匹配 predicate / object_value）
            top_k: 返回上限
            source_doc_ids: 可选，限定来源文档 ID 列表

        Returns:
            按匹配置信度排序的 Assertion 列表
        """
        if not query or not query.strip():
            return []

        keywords = [w for w in query.strip().split() if w]
        if not keywords:
            keywords = [query.strip()]

        session: Session = self._session_factory()
        try:
            stmt = select(AssertionModel)
            if source_doc_ids:
                stmt = stmt.where(AssertionModel.source_doc_id.in_(source_doc_ids))

            # 关键词匹配 predicate 或 object_value（JSONB 转文本后 ilike）
            or_clauses = []
            for kw in keywords:
                or_clauses.append(AssertionModel.predicate.ilike(f"%{kw}%"))
                or_clauses.append(cast(AssertionModel.object_value, Text).ilike(f"%{kw}%"))
            stmt = stmt.where(or_(*or_clauses))
            stmt = stmt.limit(top_k * 3)  # 取粗排后内存精排
            rows = session.execute(stmt).scalars().all()

            if not rows:
                return []

            # 内存精排：按关键词命中数 + assertion.confidence 综合评分
            scored: List[tuple[float, AssertionModel]] = []
            for row in rows:
                hit = self._count_keyword_hits(row, keywords)
                if hit == 0:
                    continue
                score = hit * 0.5 + float(row.confidence or 0.0) * 0.5
                scored.append((score, row))
            scored.sort(key=lambda x: x[0], reverse=True)

            results: List[Assertion] = []
            for _score, row in scored[:top_k]:
                results.append(self._to_assertion(row))
            logger.info(
                "Assertion search completed",
                query=query,
                candidates=len(rows),
                returned=len(results),
            )
            return results
        except Exception as e:  # noqa: BLE001
            logger.error("Assertion search failed", query=query, error=str(e), exc_info=True)
            return []
        finally:
            session.close()

    @staticmethod
    def _count_keyword_hits(row: AssertionModel, keywords: List[str]) -> int:
        """统计关键词在 predicate + object_value 文本中的命中数."""
        text = (row.predicate or "").lower()
        obj_text = ""
        if row.object_value:
            try:
                obj_text = str(row.object_value).lower()
            except Exception:  # noqa: BLE001
                obj_text = ""
        combined = f"{text} {obj_text}"
        return sum(1 for kw in keywords if kw.lower() in combined)

    @staticmethod
    def _to_assertion(row: AssertionModel) -> Assertion:
        """ORM 行转 Assertion 契约（与 AssertionRepositoryImpl._to_domain 对齐）."""
        return Assertion(
            assertion_id=row.assertion_id,
            subject_entity_id=row.subject_entity_id,
            predicate=row.predicate,
            object_entity_id=row.object_entity_id,
            object_value=row.object_value,
            observed_at=row.observed_at,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            confidence=float(row.confidence),
            source_doc_id=row.source_doc_id or "",
            source_span=row.source_span or {},
            extractor_version=row.extractor_version,
            reviewer_status=row.reviewer_status,
            reviewer=row.reviewer,
            reviewed_at=row.reviewed_at,
            trace_ref=row.trace_ref,
            team_id=row.team_id,
            project_id=row.project_id,
        )

    def get_source_reliability(self, source_doc_id: str) -> SourceReliabilityLevel:
        """查 source_doc_id 对应 document_v1 的来源可信度（用于 FactRecord.provenance）."""
        session: Session = self._session_factory()
        try:
            # source_doc_id 同时是 source_document.doc_id 与 document_v1.doc_id
            stmt = select(DocumentV1DB.quality).where(DocumentV1DB.doc_id == source_doc_id)
            quality = session.execute(stmt).scalar_one_or_none()
            if quality and isinstance(quality, dict):
                level = quality.get("source_reliability_level")
                if level:
                    try:
                        return SourceReliabilityLevel(level)
                    except ValueError:
                        return SourceReliabilityLevel.UNKNOWN
            return SourceReliabilityLevel.UNKNOWN
        except Exception:  # noqa: BLE001
            return SourceReliabilityLevel.UNKNOWN
        finally:
            session.close()
