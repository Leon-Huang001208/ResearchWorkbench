"""Agent 工厂。"""
from typing import Callable, Dict

from cognitive_agents.agents.adversarial.bear_agent import BearAgent
from cognitive_agents.agents.adversarial.bull_agent import BullAgent
from cognitive_agents.agents.adversarial.skeptic_agent import SkepticAgent
from cognitive_agents.agents.base import BaseCognitiveAgent
from cognitive_agents.agents.cognitive.fundamental_agent import FundamentalAgent
from cognitive_agents.agents.cognitive.industry_chain_agent import IndustryChainAgent
from cognitive_agents.agents.cognitive.macro_agent import MacroAgent
from cognitive_agents.agents.cognitive.policy_agent import PolicyAgent
from cognitive_agents.agents.cognitive.sentiment_agent import SentimentAgent
from cognitive_agents.agents.cognitive.technical_agent import TechnicalAgent
from cognitive_agents.agents.information.financial_report_agent import FinancialReportAgent
from cognitive_agents.agents.information.industry_data_agent import IndustryDataAgent
from cognitive_agents.agents.information.news_agent import NewsAgent
from cognitive_agents.agents.information.social_media_agent import SocialMediaAgent
from cognitive_agents.agents.validation.alpha_validation_agent import AlphaValidationAgent
from cognitive_agents.agents.validation.portfolio_agent import PortfolioAgent
from cognitive_agents.agents.validation.regime_agent import RegimeAgent
from cognitive_agents.contracts import AgentRole
from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class AgentFactory:
    """Agent 工厂类，用于创建各种 Agent 实例。"""

    def __init__(self, model_gateway: ModelGateway):
        self.model_gateway = model_gateway
        self.registry: Dict[AgentRole, Callable[[ModelGateway], BaseCognitiveAgent]] = {
            "news": NewsAgent,
            "social_media": SocialMediaAgent,
            "financial_report": FinancialReportAgent,
            "industry_data": IndustryDataAgent,
            "fundamental": FundamentalAgent,
            "technical": TechnicalAgent,
            "macro": MacroAgent,
            "industry_chain": IndustryChainAgent,
            "policy": PolicyAgent,
            "sentiment": SentimentAgent,
            "bull": BullAgent,
            "bear": BearAgent,
            "skeptic": SkepticAgent,
            "alpha_validation": AlphaValidationAgent,
            "regime": RegimeAgent,
            "portfolio": PortfolioAgent,
        }

    def create(self, role: AgentRole) -> BaseCognitiveAgent:
        """根据角色创建 Agent 实例。"""
        if role not in self.registry:
            raise ValueError(f"Unknown agent role: {role}")
        agent_class = self.registry[role]
        return agent_class(self.model_gateway)
