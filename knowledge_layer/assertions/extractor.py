"""
断言提取器 - 从文本中提取事实断言
"""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from core.contracts import Assertion
from core.interfaces import ModelGateway
from core.observability import get_logger
from knowledge_layer.assertions.prompts import AssertionPrompts
from knowledge_layer.entity_resolution import EntityResolver, EntityType

logger = get_logger(__name__)


class AssertionExtractor:
    """断言提取器"""

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        entity_resolver: Optional[EntityResolver] = None,
    ):
        self._model_gateway = model_gateway
        self._entity_resolver = entity_resolver or EntityResolver()

    def extract(
        self,
        text: str,
        source_doc_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[Assertion]:
        """
        从文本中提取断言

        Args:
            text: 输入文本
            source_doc_id: 源文档 ID
            metadata: 元数据

        Returns:
            断言列表
        """
        logger.debug(f"Extracting assertions from text (length: {len(text)})")

        # 1. 尝试使用 LLM 提取
        if self._model_gateway:
            assertions = self._extract_by_llm(text, source_doc_id)
            if assertions:
                return assertions

        # 2. 回退到规则提取
        assertions = self._extract_by_rules(text, source_doc_id)

        return assertions

    def _extract_by_llm(
        self,
        text: str,
        source_doc_id: str,
    ) -> List[Assertion]:
        """使用 LLM 提取断言"""
        try:
            # 构建提示
            system_prompt = AssertionPrompts.EXTRACT_SYSTEM_ZH
            user_prompt = AssertionPrompts.EXTRACT_USER_ZH.format(text=text)

            # 调用模型
            response = self._model_gateway.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                model=getattr(self, '_model', None),
            )

            # 解析响应
            extracted_data = self._parse_llm_response(response.content)

            # 转换为 Assertion 对象
            assertions = []
            for data in extracted_data:
                assertion = self._build_assertion(data, source_doc_id)
                if assertion:
                    assertions.append(assertion)

            logger.debug(f"LLM extracted {len(assertions)} assertions")
            return assertions

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}", exc_info=True)
            return []

    def _extract_by_rules(
        self,
        text: str,
        source_doc_id: str,
    ) -> List[Assertion]:
        """使用规则提取断言（简单实现）"""
        assertions: List[Assertion] = []

        # 提取实体作为主体
        entities = self._entity_resolver.extract_candidates(text)

        # 为每个实体创建一个断言（简单实现）
        for entity in entities[:5]:  # 限制数量
            assertion = Assertion(
                assertion_id=str(uuid.uuid4()),
                subject_entity_id=None,
                predicate="mentioned",
                object_value={"text": entity.text},
                confidence=entity.confidence,
                source_doc_id=source_doc_id,
                source_span={"text": text[:100], "entity": entity.text},
                extractor_version="rule_v1",
                reviewer_status="draft",
            )
            assertions.append(assertion)

        logger.debug(f"Rule-based extracted {len(assertions)} assertions")
        return assertions

    def _parse_llm_response(self, content: str) -> List[Dict]:
        """解析 LLM 响应"""
        # 尝试找到 JSON 部分
        json_start = content.find("[")
        json_end = content.rfind("]") + 1

        if json_start == -1 or json_end == 0:
            # 尝试单个对象
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                return []
            json_str = content[json_start:json_end]
            return [json.loads(json_str)]

        json_str = content[json_start:json_end]
        return json.loads(json_str)

    def _build_assertion(self, data: Dict, source_doc_id: str) -> Optional[Assertion]:
        """从提取的数据构建 Assertion"""
        try:
            subject = data.get("subject", "")

            # 尝试解析主体
            subject_entity_id = None
            if self._entity_resolver:
                resolved = self._entity_resolver.resolve(subject, EntityType.COMPANY)
                if resolved:
                    subject_entity_id = resolved.canonical_id

            # 解析观察时间
            observed_at = None
            observed_at_str = data.get("observed_at")
            if observed_at_str:
                try:
                    observed_at = datetime.fromisoformat(observed_at_str)
                except ValueError:
                    pass

            return Assertion(
                assertion_id=str(uuid.uuid4()),
                subject_entity_id=subject_entity_id,
                predicate=data.get("predicate", ""),
                object_entity_id=None,
                object_value={"text": data.get("object"), "value": data.get("value")},
                observed_at=observed_at,
                confidence=float(data.get("confidence", 0.7)),
                source_doc_id=source_doc_id,
                source_span={"extracted": data},
                extractor_version=f"llm_{AssertionPrompts.VERSION}",
                reviewer_status="draft",
            )
        except Exception as e:
            logger.error(f"Failed to build assertion: {e}", exc_info=True)
            return None
