# Agent Evidence SOP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add evidence bundles and SOP-guided structured Agent views while preserving the current blackboard architecture.

**Architecture:** Extend shared contracts in `core/contracts/agent_types.py`, make `AgentContext` accept a typed `EvidenceBundle`, add role SOP definitions, and update macro/fundamental/technical prompts to use the common SOP prompt builder.

**Tech Stack:** Python 3.9, Pydantic v2, pytest.

---

### Task 1: Contracts

**Files:**
- Modify: `core/contracts/agent_types.py`
- Modify: `core/contracts/__init__.py`
- Modify: `cognitive_agents/contracts.py`
- Modify: `cognitive_agents/__init__.py`

- [ ] Add `EvidenceItem`, `EvidenceBundle`, and `AgentSOP`.
- [ ] Extend `AgentView` with assumptions, risks, invalidation triggers, and recommended next checks.
- [ ] Re-export new contracts from existing compatibility modules.

### Task 2: Agent Context And SOPs

**Files:**
- Modify: `cognitive_agents/agents/base.py`
- Create: `cognitive_agents/agents/sop.py`

- [ ] Add `AgentContext.evidence_bundle` while keeping legacy `evidence`.
- [ ] Add a helper that converts legacy evidence dictionaries to an `EvidenceBundle`.
- [ ] Add role-specific SOP definitions for macro, fundamental, and technical agents.
- [ ] Add a common prompt builder to `BaseCognitiveAgent`.

### Task 3: Agent Prompt Adoption

**Files:**
- Modify: `cognitive_agents/agents/cognitive/fundamental_agent.py`
- Modify: `cognitive_agents/agents/cognitive/technical_agent.py`
- Modify: `cognitive_agents/agents/cognitive/macro_agent.py`
- Modify: `cognitive_agents/blackboard.py`

- [ ] Replace duplicate prompts with the shared SOP prompt builder.
- [ ] Preserve new `AgentView` fields when blackboard memory adjusts confidence.

### Task 4: Tests

**Files:**
- Modify: `tests/unit/test_cognitive_agents.py`

- [ ] Test evidence bundle construction from legacy evidence.
- [ ] Test SOP prompt text includes role-specific steps.
- [ ] Test blackboard stores and memory-adjusts views without dropping new fields.
- [ ] Run `pytest tests/unit/test_cognitive_agents.py -q`.

### Task 5: B/C Workflow And Committee

**Files:**
- Modify: `core/contracts/agent_types.py`
- Create: `cognitive_agents/workflow.py`
- Create: `cognitive_agents/committee.py`
- Test: `tests/unit/test_agent_workflow_committee.py`

- [ ] Add `AgentWorkflowStage`, `AgentWorkflow`, `AgentWorkflowResult`, and `CommitteeSynthesis`.
- [ ] Add `AgentWorkflowRunner` to execute staged roles and write views to `CognitiveBlackboard`.
- [ ] Add `CommitteeSynthesisService` to derive a deterministic committee summary from Agent views.
- [ ] Run `pytest tests/unit/test_agent_workflow_committee.py -q`.
