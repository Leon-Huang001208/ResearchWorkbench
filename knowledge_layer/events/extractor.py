"""
事件提取器
"""
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.contracts import CanonicalEvent
from core.interfaces import ModelGateway
from core.observability import get_logger
from data_layer.normalizers.date_normalizer import DateNormalizer
from knowledge_layer.entity_resolution import EntityResolver
from knowledge_layer.events.types import EventType, ExtractedEvent

logger = get_logger(__name__)


class EventExtractor:
    """事件提取器"""

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        entity_resolver: Optional[EntityResolver] = None,
        date_normalizer: Optional[DateNormalizer] = None,
    ):
        self._model_gateway = model_gateway
        self._entity_resolver = entity_resolver or EntityResolver()
        self._date_normalizer = date_normalizer or DateNormalizer()

        # 事件类型关键词
        self._event_keywords = {
            EventType.EARNINGS: [
                "财报",
                "年报",
                "季报",
                "业绩",
                "净利润",
                "营收",
                "盈利",
                "earnings",
                "revenue",
                "profit",
                "financial report",
            ],
            EventType.MERGER_ACQUISITION: [
                "收购",
                "并购",
                "合并",
                "重组",
                "资产注入",
                "acquire",
                "merge",
                "acquisition",
                "merger",
            ],
            EventType.DIVIDEND: [
                "分红",
                "派息",
                "股利",
                "分红方案",
                "dividend",
                "payout",
            ],
            EventType.REGULATION: [
                "政策",
                "监管",
                "新规",
                "条例",
                "法规",
                "利好",
                "利空",
                "policy",
                "regulation",
                "new rule",
            ],
            EventType.PRODUCT_LAUNCH: [
                "发布",
                "推出",
                "新品",
                "新产品",
                "launch",
                "release",
                "new product",
            ],
        }

        # 时间模式
        self._date_patterns = [
            re.compile(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})"),
            re.compile(r"(\d{2})[月/-](\d{1,2})"),
            re.compile(r"(\d{4})年(\d{1,2})月"),
        ]

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

        # 1. 尝试使用 LLM 提取
        if self._model_gateway:
            events = self._extract_by_llm(text, source_doc_id)
            if events:
                return events

        # 2. 回退到规则提取
        events = self._extract_by_rules(text, source_doc_id)

        return events

    def _extract_by_llm(
        self,
        text: str,
        source_doc_id: str,
    ) -> List[CanonicalEvent]:
        """使用 LLM 提取事件"""
        # TODO: 实现真正的 LLM 提取
        logger.debug("LLM event extraction not implemented yet")
        return []

    def _extract_by_rules(
        self,
        text: str,
        source_doc_id: str,
    ) -> List[CanonicalEvent]:
        """使用规则提取事件"""
        events: List[CanonicalEvent] = []

        # 1. 检测事件类型
        event_type_scores = self._score_event_types(text)

        # 2. 提取时间
        event_time = self._extract_event_time(text)

        # 3. 提取实体
        entities = self._entity_resolver.extract_candidates(text)
        entity_dicts = [
            {"text": e.text, "type": e.entity_type.value, "confidence": e.confidence}
            for e in entities
        ]

        # 4. 创建事件（为每个检测到的类型创建一个）
        for event_type, score in event_type_scores.items():
            if score < 0.3:
                continue

            impact_direction = self._infer_impact_direction(text)

            event = CanonicalEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type.value,
                summary=self._generate_summary(text, event_type, entities),
                event_time=event_time,
                impact_direction=impact_direction,
                confidence=score,
                needs_review=True,
                entities=entity_dicts,
                assertions=[],
                evidence_spans=[{"text": text[:200]}],
                source_doc_id=source_doc_id,
            )
            events.append(event)

        # 如果没有检测到特定类型，创建一个通用事件
        if not events:
            event = CanonicalEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.OTHER.value,
                summary=text[:100] if len(text) > 100 else text,
                event_time=event_time,
                impact_direction="unknown",
                confidence=0.5,
                needs_review=True,
                entities=entity_dicts,
                assertions=[],
                evidence_spans=[{"text": text[:200]}],
                source_doc_id=source_doc_id,
            )
            events.append(event)

        logger.debug(f"Rule-based extracted {len(events)} events")
        return events

    def _score_event_types(self, text: str) -> Dict[EventType, float]:
        """为每个事件类型打分"""
        scores: Dict[EventType, float] = {}
        text_lower = text.lower()

        for event_type, keywords in self._event_keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 0.2
            scores[event_type] = min(score, 1.0)

        return scores

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

    def _infer_impact_direction(self, text: str) -> str:
        """推断影响方向"""
        positive_words = ["增长", "上涨", "利好", "超预期", "盈利", "增加", "提升"]
        negative_words = ["下降", "下跌", "利空", "低于预期", "亏损", "减少", "下滑"]

        text_lower = text.lower()
        positive_count = sum(1 for w in positive_words if w in text)
        negative_count = sum(1 for w in negative_words if w in text)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        elif positive_count > 0 and negative_count > 0:
            return "mixed"
        else:
            return "unknown"

    def _generate_summary(
        self,
        text: str,
        event_type: EventType,
        entities: List,
    ) -> str:
        """生成事件摘要"""
        # 简单实现：取前100字符
        if len(text) <= 100:
            return text

        # 尝试找到包含实体的句子
        entity_texts = [e.text for e in entities[:3]]
        for sentence in text.split("。")[:3]:
            if any(et in sentence for et in entity_texts):
                return sentence[:100]

        return text[:100]
