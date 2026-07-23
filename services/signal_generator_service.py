"""事件信号生成服务。"""

import uuid

from core.contracts import CanonicalEvent, EventAlphaSignal
from core.observability import get_logger

logger = get_logger(__name__)


class SignalGeneratorService:
    """从已审核事件生成候选 EventAlphaSignal。"""

    CONFIDENCE_WEIGHT = 0.7
    NOVELTY_WEIGHT = 0.3

    def generate_from_event(self, event: CanonicalEvent) -> list[EventAlphaSignal]:
        """根据事件影响标的生成候选信号。

        Args:
            event: 已标准化并通过审核的事件。

        Returns:
            为每个受影响标的生成的事件型信号列表；如果事件没有标的，返回空列表。
        """
        symbols = [symbol for symbol in event.impacted_symbols if symbol]
        if not symbols:
            logger.warning("No impacted symbols found for event", event_id=event.event_id)
            return []

        return [self._build_signal(event, symbol) for symbol in symbols]

    def _build_signal(self, event: CanonicalEvent, subject_id: str) -> EventAlphaSignal:
        """构建单个事件型信号。"""
        direction_text = {
            "positive": "利好",
            "negative": "利空",
            "mixed": "多空交织",
            "unknown": "影响待验证",
        }.get(event.impact_direction, "影响待验证")
        score = self._score_from_event(event)

        return EventAlphaSignal(
            signal_id=str(uuid.uuid4()),
            subject_id=subject_id,
            horizon="20d",
            thesis=f"{event.title} 对 {subject_id} 形成{direction_text}事件驱动机会",
            score=score,
            confidence=event.confidence,
            scenario_refs=[],
            evidence_refs=[event.source_doc_id] if event.source_doc_id else [],
            status="candidate",
            metadata={
                "generated_auto": True,
                "generated_from_event_id": event.event_id,
                "source_name": event.source_name,
            },
            event_id=event.event_id,
            event_type=event.event_type,
            event_time=event.event_time,
            impact_path=[event.summary or event.title],
            industry_impacts=event.impacted_industries,
            bullish_companies=[subject_id] if event.impact_direction == "positive" else [],
            bearish_companies=[subject_id] if event.impact_direction == "negative" else [],
        )

    def _score_from_event(self, event: CanonicalEvent) -> float:
        """用事件置信度和新颖度生成初始分数。"""
        score = float(
            self.CONFIDENCE_WEIGHT * event.confidence + self.NOVELTY_WEIGHT * event.novelty_score
        )
        return max(0.0, min(1.0, score))
