"""
实体解析器 - 从文本中识别实体
"""
import json
import re
from typing import Optional

from core.interfaces import ModelGateway
from core.observability import get_logger
from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer
from knowledge_layer.entity_resolution.types import EntityCandidate, EntityType, ResolvedEntity

logger = get_logger(__name__)

_ENTITY_EXTRACTION_SYSTEM = """你是一个金融实体提取专家。从给定的文本中提取所有实体（公司、人物、概念、指数、商品等）。

返回 JSON 数组，每个元素格式：
{
  "text": "实体名称",
  "entity_type": "company|person|concept|index|commodity|currency|government|organization",
  "confidence": 0.0-1.0
}

规则：
- 只提取明确出现在文本中的实体
- 公司名、股票代码用 "company"
- 行业概念、政策名词用 "concept"
- 置信度基于文本中明确程度（代码/全称=高，简称=低）
- 不要返回空数组外的无关文本"""


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
            result = self._resolve_direct(text, entity_type)
            if result is not None:
                self._publish_entity_event(text, result)
            return result

        # 选择置信度最高的
        best_candidate = max(candidates, key=lambda c: c.confidence)

        # 生成 canonical ID
        canonical_id = self._canonicalizer.generate_id(
            best_candidate.text,
            best_candidate.entity_type,
        )

        result = ResolvedEntity(
            canonical_id=canonical_id,
            entity_type=best_candidate.entity_type,
            canonical_name=best_candidate.text,
            aliases=[best_candidate.text],
            confidence=best_candidate.confidence,
            matched_text=best_candidate.text,
        )
        self._publish_entity_event(text, result)
        return result

    @staticmethod
    def _publish_entity_event(raw_text: str, result: ResolvedEntity) -> None:
        """发布实体解析事件到管线监控。"""
        try:
            import asyncio

            from services.pipeline_monitor import pipeline_monitor
            from services.system_event_bus import event_bus

            payload = {
                "raw_text": raw_text[:100],
                "canonical_name": result.canonical_name,
                "entity_type": result.entity_type.value,
                "confidence": result.confidence,
            }
            asyncio.run(event_bus.publish("knowledge.entity_resolved", payload))
            pipeline_monitor.record_event("knowledge.entity_resolved", payload)
        except Exception:
            pass

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
        """使用 LLM 提取实体"""
        if not self._model_gateway:
            return []

        messages = [
            {"role": "system", "content": _ENTITY_EXTRACTION_SYSTEM},
            {"role": "user", "content": text},
        ]

        try:
            response = self._model_gateway.chat(messages, temperature=0.1)
            raw = response.content.strip()

            # 去除可能的 markdown 代码块包裹
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            items = json.loads(raw)
            if not isinstance(items, list):
                logger.warning("LLM entity extraction returned non-list, ignoring")
                return []

            candidates: list[EntityCandidate] = []
            for item in items:
                entity_text = item.get("text", "").strip()
                if not entity_text:
                    continue

                entity_type_str = item.get("entity_type", "concept")
                try:
                    entity_type = EntityType(entity_type_str)
                except ValueError:
                    entity_type = EntityType.CONCEPT

                confidence = float(item.get("confidence", 0.6))
                confidence = max(0.0, min(1.0, confidence))

                candidates.append(
                    EntityCandidate(
                        text=entity_text,
                        entity_type=entity_type,
                        confidence=confidence,
                    )
                )

            logger.info("LLM extracted %d entities from text", len(candidates))
            return candidates

        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.error("LLM entity extraction failed: %s", e, exc_info=True)
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
