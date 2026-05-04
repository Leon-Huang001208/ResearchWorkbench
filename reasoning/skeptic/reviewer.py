"""
反证审查节点
"""
from typing import List, Optional

from core.observability import get_logger
from reasoning.state import ReasoningState

logger = get_logger(__name__)


class Skeptic:
    """怀疑者 - 审查假设"""

    def __init__(self):
        pass

    def review(self, state: ReasoningState) -> ReasoningState:
        """
        审查假设

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info("Reviewing hypotheses")

        notes: List[str] = []

        # 1. 检查概率总和
        total_prob = sum(h.probability for h in state.hypotheses)
        if not (0.95 <= total_prob <= 1.05):
            notes.append(f"概率总和为 {total_prob:.2f}，建议归一化")

        # 2. 检查证据支持
        for hypothesis in state.hypotheses:
            if not hypothesis.evidence_assertion_ids:
                notes.append(f"假设 '{hypothesis.title}' 缺少明确的证据支持")

        # 3. 检查来源多样性
        doc_ids = set(state.retrieved_doc_ids)
        if len(doc_ids) == 0:
            notes.append("未检索到任何文档作为证据")
        elif len(doc_ids) < 3:
            notes.append(f"仅检索到 {len(doc_ids)} 个文档，来源可能不够多样化")

        # 4. 检查时间相关性
        # TODO: 检查证据的时效性

        state.skeptic_notes = notes

        if notes:
            logger.warning(f"Skeptic found {len(notes)} issues: {notes}")
        else:
            logger.info("Skeptic review passed without issues")

        return state

    def get_next_node(self, state: ReasoningState) -> str:
        """获取下一个节点"""
        # 下一步校准概率
        return "probability_calibrator"
