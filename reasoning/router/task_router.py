"""
任务路由节点
"""

from typing import Dict

from core.observability import get_logger
from reasoning.state import ReasoningState, RequestType

logger = get_logger(__name__)


class TaskRouter:
    """任务路由器"""

    def __init__(self):
        # 关键词映射到请求类型
        self._keywords = {
            RequestType.ASSET_ANALYSIS: [
                "分析",
                "资产",
                "股票",
                "走势",
                "估值",
                "财报",
                "analysis",
                "asset",
                "stock",
                "valuation",
                "financial",
            ],
            RequestType.THESIS_RESEARCH: [
                "研究",
                "专题",
                "探讨",
                "深度",
                "产业链",
                "政策",
                "research",
                "thesis",
                "topic",
                "industry chain",
                "policy",
            ],
            RequestType.MARKET_REPORT: [
                "市场",
                "走势",
                "展望",
                "策略",
                "投资",
                "宏观",
                "market",
                "outlook",
                "strategy",
                "investment",
                "macro",
            ],
            RequestType.SIGNAL_VALIDATION: [
                "信号",
                "验证",
                "回测",
                "策略",
                "因子",
                "alpha",
                "signal",
                "validation",
                "backtest",
                "strategy",
                "factor",
            ],
        }

    def route(self, state: ReasoningState) -> ReasoningState:
        """
        路由任务

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        # 如果已经有请求类型，直接返回
        if state.request_type:
            return state

        # 分析问题确定请求类型
        request_type = self._infer_request_type(state.question)
        state.request_type = request_type

        logger.info(f"Routed request to type: {request_type}")
        return state

    def get_next_node(self, state: ReasoningState) -> str:
        """
        获取下一个节点

        Returns:
            下一个节点名称
        """
        # 所有类型都先经过证据收集
        return "evidence_collector"

    def _infer_request_type(self, question: str) -> RequestType:
        """推断请求类型"""
        question_lower = question.lower()

        # 统计关键词匹配
        scores: Dict[RequestType, int] = {}
        for request_type, keywords in self._keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    score += 1
            scores[request_type] = score

        # 找出最高分
        max_score = max(scores.values()) if scores else 0

        if max_score > 0:
            # 返回最高分的类型
            for request_type, score in scores.items():
                if score == max_score:
                    return request_type

        # 默认返回专题研究
        return RequestType.THESIS_RESEARCH
