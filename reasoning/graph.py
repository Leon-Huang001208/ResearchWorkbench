"""
推理引擎 - LangGraph 状态图
"""

from datetime import datetime
from typing import Any, Optional

from core.contracts import AssetAnalysisSnapshot, ReasoningTrace, ScenarioSet
from core.interfaces.reasoning_engine import ReasoningEngine as ReasoningEngineABC
from core.observability import get_logger
from reasoning.evidence.collector import EvidenceCollector
from reasoning.router.task_router import TaskRouter
from reasoning.scenarios.builder import HypothesisBuilder
from reasoning.scenarios.calibrator import ProbabilityCalibrator
from reasoning.skeptic.reviewer import Skeptic
from reasoning.state import ReasoningState, RequestType, create_initial_state
from reasoning.traces.writer import TraceWriter

logger = get_logger(__name__)


class ReasoningEngine(ReasoningEngineABC):
    """推理引擎"""

    def __init__(
        self,
        task_router: Optional[TaskRouter] = None,
        evidence_collector: Optional[EvidenceCollector] = None,
        hypothesis_builder: Optional[HypothesisBuilder] = None,
        skeptic: Optional[Skeptic] = None,
        probability_calibrator: Optional[ProbabilityCalibrator] = None,
        trace_writer: Optional[TraceWriter] = None,
    ):
        self._task_router = task_router or TaskRouter()
        self._evidence_collector = evidence_collector or EvidenceCollector()
        self._hypothesis_builder = hypothesis_builder or HypothesisBuilder()
        self._skeptic = skeptic or Skeptic()
        self._probability_calibrator = probability_calibrator or ProbabilityCalibrator()
        self._trace_writer = trace_writer or TraceWriter()

    def run(
        self,
        question: str,
        request_type: Optional[RequestType] = None,
        subject_ids: Optional[list] = None,
    ) -> ReasoningState:
        """
        运行推理

        Args:
            question: 问题
            request_type: 请求类型（可选，自动推断）
            subject_ids: 主题 ID 列表

        Returns:
            最终状态
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting reasoning for question: {question}")

        # 创建初始状态
        state = create_initial_state(
            request_type or RequestType.THESIS_RESEARCH,
            question,
            subject_ids,
        )

        # 如果没有提供请求类型，先路由
        if not request_type:
            state = self._task_router.route(state)

        # 执行节点链
        state = self._evidence_collector.collect(state)
        state = self._hypothesis_builder.build(state)
        state = self._skeptic.review(state)
        state = self._probability_calibrator.calibrate(state)

        # 生成最终答案
        state.final_answer = self._generate_final_answer(state)

        # 写入 trace
        state.total_latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        state = self._trace_writer.write(state)

        logger.info(f"Reasoning completed in {state.total_latency_ms}ms")
        return state

    def _generate_final_answer(self, state: ReasoningState) -> str:
        """生成最终答案"""
        parts = [
            f"# 分析结果: {state.question}",
            "",
            "## 情景分析",
        ]

        for hypothesis in state.hypotheses:
            parts.append(f"\n### {hypothesis.title} (概率: {hypothesis.probability:.0%})")
            if hypothesis.assumptions:
                parts.append("\n**核心假设:**")
                for assumption in hypothesis.assumptions:
                    parts.append(f"- {assumption}")
            if hypothesis.key_triggers:
                parts.append("\n**关键触发因素:**")
                for trigger in hypothesis.key_triggers:
                    parts.append(f"- {trigger}")

        if state.residual_uncertainty:
            parts.append("\n## 不确定性提示")
            for item in state.residual_uncertainty[:5]:
                parts.append(f"- {item}")

        return "\n".join(parts)

    # ---- ReasoningEngineABC interface ----

    def analyze_asset(self, canonical_id: str, **kwargs: Any) -> AssetAnalysisSnapshot:
        """实现 ReasoningEngineABC.analyze_asset。

        委托给 run() 使用 ASSET_ANALYSIS 请求类型，将结果转为
        AssetAnalysisSnapshot。
        """
        state = self.run(canonical_id, RequestType.ASSET_ANALYSIS)
        return AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=state.created_at,
            evidence_refs=state.retrieved_doc_ids,
            event_impact=[],
        )

    def generate_scenarios(self, question: str, **kwargs: Any) -> ScenarioSet:
        """实现 ReasoningEngineABC.generate_scenarios。

        委托给 run() 使用 THESIS_RESEARCH 请求类型，将 hypotheses
        转为 ScenarioSet。
        """
        state = self.run(question, RequestType.THESIS_RESEARCH)
        return ScenarioSet(
            set_id=state.trace_id or "",
            question=question,
            hypotheses=state.hypotheses,
            normalization_check=True,
            residual_uncertainty=state.residual_uncertainty,
        )

    def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        """实现 ReasoningEngineABC.get_trace。当前暂无持久化跟踪，return None。"""
        return None
