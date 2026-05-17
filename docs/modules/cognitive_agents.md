# Module: cognitive_agents

## Responsibility

`cognitive_agents` provides cognitive agent contracts, blackboard write/read behavior, and multi-perspective reasoning inputs.

---

## Design Rules

- Agents should have clear, single responsibilities
- Blackboard should be transactional
- Agent outputs should be composable
- Keep agent logic testable
- Add or update tests when agent behavior changes

---

## Files

### `cognitive_agents/*.py`

Purpose:
- Agent interface definitions
- Blackboard implementation
- Multi-agent orchestration
- Perspective integration

Update this section when:
- Agent contracts change
- Blackboard schema changes
- New agent types are added
- Orchestration logic changes

---

## Required Tests

- Blackboard read/write tests
- Agent contract tests
- Multi-agent interaction tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/cognitive_agents.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`