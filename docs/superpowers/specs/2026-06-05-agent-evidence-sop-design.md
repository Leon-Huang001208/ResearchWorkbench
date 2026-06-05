# Agent Evidence SOP Design

## Goal

Build the first iteration of multi-agent research discipline without replacing the existing Agent architecture.

## Scope

This design starts with layer A: stable contracts for evidence packages, agent SOPs, and richer structured Agent views. The follow-up implementation adds a minimal layer B workflow runner and layer C committee synthesis service without replacing the existing AgentOrchestrator.

## Architecture

The existing flow remains the backbone:

```text
AgentContext -> BaseCognitiveAgent -> CognitiveBlackboard -> AgentView
```

The change is to make inputs and outputs auditable:

```text
SourceDocument / Assertion / CanonicalEvent / MarketData
        -> EvidenceBundle
        -> Agent SOP prompt
        -> AgentView
        -> CognitiveBlackboard
```

## Design

`EvidenceBundle` groups source evidence, market snapshots, target, event, and prior view references. It can also be built from legacy `list[dict]` evidence so current callers are not broken.

`AgentSOP` describes what each agent should inspect and how it should reason. Macro, fundamental, and technical agents receive role-specific SOPs now. Other agents can adopt the same contract later.

`AgentView` is extended with assumptions, risks, invalidation triggers, and recommended next checks. These fields make Agent output useful for later workflow orchestration and committee synthesis.

## B/C Evolution

Layer B adds `AgentWorkflow`, `AgentWorkflowStage`, and `AgentWorkflowRunner`. The runner executes staged Agent roles, writes each view to the blackboard, stamps `workflow_id`, and returns `AgentWorkflowResult`.

Layer C adds `CommitteeSynthesis` and `CommitteeSynthesisService`. The service reads blackboard `AgentView` records and produces a deterministic committee-level summary. It does not replace per-agent SOP outputs and does not call an LLM.

## Testing

Unit tests cover contract validation, legacy evidence compatibility, SOP prompt injection, blackboard preservation of new fields, workflow execution, and committee synthesis.
