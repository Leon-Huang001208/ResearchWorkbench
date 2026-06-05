"""认知 Agent 基类与共享数据结构。"""
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentRole, AgentSOP, AgentView, EvidenceBundle
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class AgentContext(BaseModel):
    """Agent 执行上下文。"""

    target_id: str  # 标的ID
    event_id: str | None = None  # 关联事件ID
    question: str  # 分析问题
    evidence: list[dict] = Field(default_factory=list)  # 证据（断言、事件等）
    evidence_bundle: EvidenceBundle | None = None  # 统一证据包
    market_data: dict = Field(default_factory=dict)  # 市场数据快照
    prior_views: list[AgentView] = Field(default_factory=list)  # 黑板已有观点

    def get_evidence_bundle(self) -> EvidenceBundle:
        """返回统一证据包，兼容旧版 loose evidence 输入。"""
        if self.evidence_bundle is not None:
            return self.evidence_bundle
        return EvidenceBundle.from_legacy(
            target_id=self.target_id,
            event_id=self.event_id,
            question=self.question,
            evidence=self.evidence,
            market_snapshot=self.market_data,
            prior_view_refs=[view.view_id for view in self.prior_views],
        )


class BaseCognitiveAgent(ABC):
    """认知 Agent 抽象基类。"""

    def __init__(self, model_gateway: ModelGateway, agent_name: str, agent_role: AgentRole):
        self.model_gateway = model_gateway
        self.agent_name = agent_name
        self.agent_role = agent_role

    @abstractmethod
    async def analyze(self, context: AgentContext) -> AgentView:
        """核心分析逻辑，由子类实现。"""
        pass

    def build_sop_prompt(self, context: AgentContext, sop: AgentSOP) -> str:
        """基于统一 SOP 和证据包构建 Agent 提示词。"""
        try:
            evidence_bundle = context.get_evidence_bundle()
        except Exception as exc:
            logger.error(
                "failed to build evidence bundle for agent prompt",
                agent_name=self.agent_name,
                agent_role=self.agent_role,
                target_id=context.target_id,
                error=str(exc),
                exc_info=True,
            )
            raise

        evidence_items = [
            {
                "evidence_id": item.evidence_id,
                "ref_id": item.ref_id,
                "ref_type": item.ref_type,
                "evidence_kind": item.evidence_kind,
                "source_type": item.source_type,
                "source_name": item.source_name,
                "title": item.title,
                "summary": item.summary,
                "reliability": item.reliability,
                "relevance": item.relevance,
            }
            for item in evidence_bundle.evidence_items
        ]

        return f"""你是 {self.agent_name}，角色是 {self.agent_role}。

目标标的: {context.target_id}
关联事件: {context.event_id or "无"}
问题: {context.question}

你的 SOP 目标:
{sop.objective}

重点检查:
{self._format_list(sop.focus_areas)}

必须优先引用的证据类型:
{self._format_list(list(sop.required_evidence_kinds))}

分析步骤:
{self._format_list(sop.analysis_steps)}

输出要求:
{self._format_list(sop.output_expectations)}

风险提示:
{self._format_list(sop.red_flags)}

统一证据包:
{evidence_items}

市场数据:
{evidence_bundle.market_snapshot}

已有观点:
{[view.model_dump() for view in context.prior_views]}

请严格输出 AgentView 结构，至少包含:
- view: bullish / bearish / neutral / mixed / unknown
- thesis: 核心论点
- confidence: 0 到 1
- reasoning: 推理步骤
- assumptions: 关键假设
- risks: 主要风险
- invalidation_triggers: 证伪触发条件
- recommended_next_checks: 下一步应该检查什么
- evidence_refs: 引用的证据 ref_id，必须来自统一证据包
- evaluation: 结构化评分
- metadata: 其他上下文
"""

    async def run(self, context: AgentContext, blackboard: CognitiveBlackboard) -> AgentView:
        """执行分析并写入黑板。"""
        logger.info(
            "running cognitive agent",
            agent_name=self.agent_name,
            agent_role=self.agent_role,
            target_id=context.target_id,
            event_id=context.event_id,
        )
        view = await self.analyze(context)
        blackboard.add_view(view)
        return view

    @staticmethod
    def _format_list(items: list[str]) -> str:
        if not items:
            return "- 无"
        return "\n".join(f"- {item}" for item in items)
