"""
实体解析器 - 从文本中识别实体
"""
import re
from pathlib import Path
from typing import Any, Optional

from core.interfaces import ModelGateway
from core.observability import get_logger
from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer, Market, Venue
from knowledge_layer.entity_resolution.types import EntityCandidate, EntityType, ResolvedEntity

logger = get_logger(__name__)


class EntityResolver:
    """实体解析器"""

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        canonicalizer: Optional[Canonicalizer] = None,
    ):
        self._model_gateway = model_gateway
        self._canonicalizer = canonicalizer or Canonicalizer()

        # 规则匹配模式
        self._stock_code_pattern = re.compile(r"\b(\d{6})(?:\.SH|\.SZ)?\b", re.IGNORECASE)
        self._hk_stock_pattern = re.compile(r"\b(\d{4,5})(?:\.HK)?\b", re.IGNORECASE)

        # 常见机构和概念词典（示例）
        self._entity_dict = {
            "公司": [
                "贵州茅台",
                "腾讯控股",
                "阿里巴巴",
                "美团",
                "京东",
                "拼多多",
                "中国平安",
                "招商银行",
                "工商银行",
                "建设银行",
                "宁德时代",
                "比亚迪",
                "特斯拉",
                "苹果",
                "微软",
                "谷歌",
            ],
            "概念": [
                "人工智能",
                "AI",
                "ChatGPT",
                "新能源",
                "锂电池",
                "光伏",
                "半导体",
                "芯片",
                "5G",
                "新基建",
                "数字经济",
                "元宇宙",
            ],
        }

    def extract_candidates(self, text: str) -> list[EntityCandidate]:
        """
        从文本中提取实体候选

        Args:
            text: 输入文本

        Returns:
            实体候选列表
        """
        candidates: list[EntityCandidate] = []

        # 1. 规则匹配 - 股票代码
        candidates.extend(self._extract_stock_codes(text))

        # 2. 词典匹配
        candidates.extend(self._extract_by_dictionary(text))

        # 3. LLM 提取（如果可用）
        if self._model_gateway:
            candidates.extend(self._extract_by_llm(text))

        # 去重
        candidates = self._deduplicate_candidates(candidates)

        return candidates

    def resolve(
        self,
        text: str,
        entity_type: Optional[EntityType] = None,
    ) -> Optional[ResolvedEntity]:
        """
        解析文本为规范化实体

        Args:
            text: 实体文本
            entity_type: 可选的实体类型提示

        Returns:
            解析后的实体，或 None
        """
        # 先提取候选
        candidates = self.extract_candidates(text)
        if not candidates:
            # 如果没有候选，尝试直接解析
            return self._resolve_direct(text, entity_type)

        # 选择置信度最高的
        best_candidate = max(candidates, key=lambda c: c.confidence)

        # 生成 canonical ID
        canonical_id = self._canonicalizer.generate_id(
            best_candidate.text,
            best_candidate.entity_type,
        )

        return ResolvedEntity(
            canonical_id=canonical_id,
            entity_type=best_candidate.entity_type,
            canonical_name=best_candidate.text,
            aliases=[best_candidate.text],
            confidence=best_candidate.confidence,
            matched_text=best_candidate.text,
        )

    def _extract_stock_codes(self, text: str) -> list[EntityCandidate]:
        """使用规则提取股票代码"""
        candidates: list[EntityCandidate] = []

        # A股
        for match in self._stock_code_pattern.finditer(text):
            code = match.group(1)
            candidates.append(
                EntityCandidate(
                    text=code,
                    entity_type=EntityType.COMPANY,
                    confidence=0.95,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )

        # 港股
        for match in self._hk_stock_pattern.finditer(text):
            code = match.group(1)
            candidates.append(
                EntityCandidate(
                    text=code,
                    entity_type=EntityType.COMPANY,
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )

        return candidates

    def _extract_by_dictionary(self, text: str) -> list[EntityCandidate]:
        """使用词典匹配提取实体"""
        candidates: list[EntityCandidate] = []

        # 公司
        for company in self._entity_dict.get("公司", []):
            idx = text.find(company)
            if idx != -1:
                candidates.append(
                    EntityCandidate(
                        text=company,
                        entity_type=EntityType.COMPANY,
                        confidence=0.85,
                        start_pos=idx,
                        end_pos=idx + len(company),
                    )
                )

        # 概念
        for concept in self._entity_dict.get("概念", []):
            idx = text.find(concept)
            if idx != -1:
                candidates.append(
                    EntityCandidate(
                        text=concept,
                        entity_type=EntityType.CONCEPT,
                        confidence=0.8,
                        start_pos=idx,
                        end_pos=idx + len(concept),
                    )
                )

        return candidates

    def _extract_by_llm(self, text: str) -> list[EntityCandidate]:
        """使用 LLM 提取实体（占位实现）"""
        # TODO: 实现真正的 LLM 提取逻辑
        logger.debug("LLM extraction not implemented yet")
        return []

    def _deduplicate_candidates(
        self,
        candidates: list[EntityCandidate],
    ) -> list[EntityCandidate]:
        """去重候选实体"""
        # 按文本和类型去重，保留置信度最高的
        seen: dict[tuple[str, EntityType], EntityCandidate] = {}
        for candidate in candidates:
            key = (candidate.text, candidate.entity_type)
            if key not in seen or candidate.confidence > seen[key].confidence:
                seen[key] = candidate
        return list(seen.values())

    def _resolve_direct(
        self,
        text: str,
        entity_type: Optional[EntityType] = None,
    ) -> Optional[ResolvedEntity]:
        """直接解析（当没有候选时）"""
        if entity_type is None:
            # 默认为概念
            entity_type = EntityType.CONCEPT

        canonical_id = self._canonicalizer.generate_id(text, entity_type)

        return ResolvedEntity(
            canonical_id=canonical_id,
            entity_type=entity_type,
            canonical_name=text,
            aliases=[text],
            confidence=0.5,
            matched_text=text,
        )
