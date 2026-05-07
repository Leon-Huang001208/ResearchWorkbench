"""认知 Agent 插件层。

Agent 只产出结构化观点，协作通过 CognitiveBlackboard 完成。
"""
from .blackboard import CognitiveBlackboard
from .contracts import AgentRole, AgentView, BlackboardConflict, ViewDirection
from .agents import BaseCognitiveAgent, AgentContext, AgentFactory, AgentOrchestrator

__all__ = [
    "AgentRole",
    "AgentView",
    "BlackboardConflict",
    "CognitiveBlackboard",
    "ViewDirection",
    "BaseCognitiveAgent",
    "AgentContext",
    "AgentFactory",
    "AgentOrchestrator",
]
