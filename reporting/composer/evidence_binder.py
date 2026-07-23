"""证据绑定器"""

from dataclasses import dataclass
from typing import Any, Optional

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass
class BoundEvidence:
    """绑定后的证据"""

    id: str
    source: str
    content: str
    relevance_score: float
    section_key: str | None = None


class EvidenceBinder:
    """证据绑定器 - 为报告段落绑定相关证据"""

    def __init__(self):
        self._evidence_store: dict[str, BoundEvidence] = {}

    def add_evidence(
        self,
        evidence_id: str,
        source: str,
        content: str,
        relevance_score: float = 1.0,
    ):
        """添加证据"""
        evidence = BoundEvidence(
            id=evidence_id,
            source=source,
            content=content,
            relevance_score=relevance_score,
        )
        self._evidence_store[evidence_id] = evidence
        logger.debug(f"Added evidence: {evidence_id}")

    def bind_to_section(
        self,
        section_key: str,
        query: str,
        top_k: int = 5,
    ) -> list[BoundEvidence]:
        """
        为指定段落绑定证据

        Args:
            section_key: 段落 key
            query: 查询关键词
            top_k: 返回的证据数量

        Returns:
            绑定的证据列表
        """
        # 简单的关键词匹配
        relevant_evidence = []
        query_terms = set(query.lower().split())

        for evidence in self._evidence_store.values():
            content_lower = evidence.content.lower()
            matches = sum(1 for term in query_terms if term in content_lower)

            if matches > 0:
                evidence.section_key = section_key
                # 简单评分：匹配词数 + 原始分数
                score = matches * 0.1 + evidence.relevance_score
                relevant_evidence.append((score, evidence))

        # 排序并返回 top_k
        relevant_evidence.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in relevant_evidence[:top_k]]

        logger.info(f"Bound {len(results)} evidences to section: {section_key}")
        return results

    def get_evidence_for_section(self, section_key: str) -> list[BoundEvidence]:
        """获取指定段落的证据"""
        return [e for e in self._evidence_store.values() if e.section_key == section_key]

    def get_evidence_by_id(self, evidence_id: str) -> Optional[BoundEvidence]:
        """根据 ID 获取证据"""
        return self._evidence_store.get(evidence_id)

    def to_dict_list(self, evidences: list[BoundEvidence]) -> list[dict[str, Any]]:
        """转换为字典列表"""
        return [
            {
                "id": e.id,
                "source": e.source,
                "content": e.content,
                "relevance_score": e.relevance_score,
            }
            for e in evidences
        ]

    def clear(self):
        """清空所有证据"""
        self._evidence_store.clear()
        logger.debug("Evidence store cleared")
