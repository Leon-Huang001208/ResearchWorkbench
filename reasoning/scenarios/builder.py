"""
假设构建节点 - 生成情景
"""
import uuid
from typing import Any, Dict, List, Optional

from core.interfaces import ModelGateway
from core.observability import get_logger
from reasoning.state import ReasoningState, ScenarioHypothesis

logger = get_logger(__name__)


class HypothesisBuilder:
    """假设构建器"""

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self._model_gateway = model_gateway

    def build(self, state: ReasoningState) -> ReasoningState:
        """
        构建假设

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info(f"Building hypotheses for: {state.question}")

        if self._model_gateway:
            hypotheses = self._build_by_llm(state)
        else:
            hypotheses = self._build_by_rules(state)

        state.hypotheses = hypotheses

        logger.info(f"Built {len(hypotheses)} hypotheses")
        return state

    def get_next_node(self, state: ReasoningState) -> str:
        """获取下一个节点"""
        return "skeptic"

    def _build_by_llm(self, state: ReasoningState) -> List[ScenarioHypothesis]:
        """使用 LLM 构建假设"""
        # TODO: 实现真正的 LLM 假设生成
        logger.debug("LLM hypothesis building not implemented yet")
        return self._build_by_rules(state)

    def _build_by_rules(self, state: ReasoningState) -> List[ScenarioHypothesis]:
        """使用规则构建假设（简单实现）"""
        question = state.question
        hypotheses: List[ScenarioHypothesis] = []

        # 基准情景
        hypotheses.append(
            ScenarioHypothesis(
                scenario_id=str(uuid.uuid4()),
                title="基准情景 - 按预期发展",
                horizon="mid",
                probability=0.5,
                assumptions=["当前趋势继续", "无重大意外事件"],
                key_triggers=["数据符合预期", "政策保持稳定"],
                invalidation_signals=["超预期事件", "政策转向"],
                confidence=0.7,
            )
        )

        # 乐观情景
        hypotheses.append(
            ScenarioHypothesis(
                scenario_id=str(uuid.uuid4()),
                title="乐观情景 - 超预期表现",
                horizon="mid",
                probability=0.25,
                assumptions=["数据超预期", "政策利好"],
                key_triggers=["超预期数据", "政策出台"],
                invalidation_signals=["数据不及预期", "政策未出台"],
                confidence=0.6,
            )
        )

        # 悲观情景
        hypotheses.append(
            ScenarioHypothesis(
                scenario_id=str(uuid.uuid4()),
                title="悲观情景 - 不及预期",
                horizon="mid",
                probability=0.25,
                assumptions=["数据不及预期", "外部负面冲击"],
                key_triggers=["弱于预期的数据", "负面事件"],
                invalidation_signals=["数据好转", "利好政策"],
                confidence=0.6,
            )
        )

        return hypotheses
