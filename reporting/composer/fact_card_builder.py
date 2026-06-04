"""
Fact Card 构建器 - 从证据中提取结构化事实.

Fact Card builder extracts structured facts from evidence before paragraph generation.
"""
from typing import Any, Dict, List, Optional

from core.contracts import FactCard
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class FactCardBuilder:
    """Fact Card 构建器.

    Extracts structured facts from evidence to create a FactCard,
    which serves as an intermediate representation before paragraph generation.
    This allows for review and validation of facts before writing.

    Attributes:
        model_gateway: Model gateway for LLM calls.
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        """初始化 Fact Card 构建器.

        Args:
            model_gateway: Model gateway for LLM calls.
        """
        self.model_gateway = model_gateway

    def build_fact_card(
        self,
        evidence: List[Dict[str, Any]],
        section_context: Optional[Dict[str, Any]] = None,
    ) -> FactCard:
        """从证据构建 Fact Card.

        Args:
            evidence: List of evidence dictionaries.
            section_context: Context for the section.

        Returns:
            Built FactCard.
        """
        logger.info("Building fact card from evidence")

        if not evidence:
            logger.warning("No evidence provided, returning empty fact card")
            return FactCard()

        # Simple rule-based extraction if no model gateway
        if not self.model_gateway:
            return self._extract_facts_rule_based(evidence)

        # Use LLM for more sophisticated extraction
        try:
            return self._extract_facts_with_llm(evidence, section_context)
        except Exception as e:
            logger.error(
                f"LLM fact extraction failed: {e}, falling back to rule-based", exc_info=True
            )
            return self._extract_facts_rule_based(evidence)

    def _extract_facts_rule_based(self, evidence: List[Dict[str, Any]]) -> FactCard:
        """基于规则的事实提取.

        Simple rule-based extraction for when LLM is not available.

        Args:
            evidence: List of evidence dictionaries.

        Returns:
            Extracted FactCard.
        """
        key_changes: List[str] = []
        drivers: List[str] = []
        impacts: List[str] = []
        watch_points: List[str] = []
        risks: List[str] = []
        source_refs: List[str] = []

        for idx, ev in enumerate(evidence, 1):
            content = ev.get("content", "")
            source = ev.get("source", f"Source {idx}")
            source_refs.append(source)

            # Simple keyword-based extraction
            content_lower = content.lower()

            # Extract key changes
            change_keywords = ["上涨", "下跌", "增长", "下降", "提升", "降低", "发布", "推出", "政策"]
            for keyword in change_keywords:
                if keyword in content_lower:
                    # Extract sentence with keyword
                    sentences = content.split("。")
                    for sentence in sentences:
                        if keyword in sentence:
                            clean_sentence = sentence.strip()
                            if clean_sentence and len(clean_sentence) < 200:
                                key_changes.append(clean_sentence)
                            break

            # Extract drivers
            driver_keywords = ["原因", "由于", "因为", "推动", "驱动", "导致"]
            for keyword in driver_keywords:
                if keyword in content_lower:
                    sentences = content.split("。")
                    for sentence in sentences:
                        if keyword in sentence:
                            clean_sentence = sentence.strip()
                            if clean_sentence and len(clean_sentence) < 200:
                                drivers.append(clean_sentence)
                            break

            # Extract impacts
            impact_keywords = ["影响", "利好", "利空", "受益", "受损", "推动"]
            for keyword in impact_keywords:
                if keyword in content_lower:
                    sentences = content.split("。")
                    for sentence in sentences:
                        if keyword in sentence:
                            clean_sentence = sentence.strip()
                            if clean_sentence and len(clean_sentence) < 200:
                                impacts.append(clean_sentence)
                            break

            # Extract risks
            risk_keywords = ["风险", "不确定性", "警惕", "注意", "担忧", "压力"]
            for keyword in risk_keywords:
                if keyword in content_lower:
                    sentences = content.split("。")
                    for sentence in sentences:
                        if keyword in sentence:
                            clean_sentence = sentence.strip()
                            if clean_sentence and len(clean_sentence) < 200:
                                risks.append(clean_sentence)
                            break

        # Deduplicate
        key_changes = list(dict.fromkeys(key_changes))[:5]
        drivers = list(dict.fromkeys(drivers))[:3]
        impacts = list(dict.fromkeys(impacts))[:3]
        risks = list(dict.fromkeys(risks))[:3]

        fact_card = FactCard(
            key_changes=key_changes,
            drivers=drivers,
            impacts=impacts,
            watch_points=watch_points,
            risks=risks,
            source_refs=source_refs,
        )

        logger.info(f"Built fact card with {len(key_changes)} key changes")
        return fact_card

    def _extract_facts_with_llm(
        self,
        evidence: List[Dict[str, Any]],
        section_context: Optional[Dict[str, Any]] = None,
    ) -> FactCard:
        """使用 LLM 进行事实提取.

        More sophisticated fact extraction using LLM.

        Args:
            evidence: List of evidence dictionaries.
            section_context: Context for the section.

        Returns:
            Extracted FactCard.
        """
        prompt = self._build_fact_extraction_prompt(evidence, section_context)
        model_gateway = self.model_gateway
        if model_gateway is None:
            return self._extract_facts_rule_based(evidence)

        try:
            response = model_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.3,
            )

            fact_card = self._parse_fact_card_response(response.content)
            logger.info(f"LLM fact extraction completed: {len(fact_card.key_changes)} key changes")
            return fact_card

        except Exception as e:
            logger.error(f"LLM fact extraction failed: {e}", exc_info=True)
            raise

    def _build_fact_extraction_prompt(
        self,
        evidence: List[Dict[str, Any]],
        section_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建事实提取提示词.

        Args:
            evidence: List of evidence dictionaries.
            section_context: Context for the section.

        Returns:
            Prompt string.
        """
        prompt_parts = [
            "# 事实提取任务",
            "",
            "请从以下证据中提取结构化事实，输出为 JSON 格式。",
            "",
            "## 输出格式：",
            """{
                "key_changes": ["关键变化1", "关键变化2"],
                "drivers": ["驱动因素1", "驱动因素2"],
                "impacts": ["影响1", "影响2"],
                "watch_points": ["观察点1", "观察点2"],
                "risks": ["风险1", "风险2"]
            }""",
            "",
            "## 参考证据：",
        ]

        for idx, ev in enumerate(evidence, 1):
            source = ev.get("source", "unknown")
            content = ev.get("content", "")[:500]
            prompt_parts.append(f"[{idx}] {source}: {content}")
            prompt_parts.append("")

        if section_context:
            prompt_parts.append("## 上下文信息：")
            for key, value in section_context.items():
                prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")

        prompt_parts.append("请只返回 JSON，不要包含其他文字。")

        return "\n".join(prompt_parts)

    def _parse_fact_card_response(self, response_content: str) -> FactCard:
        """解析 Fact Card 响应.

        Args:
            response_content: LLM response content.

        Returns:
            Parsed FactCard.
        """
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response_content)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_content

        try:
            data = json.loads(json_str)
            return FactCard(
                key_changes=data.get("key_changes", []),
                drivers=data.get("drivers", []),
                impacts=data.get("impacts", []),
                watch_points=data.get("watch_points", []),
                risks=data.get("risks", []),
                source_refs=[],
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse fact card JSON: {e}, returning empty")
            return FactCard()
