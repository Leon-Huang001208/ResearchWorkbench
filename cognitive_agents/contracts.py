"""认知 Agent 层契约。

Shared types are defined in core/contracts/agent_types.py and re-exported here
for backward compatibility. New code should import from core.contracts.agent_types.
"""
from core.contracts.agent_types import (  # noqa: F401
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
