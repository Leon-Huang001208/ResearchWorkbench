# AF-AUTO-001: Proposal - Follow-up Tasks

**Task Set ID**: af-auto-001  
**Based On**: AF-AUTO-000 Findings  
**Status**: Proposal

---

## Executive Summary

This task set addresses the remaining issues identified during AF-AUTO-000, focusing on fixing failing tests, improving test coverage, and completing the remaining TODO items in the reasoning layer.

---

## Task Breakdown

### High Priority Tasks

#### af-auto-001-01: Fix Failing Tests
- **Description**: Fix the 70 failing tests from the baseline
- **Priority**: High
- **Dependencies**: None
- **Success Criteria**:
  - All 840 tests pass
  - Pass rate: 100%
- **Report Location**: `.ai/reports/failing_tests_fixed.md`

#### af-auto-001-02: Add Quick-Win Tests (Phase 1)
- **Description**: Add the 5 quick-win tests identified in AF-AUTO-000-10
- **Priority**: High
- **Dependencies**: af-auto-001-01
- **Success Criteria**:
  - Add tests for signal_service
  - Add tests for failure_memory_service
  - Add tests for outcome_service
  - Add tests for search_service
  - Add tests for report_generator
- **Report Location**: `.ai/reports/quick_win_tests_added.md`

#### af-auto-001-03: Complete Reasoning Layer TODOs
- **Description**: Implement the remaining TODO items in the reasoning layer
- **Priority**: High
- **Dependencies**: None
- **Success Criteria**:
  - Implement LLM hypothesis generation
  - Implement assertion query in evidence collector
  - Implement event query in evidence collector
  - Implement temporal correlation check in skeptic
- **Report Location**: `.ai/reports/reasoning_layer_todos_complete.md`

### Medium Priority Tasks

#### af-auto-001-04: Phase 2 - Critical Services Test Coverage
- **Description**: Add tests for high-risk core services
- **Priority**: Medium
- **Dependencies**: af-auto-001-02
- **Success Criteria**:
  - Add tests for paper_trading_service
  - Add tests for monitoring_service
  - Add tests for replay_service
  - Add tests for closed_loop_service
  - Add tests for governance_service
  - Coverage improves by 10%
- **Report Location**: `.ai/reports/phase2_coverage_improvement.md`

#### af-auto-001-05: Phase 3 - Knowledge Layer Test Coverage
- **Description**: Add tests for knowledge layer modules
- **Priority**: Medium
- **Dependencies**: af-auto-001-04
- **Success Criteria**:
  - Add tests for entity resolution
  - Add tests for assertion extraction
  - Add tests for event extraction
  - Add tests for graph projection
  - Add tests for retrieval (hybrid search & vector store)
- **Report Location**: `.ai/reports/phase3_coverage_improvement.md`

#### af-auto-001-06: Phase 4 - All Remaining Coverage
- **Description**: Add tests for remaining modules to reach 75% coverage
- **Priority**: Medium
- **Dependencies**: af-auto-001-05
- **Success Criteria**:
  - Overall test coverage reaches 75%
  - All critical modules have test coverage
  - Test coverage report created
- **Report Location**: `.ai/reports/phase4_coverage_complete.md`

---

## Expected Outcomes

### Overall Goals
1. 100% test pass rate (840/840)
2. 75%+ overall test coverage
3. Reasoning layer at 100% completion
4. All audit TODOs addressed

### Deliverables
- 100% passing tests
- 75%+ coverage report
- Complete reasoning layer implementation
- Additional tests for all layers

---

## Task Metadata

| Category | Count |
|----------|-------|
| High Priority | 3 |
| Medium Priority | 3 |
| **Total** | **6** |

---

## Dependencies Flow

```
af-auto-001-01 (fix failing tests)
  └── af-auto-001-02 (quick-win tests)
        └── af-auto-001-04 (phase 2 coverage)
              └── af-auto-001-05 (phase 3 coverage)
                    └── af-auto-001-06 (phase 4 coverage)

af-auto-001-03 (reasoning TODOs) [independent]
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Test Pass Rate | 100% (840/840) |
| Test Coverage | 75%+ |
| Reasoning Layer | 100% Complete |
| All High Priority Tasks | Done |
| All Medium Priority Tasks | Done |

---

## Notes

This task set assumes that the codebase remains stable and no major architectural changes are made.
