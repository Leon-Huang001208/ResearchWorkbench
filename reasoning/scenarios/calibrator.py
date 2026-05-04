"""
概率校准节点
"""
from typing import List

from core.observability import get_logger
from reasoning.state import ReasoningState

logger = get_logger(__name__)


class ProbabilityCalibrator:
    """概率校准器"""

    def __init__(self):
        pass

    def calibrate(self, state: ReasoningState) -> ReasoningState:
        """
        校准概率

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info("Calibrating probabilities")

        if not state.hypotheses:
            return state

        # 计算当前总和
        total_prob = sum(h.probability for h in state.hypotheses)

        # 归一化
        if total_prob > 0:
            for hypothesis in state.hypotheses:
                hypothesis.probability = hypothesis.probability / total_prob

        # 检查并添加残余不确定性
        residual_uncertainty: List[str] = []
        if not state.skeptic_notes:
            residual_uncertainty.append("未发现明显问题，但仍需保持谨慎")
        else:
            residual_uncertainty.extend(state.skeptic_notes)

        # 添加一些通用的残余不确定性
        residual_uncertainty.extend(
            [
                "可能存在未预期的外部冲击",
                "历史表现不代表未来走势",
                "模型可能存在认知偏差",
            ]
        )

        state.residual_uncertainty = residual_uncertainty

        logger.info(
            f"Calibrated {len(state.hypotheses)} hypotheses, "
            f"probabilities sum to {sum(h.probability for h in state.hypotheses):.2f}, "
            f"residual uncertainty: {len(residual_uncertainty)} items"
        )

        return state

    def get_next_node(self, state: ReasoningState) -> str:
        """获取下一个节点"""
        # 下一步写报告
        return "report_composer"
