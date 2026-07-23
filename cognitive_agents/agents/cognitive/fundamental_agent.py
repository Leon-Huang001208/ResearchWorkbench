"""基本面分析 Agent。"""

import uuid

from cognitive_agents.agents.base import AgentContext, BaseCognitiveAgent
from cognitive_agents.agents.sop import get_agent_sop
from cognitive_agents.contracts import AgentView
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class FundamentalAgent(BaseCognitiveAgent):
    """负责从基本面角度分析的 Agent。"""

    def __init__(self, model_gateway: ModelGateway):
        super().__init__(model_gateway, "fundamental_agent", "fundamental")

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
            assumptions=view_data.assumptions,
            risks=view_data.risks,
            invalidation_triggers=view_data.invalidation_triggers,
            recommended_next_checks=view_data.recommended_next_checks,
            evidence_refs=view_data.evidence_refs,
            tool_refs=view_data.tool_refs,
            memory_refs=view_data.memory_refs,
            workflow_id=view_data.workflow_id,
            evaluation=view_data.evaluation,
            metadata=view_data.metadata,
        )

    def _build_prompt(self, context: AgentContext) -> str:
        return self.build_sop_prompt(context, get_agent_sop(self.agent_role))
