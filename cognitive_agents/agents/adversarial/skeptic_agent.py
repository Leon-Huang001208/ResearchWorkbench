"""怀疑论对抗 Agent。"""
import uuid

from cognitive_agents.agents.base import AgentContext, BaseCognitiveAgent
from cognitive_agents.contracts import AgentView
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class SkepticAgent(BaseCognitiveAgent):
    """负责主动质疑已有观点的对抗 Agent。"""

    def __init__(self, model_gateway: ModelGateway):
        super().__init__(model_gateway, "skeptic_agent", "skeptic")

    async def analyze(self, context: AgentContext) -> AgentView:
        prompt = self._build_prompt(context)
        messages = [{"role": "user", "content": prompt}]
        view_data = self.model_gateway.structured_output(
            messages=messages,
            output_schema=AgentView,
            temperature=0.7,
        )
        return AgentView(
            view_id=str(uuid.uuid4()),
            agent_name=self.agent_name,
            agent_role=self.agent_role,
            target_id=context.target_id,
            event_id=context.event_id,
            view=view_data.view,
            thesis=view_data.thesis,
            confidence=view_data.confidence,
            reasoning=view_data.reasoning,
            evidence_refs=view_data.evidence_refs,
            tool_refs=view_data.tool_refs,
            memory_refs=view_data.memory_refs,
            workflow_id=view_data.workflow_id,
            evaluation=view_data.evaluation,
            metadata=view_data.metadata,
        )

    def _build_prompt(self, context: AgentContext) -> str:
        return f"""你是一个怀疑论者，请基于以下信息，主动质疑已有观点，寻找潜在的风险和漏洞。

目标标的: {context.target_id}
问题: {context.question}
证据: {context.evidence}
市场数据: {context.market_data}
已有观点: {[v.model_dump() for v in context.prior_views]}

请以结构化方式输出你的分析结果，包含以下字段:
- view: 观点方向
- thesis: 核心论点
- confidence: 置信度（0-1）
- reasoning: 推理过程（列表形式）
- evidence_refs: 引用的证据（列表形式）
- metadata: 其他元数据
"""
