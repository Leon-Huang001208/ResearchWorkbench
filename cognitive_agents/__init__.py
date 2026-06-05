"""认知 Agent 插件层。

Agent 只产出结构化观点，协作通过 CognitiveBlackboard 完成。
"""
from .agents import AgentContext, AgentFactory, AgentOrchestrator, BaseCognitiveAgent
from .blackboard import CognitiveBlackboard
from .committee import CommitteeSynthesisService
from .contracts import (
    AgentRole,
    AgentSOP,
    AgentView,
    AgentWorkflow,
    AgentWorkflowResult,
    AgentWorkflowStage,
    BlackboardConflict,
    CommitteeSynthesis,
    EvidenceBundle,
    EvidenceItem,
    EvidenceKind,
    EvidenceRefType,
    ViewDirection,
)
from .workflow import AgentWorkflowRunner

__all__ = [
    "AgentRole",
    "AgentSOP",
    "AgentWorkflow",
    "AgentWorkflowResult",
    "AgentWorkflowStage",
    "AgentWorkflowRunner",
    "AgentView",
    "BlackboardConflict",
    "CommitteeSynthesis",
    "CommitteeSynthesisService",
    "EvidenceBundle",
    "EvidenceItem",
    "EvidenceKind",
    "EvidenceRefType",
    "CognitiveBlackboard",
    "ViewDirection",
    "BaseCognitiveAgent",
    "AgentContext",
    "AgentFactory",
    "AgentOrchestrator",
]
