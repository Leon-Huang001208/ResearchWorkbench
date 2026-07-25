"""
任务分解器 - 报告编译器第一阶段.

把用户的报告需求（ReportTask）拆解为 research questions、证据需求表与检索预算，
指导来源规划器与检索器。对应 deep-research-report.md "任务分解器" 技能。

输入：ReportTask（template_name + context）
输出：ResearchPlan（research_questions / required_claim_types / required_evidence_types / retrieval_budget）

使用 model_gateway.structured_output 确保 JSON 可靠。
"""

from typing import Optional

from pydantic import BaseModel, Field

from core.contracts import ClaimType, EvidenceType, ReportTask, ResearchPlan
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class _ResearchPlanLLM(BaseModel):
    """LLM 任务分解的输出 schema（structured_output 约束）."""

    research_questions: list[str] = Field(default_factory=list, description="拆解出的研究子问题列表")
    required_claim_types: list[ClaimType] = Field(default_factory=list, description="需要的事实声明类型")
    required_evidence_types: list[EvidenceType] = Field(default_factory=list, description="需要的证据类型")
    max_documents: int = Field(default=50, description="检索文档预算")
    max_chunks: int = Field(default=200, description="检索 chunk 预算")


class TaskDecomposer:
    """任务分解器.

    将报告需求拆解为可执行的研究计划。不直接写长文，只负责编排结构。
    """

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self.model_gateway = model_gateway

    def decompose(self, task: ReportTask) -> ResearchPlan:
        """分解报告任务为研究计划.

        Args:
            task: 报告生成任务，含 template_name 与 context

        Returns:
            ResearchPlan：研究子问题、证据需求、检索预算
        """
        logger.info(
            "Decomposing report task",
            task_id=task.task_id,
            template=task.template_name,
        )

        if not self.model_gateway:
            logger.warning("No model gateway, returning default research plan")
            return self._default_plan(task)

        try:
            llm_plan = self.model_gateway.structured_output(
                messages=self._build_messages(task),
                output_schema=_ResearchPlanLLM,
                temperature=0.2,
            )
            return ResearchPlan(
                research_questions=llm_plan.research_questions,
                required_claim_types=llm_plan.required_claim_types,
                required_evidence_types=llm_plan.required_evidence_types,
                retrieval_budget={
                    "max_documents": llm_plan.max_documents,
                    "max_chunks": llm_plan.max_chunks,
                },
                metadata={"task_id": task.task_id, "template": task.template_name},
            )
        except Exception as e:
            logger.error(
                "Task decomposition failed, falling back to default plan",
                error=str(e),
                exc_info=True,
            )
            return self._default_plan(task)

    def _build_messages(self, task: ReportTask) -> list[dict[str, str]]:
        """构建任务分解 prompt."""
        context_str = ", ".join(f"{k}={v}" for k, v in task.context.items())
        system_msg = (
            "你是资深行业研究主编，负责把报告需求拆解为研究子问题。"
            "只输出 JSON：研究子问题列表、需要的事实声明类型(metric/event/spec/guidance/risk)、"
            "需要的证据类型(fact/opinion/mixed/data/quote/analysis)、检索预算。"
            "不要输出正文段落。"
        )
        user_msg = f"报告模板: {task.template_name}\n" f"上下文: {context_str or '（无）'}\n" "请拆解为研究计划。"
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _default_plan(self, task: ReportTask) -> ResearchPlan:
        """无 LLM 时的默认研究计划."""
        return ResearchPlan(
            research_questions=[f"分析 {task.template_name} 的核心驱动与风险"],
            required_claim_types=[ClaimType.METRIC, ClaimType.EVENT, ClaimType.RISK],
            required_evidence_types=[EvidenceType.FACT, EvidenceType.DATA],
            retrieval_budget={"max_documents": 50, "max_chunks": 200},
            metadata={"task_id": task.task_id, "template": task.template_name},
        )
