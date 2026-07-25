"""
大纲规划器 - 报告编译器第一阶段.

基于 facts 摘要和报告模板生成标题树（ReportOutline），每节明确 must_answer、
required_evidence_types、counterpoints。对应 deep-research-report.md "大纲规划器"
技能，参考其第 106-133 行的 outline planner prompt 结构。

outline 优先于 prose：先做逻辑框架，再分节写作。禁止输出正文段落。
"""

from typing import Optional

from pydantic import BaseModel, Field

from core.contracts import (
    ClaimType,
    EvidenceType,
    FactRecord,
    OutlineSection,
    ReportOutline,
    ReportTask,
)
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class _OutlineSectionLLM(BaseModel):
    """LLM 大纲单节输出 schema."""

    title: str = Field(description="节点标题")
    goal: str = Field(default="", description="本节目标")
    must_answer: list[str] = Field(default_factory=list, description="必须回答的子问题")
    required_evidence_types: list[EvidenceType] = Field(default_factory=list, description="需要的证据类型")
    required_claim_types: list[ClaimType] = Field(default_factory=list, description="需要的事实声明类型")
    counterpoints: list[str] = Field(default_factory=list, description="风险与反证")
    target_words: int = Field(default=500, description="目标字数")


class _OutlineLLM(BaseModel):
    """LLM 大纲整体输出 schema."""

    report_title: str = Field(description="报告标题")
    thesis: str = Field(default="", description="核心论点")
    sections: list[_OutlineSectionLLM] = Field(default_factory=list, description="章节列表")


class OutlinePlanner:
    """大纲规划器.

    只根据给定证据规划标题树，不直接写长文。
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self.model_gateway = model_gateway

    def plan(
        self,
        facts: list[FactRecord],
        task: ReportTask,
    ) -> ReportOutline:
        """基于事实生成报告大纲.

        Args:
            facts: 事实抽取器产出的 FactRecord 列表
            task: 报告任务

        Returns:
            ReportOutline：标题树 + 各节证据覆盖要求
        """
        logger.info("Planning outline", facts=len(facts), template=task.template_name)

        if not self.model_gateway or not facts:
            return self._default_outline(facts, task)

        try:
            llm_outline = self.model_gateway.structured_output(
                messages=self._build_messages(facts, task),
                output_schema=_OutlineLLM,
                temperature=0.2,
            )
            sections = [
                OutlineSection(
                    section_id=f"sec_{i}",
                    title=s.title,
                    goal=s.goal,
                    must_answer=s.must_answer,
                    required_evidence_types=s.required_evidence_types,
                    required_claim_types=s.required_claim_types,
                    counterpoints=s.counterpoints,
                    target_words=s.target_words,
                )
                for i, s in enumerate(llm_outline.sections)
            ]
            return ReportOutline(
                report_title=llm_outline.report_title,
                thesis=llm_outline.thesis,
                sections=sections,
                metadata={"task_id": task.task_id},
            )
        except Exception as e:
            logger.error(
                "Outline planning failed, falling back to default",
                error=str(e),
                exc_info=True,
            )
            return self._default_outline(facts, task)

    def _build_messages(self, facts: list[FactRecord], task: ReportTask) -> list[dict[str, str]]:
        """构建大纲规划 prompt（参考 deep-research-report.md 示例一）."""
        system_msg = (
            "你是资深行业研究总编，不直接写长文，先负责编排结构。"
            "你的目标是：1) 只根据给定证据规划标题树；"
            "2) 每一节必须说明'要回答的问题''要用到的证据类型''风险与反证'；"
            "3) 禁止输出正文段落。只输出 JSON。"
        )
        evidence_digest = self._digest_facts(facts)
        user_msg = (
            f"任务: 生成《{task.template_name}》的大纲\n"
            f"受众: 投资/战略/产品团队\n"
            f"语言: 中文\n"
            f"证据摘要:\n{evidence_digest}\n"
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _digest_facts(self, facts: list[FactRecord]) -> str:
        """把 facts 压缩为大纲规划可用的证据摘要."""
        lines: list[str] = []
        for f in facts[:60]:  # 限制摘要长度
            value_str = f"{f.value}{f.unit}" if f.value is not None else ""
            lines.append(
                f"- [{f.claim_type.value}] {f.claim_text} {value_str}"
                f"（来源: {f.provenance.source_name}, {f.provenance.source_tier.value}）"
            )
        return "\n".join(lines) if lines else "（暂无可用证据）"

    def _default_outline(self, facts: list[FactRecord], task: ReportTask) -> ReportOutline:
        """无 LLM 或无证据时的默认大纲."""
        sections = [
            OutlineSection(
                section_id="sec_summary",
                title="摘要与核心判断",
                goal="用一页讲清赛道结论、假设和风险",
                must_answer=["核心结论是什么", "关键假设", "主要风险"],
                required_claim_types=[ClaimType.METRIC, ClaimType.RISK],
                counterpoints=["利多叙事的反证"],
                target_words=400,
            ),
            OutlineSection(
                section_id="sec_evidence",
                title="关键证据与数据",
                goal="呈现支撑结论的核心事实与数字",
                must_answer=["关键指标", "时间线事件"],
                required_claim_types=[ClaimType.METRIC, ClaimType.EVENT],
                target_words=600,
            ),
            OutlineSection(
                section_id="sec_risk",
                title="风险与反证",
                goal="覆盖风险与反证，而非只写利多叙事",
                must_answer=["主要风险点", "历史反证案例"],
                required_claim_types=[ClaimType.RISK],
                counterpoints=["利多不成立的条件"],
                target_words=300,
            ),
        ]
        return ReportOutline(
            report_title=task.template_name,
            thesis="",
            sections=sections,
            metadata={"task_id": task.task_id, "default": True},
        )
