"""
事件提取器
"""
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from core.contracts import CanonicalEvent
from core.interfaces import ModelGateway
from core.observability import get_logger
from data_layer.normalizers.date_normalizer import DateNormalizer
from knowledge_layer.entity_resolution import EntityResolver
from knowledge_layer.events.types import EventType

logger = get_logger(__name__)


class EventExtractor:
    """事件提取器"""

    FALLBACK_MODEL = "deepseek-v4-pro"

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        entity_resolver: Optional[EntityResolver] = None,
        date_normalizer: Optional[DateNormalizer] = None,
    ):
        self._model_gateway = model_gateway
        self._entity_resolver = entity_resolver or EntityResolver()
        self._date_normalizer = date_normalizer or DateNormalizer()

        # 时间模式
        self._date_patterns = [
            re.compile(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})"),
            re.compile(r"(\d{2})[月/-](\d{1,2})"),
            re.compile(r"(\d{4})年(\d{1,2})月"),
        ]

    def _call_llm(self, messages, model=None):
        """调用 LLM，可指定模型。"""
        return self._model_gateway.chat(
            messages=messages,
            model=model,
            temperature=0.1,
            max_tokens=1500,
            task="extraction" if model is None else None,
        )

    def extract(
        self,
        text: str,
        source_doc_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[CanonicalEvent]:
        """
        从文本中提取事件

        Args:
            text: 输入文本
            source_doc_id: 源文档 ID
            metadata: 元数据

        Returns:
            规范事件列表
        """
        logger.debug(f"Extracting events from text (length: {len(text)})")

        if self._model_gateway:
            events = self._extract_by_llm(text, source_doc_id)
            if events:
                return events
            logger.warning("LLM event extraction returned empty, returning empty list")

        logger.warning("No LLM available for event extraction, returning empty list")
        return []

    def _extract_by_llm(
        self,
        text: str,
        source_doc_id: str,
    ) -> List[CanonicalEvent]:
        """使用 LLM 提取事件，flash 失败则用 pro 重试。"""
        try:
            from knowledge_layer.events.prompts import EventPrompts

            system_prompt = EventPrompts.EXTRACT_SYSTEM_ZH
            user_prompt = EventPrompts.EXTRACT_USER_ZH.format(text=text)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            try:
                response = self._call_llm(messages)
                extracted_data = self._parse_llm_response(response.content)
                if extracted_data:
                    return self._build_events(extracted_data, source_doc_id)
            except Exception:
                logger.warning(
                    "Primary extraction model failed, retrying with fallback model",
                    fallback_model=self.FALLBACK_MODEL,
                )
                response = self._call_llm(messages, model=self.FALLBACK_MODEL)
                extracted_data = self._parse_llm_response(response.content)
                return self._build_events(extracted_data, source_doc_id)

            return []

        except Exception as e:
            logger.error(f"LLM event extraction failed: {e}", exc_info=True)
            return []

    def _build_events(self, extracted_data: List[Dict], source_doc_id: str) -> List[CanonicalEvent]:
        events = []
        for data in extracted_data:
            event = self._build_event(data, source_doc_id)
            if event:
                events.append(event)
        logger.debug(f"LLM extracted {len(events)} events")
        return events

    def _parse_llm_response(self, content: str) -> List[Dict]:
        """解析 LLM 响应"""
        import json

        json_start = content.find("[")
        json_end = content.rfind("]") + 1

        if json_start == -1 or json_end == 0:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                return []
            json_str = content[json_start:json_end]
            return [json.loads(json_str)]

        json_str = content[json_start:json_end]
        return json.loads(json_str)

    def _build_event(self, data: Dict, source_doc_id: str) -> Optional[CanonicalEvent]:
        """从 LLM 提取数据构建 CanonicalEvent"""
        try:
            event_type_str = data.get("event_type", "other")
            event_type = self._map_event_type(event_type_str)

            entities_raw = data.get("entities", [])
            entity_dicts = []
            if isinstance(entities_raw, list):
                for e in entities_raw:
                    if isinstance(e, str):
                        entity_dicts.append({"text": e, "type": "unknown", "confidence": 0.8})
                    elif isinstance(e, dict):
                        entity_dicts.append(e)

            event_time = self._extract_event_time(data.get("evidence", ""))

            return CanonicalEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                summary=data.get("summary", "")[:200],
                event_time=event_time,
                impact_direction=data.get("impact_direction", "unknown"),
                confidence=float(data.get("confidence", 0.7)),
                needs_review=data.get("confidence", 0.7) < 0.8,
                entities=entity_dicts,
                assertions=[],
                evidence_spans=[{"text": data.get("evidence", "")[:300]}],
                source_doc_id=source_doc_id,
            )
        except Exception as e:
            logger.error(f"Failed to build event: {e}", exc_info=True)
            return None

    def _map_event_type(self, type_str: str) -> str:
        """将 LLM 输出的事件类型映射到枚举值"""
        mapping = {
            "earnings": EventType.EARNINGS.value,
            "merger_acquisition": EventType.MERGER_ACQUISITION.value,
            "dividend": EventType.DIVIDEND.value,
            "regulation": EventType.REGULATION.value,
            "product_launch": EventType.PRODUCT_LAUNCH.value,
        }
        return mapping.get(type_str, EventType.OTHER.value)

    def _extract_event_time(self, text: str) -> Optional[datetime]:
        """从文本中提取时间"""
        # 先尝试从元数据或已知位置提取
        for pattern in self._date_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        year, month, day = groups
                        return datetime(int(year), int(month), int(day))
                    elif len(groups) == 2:
                        # 没有年份，使用当前年
                        month, day = groups
                        now = datetime.utcnow()
                        return datetime(now.year, int(month), int(day))
                except ValueError:
                    continue

        return None
