"""
情景服务 - 专题研究报告生成
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.contracts import ScenarioHypothesis as ContractScenarioHypothesis
from core.contracts import ScenarioSet
from core.observability import get_logger
from reasoning import ReasoningEngine, RequestType
from reporting.composer import ReportComposer
from reporting.projections import MarkdownProjection

logger = get_logger(__name__)


class ScenarioService:
    """情景服务"""

    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        report_composer: Optional[ReportComposer] = None,
    ):
        self._reasoning_engine = reasoning_engine or ReasoningEngine()
        self._report_composer = report_composer or ReportComposer()

    def generate_scenario_set(
        self,
        topic: str,
        subject_ids: Optional[List[str]] = None,
    ) -> ScenarioSet:
        """
        生成情景集合

        Args:
            topic: 研究主题
            subject_ids: 主题 ID 列表

        Returns:
            情景集合
        """
        logger.info(f"Generating scenario set for topic: {topic}")

        # 运行推理引擎
        state = self._reasoning_engine.run(
            topic,
            RequestType.THESIS_RESEARCH,
            subject_ids,
        )

        # 转换为契约类型
        hypotheses = []
        for h in state.hypotheses:
            hypotheses.append(
                ContractScenarioHypothesis(
                    scenario_id=h.scenario_id,
                    title=h.title,
                    horizon=h.horizon,
                    probability=h.probability,
                    assumptions=h.assumptions,
                    key_triggers=h.key_triggers,
                    invalidation_signals=h.invalidation_signals,
                    impact_map=h.impact_map,
                    evidence_assertion_ids=h.evidence_assertion_ids,
                    confidence=h.confidence,
                )
            )

        return ScenarioSet(
            set_id=state.trace_id or "",
            question=topic,
            hypotheses=hypotheses,
            normalization_check=True,
            residual_uncertainty=state.residual_uncertainty,
        )

    def generate_thesis_report(
        self,
        topic: str,
        output_path: Optional[Path] = None,
        subject_ids: Optional[List[str]] = None,
    ) -> str:
        """
        生成专题研究报告

        Args:
            topic: 研究主题
            output_path: 输出文件路径
            subject_ids: 主题 ID 列表

        Returns:
            报告内容
        """
        logger.info(f"Generating thesis report for: {topic}")

        scenario_set = self.generate_scenario_set(topic, subject_ids)

        # 构建报告
        lines = [
            f"# {topic}",
            "",
            "## 摘要",
            "",
            f"本报告针对 '{topic}' 进行多情景分析，共包含 {len(scenario_set.hypotheses)} 个情景假设。",
            "",
            "## 情景分析",
        ]

        for hypothesis in scenario_set.hypotheses:
            lines.append("")
            lines.append(f"### {hypothesis.title}")
            lines.append("")
            lines.append(f"**概率**: {hypothesis.probability:.0%}")
            lines.append(f"**时间维度**: {hypothesis.horizon}")
            lines.append("")

            if hypothesis.assumptions:
                lines.append("**核心假设**:")
                for assumption in hypothesis.assumptions:
                    lines.append(f"- {assumption}")
                lines.append("")

            if hypothesis.key_triggers:
                lines.append("**关键触发因素**:")
                for trigger in hypothesis.key_triggers:
                    lines.append(f"- {trigger}")
                lines.append("")

            if hypothesis.invalidation_signals:
                lines.append("**失效信号**:")
                for signal in hypothesis.invalidation_signals:
                    lines.append(f"- {signal}")
                lines.append("")

        if scenario_set.residual_uncertainty:
            lines.append("")
            lines.append("## 不确定性提示")
            lines.append("")
            for item in scenario_set.residual_uncertainty:
                lines.append(f"- {item}")

        report_content = "\n".join(lines)

        # 保存到文件
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_content, encoding="utf-8")
            logger.info(f"Thesis report saved to: {output_path}")

        return report_content
