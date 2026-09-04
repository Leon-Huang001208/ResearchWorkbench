"""
Abstract base class (interface) for reasoning engines.

Defines the interface for reasoning engines, which perform asset analysis, scenario
generation, and reasoning trace retrieval in Research Workbench.
"""

from abc import ABC, abstractmethod
from typing import Any

from core.contracts import AssetAnalysisSnapshot, ReasoningTrace, ScenarioSet


class ReasoningEngine(ABC):
    """推理引擎基类 - 基于证据进行推理.

    Abstract base class for reasoning engines, which are responsible for analyzing assets,
    generating scenario sets, and retrieving reasoning traces.
    """

    @abstractmethod
    def analyze_asset(self, canonical_id: str, **kwargs: Any) -> AssetAnalysisSnapshot:
        """分析资产并生成快照.

        Analyzes an asset by its canonical ID and generates an AssetAnalysisSnapshot.

        Args:
            canonical_id: Unique canonical ID of the asset to analyze.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            AssetAnalysisSnapshot: Snapshot of the asset analysis results.
        """
        pass

    @abstractmethod
    def generate_scenarios(self, question: str, **kwargs: Any) -> ScenarioSet:
        """生成多情景分析.

        Generates a ScenarioSet for a given question, including multiple hypotheses.

        Args:
            question: Question to generate scenarios for.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            ScenarioSet: Set of scenarios for the question.
        """
        pass

    @abstractmethod
    def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        """获取推理追踪.

        Retrieves a ReasoningTrace by its ID (if it exists).

        Args:
            trace_id: Unique ID of the reasoning trace to retrieve.

        Returns:
            ReasoningTrace | None: The requested trace, or None if not found.
        """
        pass
