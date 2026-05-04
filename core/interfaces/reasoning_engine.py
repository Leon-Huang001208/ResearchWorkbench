from abc import ABC, abstractmethod
from typing import Any

from core.contracts import AssetAnalysisSnapshot, ReasoningTrace, ScenarioSet


class ReasoningEngine(ABC):
    """推理引擎基类 - 基于证据进行推理"""

    @abstractmethod
    def analyze_asset(self, canonical_id: str, **kwargs: Any) -> AssetAnalysisSnapshot:
        """分析资产并生成快照"""
        pass

    @abstractmethod
    def generate_scenarios(self, question: str, **kwargs: Any) -> ScenarioSet:
        """生成多情景分析"""
        pass

    @abstractmethod
    def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        """获取推理追踪"""
        pass
