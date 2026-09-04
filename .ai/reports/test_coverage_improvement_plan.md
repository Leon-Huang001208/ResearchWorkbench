# Test Coverage Improvement Plan - rwb-auto-000-10

**Task ID**: rwb-auto-000-10
**Date**: 2026-05-11
**Status**: Complete

---

## Executive Summary

Based on the baseline test results:
- **Current Coverage**: 49% (18,934 total lines, 9,731 missing)
- **Total Tests**: 840 (765 passed, 70 failed, 5 errors)
- **Pass Rate**: 91%

This plan provides a prioritized roadmap to improve test coverage to 75%+ and address critical testing gaps.

---

## Baseline Analysis

### Modules with Tests (7/43 Core Services)

| Module | Status | Notes |
|--------|--------|-------|
| `asset_analysis_service.py` | ✓ Tested | `test_asset_analysis_service.py` |
| `ingest_service.py` | ✓ Tested | `test_ingest_service.py` |
| `pipeline_service.py` | ✓ Tested | Indirect coverage |
| `review_service.py` | ✓ Tested | `test_cli_review.py` |
| `scenario_service.py` | ✓ Tested | `test_cli_scenario.py` |

### Modules Missing Tests (36/43 Core Services)

High Priority Critical Services:
- `paper_trading_service.py` (34KB, high risk)
- `monitoring_service.py` (25KB, high risk)
- `replay_service.py` (26KB, high risk)
- `asset_analysis_service.py` (27KB, tested ✓)
- `closed_loop_service.py` (22KB, high risk)
- `governance_service.py` (19KB, high risk)
- `portfolio_service.py` (20KB, high risk)
- `rag_retrieval.py` (23KB, high risk)

Medium Priority Services:
- `dashboard_service.py` (13KB)
- `document_chunker.py` (14KB)
- `document_classifier.py` (16KB)
- `taxonomy_service.py` (14KB)
- `thesis_review_service.py` (14KB)
- `event_extractor.py` (11KB)
- `news_feature_service.py` (10KB)

Lower Priority Services (22):
- `audit_service.py`, `crawl_orchestrator.py`, `crawl_scheduler.py`, etc.

---

## Prioritized Roadmap

### Phase 1: Quick Wins (0-2 Weeks) - Target: 55% Coverage

**Goal**: Add tests for highest risk, easiest to test modules.

| Priority | Module | Effort | Coverage Goal |
|----------|--------|--------|---------------|
| 1 | `signal_service.py` | Low | Add unit tests for signal CRUD |
| 2 | `failure_memory_service.py` | Low | Add unit tests for failure tracking |
| 3 | `outcome_service.py` | Low | Add unit tests for outcome management |
| 4 | `search_service.py` | Low | Add unit tests for search functionality |
| 5 | `report_generator.py` | Low | Add unit tests for report generation |

**Quick Win Actions**:
- Fix the 70 failing tests first (91% → 100% pass rate)
- Add tests for 5 simplest missing service tests
- Estimated coverage gain: +6%

### Phase 2: Critical Services (2-4 Weeks) - Target: 65% Coverage

**Goal**: Test high-risk business logic modules.

| Priority | Module | Effort | Coverage Goal |
|----------|--------|--------|---------------|
| 1 | `paper_trading_service.py` | High | Full unit + integration tests |
| 2 | `monitoring_service.py` | Medium | Unit tests for core monitoring |
| 3 | `replay_service.py` | High | Unit + integration tests |
| 4 | `closed_loop_service.py` | High | Unit tests for closed loop logic |
| 5 | `governance_service.py` | Medium | Unit tests for governance rules |
| 6 | `portfolio_service.py` | Medium | Unit tests for portfolio logic |
| 7 | `rag_retrieval.py` | Medium | Unit tests for retrieval logic |

**Phase 2 Actions**:
- Add comprehensive tests for 7 critical services
- Add integration tests for service interactions
- Estimated coverage gain: +10%

### Phase 3: Knowledge & Reasoning Layers (4-6 Weeks) - Target: 70% Coverage

**Goal**: Test knowledge layer and reasoning layer modules.

Modules to test:
- `knowledge_layer/assertions/`
- `knowledge_layer/entity_resolution/`
- `knowledge_layer/events/`
- `knowledge_layer/graph_projection/`
- `knowledge_layer/retrieval/`
- `reasoning/evidence/`
- `reasoning/scenarios/`
- `reasoning/skeptic/`

**Phase 3 Actions**:
- Add unit tests for knowledge layer modules
- Add integration tests for reasoning flows
- Add graph data validation tests
- Estimated coverage gain: +5%

### Phase 4: Timing & Memory Learning (6-8 Weeks) - Target: 75% Coverage

**Goal**: Test timing engine and memory learning modules.

Modules to test:
- `timing_engine/models/` (10+ models)
- `timing_engine/meta.py`
- `memory_learning/journal.py`
- `memory_learning/pattern_learner.py`
- `memory_learning/persistent_journal.py`

**Phase 4 Actions**:
- Add unit tests for all timing models
- Add integration tests for meta timing engine
- Add tests for pattern learning
- Estimated coverage gain: +5%

---

## Test Strategy Recommendations

### Unit Test Strategy

**Patterns to use**:
- Arrange-Act-Assert structure
- Mock external dependencies (LLM gateway, DB, APIs)
- Use fixtures for common test data
- Parameterize tests for multiple scenarios

**What to test**:
- Happy path functionality
- Edge cases and error conditions
- Boundary values
- Validation logic
- Error handling

### Integration Test Strategy

**What to test**:
- Service-to-service interactions
- Database operations
- API endpoint workflows
- End-to-end data flows

### Test Coverage Goals

| Module Type | Target Coverage |
|-------------|-----------------|
| Core Contracts | 100% (already achieved) |
| Core Services | 80%+ |
| Signal Lab | 80%+ |
| Knowledge Layer | 70%+ |
| Reasoning Layer | 70%+ |
| Timing Engine | 70%+ |
| Memory Learning | 70%+ |

---

## Quick-Win Test Ideas

### 1. Add Test for `signal_service.py` (Low Effort)

File: `tests/unit/test_signal_service.py`

Test cases:
- Create signal with valid data
- Create signal with invalid data (validation error)
- Update existing signal
- Delete signal
- Query signals by asset
- Query signals by date range

### 2. Add Test for `failure_memory_service.py` (Low Effort)

File: `tests/unit/test_failure_memory_service.py`

Test cases:
- Record a failure
- Retrieve failures by date
- Retrieve failures by asset
- Get failure statistics
- Clear old failures

### 3. Add Test for `outcome_service.py` (Low Effort)

File: `tests/unit/test_outcome_service.py`

Test cases:
- Record a trading outcome
- Calculate win/loss ratio
- Get outcomes by signal
- Get outcomes by time period
- Calculate performance metrics

### 4. Add Test for `search_service.py` (Low Effort)

File: `tests/unit/test_search_service.py`

Test cases:
- Search documents by keyword
- Search with filters (date, source, type)
- Empty search results
- Pagination

### 5. Add Test for `report_generator.py` (Low Effort)

File: `tests/unit/test_report_generator.py`

Test cases:
- Generate markdown report
- Generate JSON report
- Report contains expected sections
- Handle missing data gracefully

---

## Failing Tests Remediation

### Prioritized Fix Order

1. **Simple Path/Config Issues** (~20 tests) - Easy to fix
2. **Database Setup Issues** (~25 tests) - Add test DB setup
3. **LLM Gateway Issues** (~15 tests) - Add mocks
4. **Type Hint Issues** (~10 tests) - Fix typing

### Fix Strategy

For failing tests:
- First, understand if the test is wrong or the code is wrong
- Prefer fixing the code over changing the test (unless test is invalid)
- Add mocks for external dependencies
- Create test-specific configuration

---

## Tools & Infrastructure

### Recommended Tools

- **pytest-cov**: Already in use, continue using
- **pytest-xdist**: Parallel test execution
- **pytest-mock**: Better mocking support
- **hypothesis**: Property-based testing for edge cases
- **pytest-watch**: Auto-reload during development

### CI/CD Integration

Recommend adding:
- Pre-commit test runs
- Coverage threshold checks (fail PR if coverage drops)
- Test parallelization
- Flaky test detection

---

## Success Metrics

| Phase | Target Coverage | Target Pass Rate |
|-------|-----------------|------------------|
| Baseline | 49% | 91% |
| Phase 1 | 55% | 100% |
| Phase 2 | 65% | 100% |
| Phase 3 | 70% | 100% |
| Phase 4 | 75% | 100% |

---

## Next Steps

1. **Immediate**: Start Phase 1 - Fix failing tests + add 5 quick-win tests
2. **This Week**: Pick 1 high-priority service from Phase 2 and start testing
3. **This Month**: Complete Phase 1 and begin Phase 2
4. **Long Term**: Execute full roadmap to reach 75% coverage

---

## Appendices

### Appendix A: Complete Missing Test Inventory

Core Services Missing Tests (36):
- `audit_service.py`
- `closed_loop_service.py`
- `crawl_orchestrator.py`
- `crawl_scheduler.py`
- `dashboard_service.py`
- `data_tier_service.py`
- `decision_console_service.py`
- `deduplication_service.py`
- `document_chunker.py`
- `document_classifier.py`
- `document_enrichment.py`
- `entity_extractor.py`
- `event_auto_signal_generator.py`
- `event_extractor.py`
- `failure_memory_service.py`
- `governance_service.py`
- `graph_data_service.py`
- `historical_replay_service.py`
- `ingestion_queue_service.py`
- `monitoring_service.py`
- `news_feature_service.py`
- `outcome_journal_service.py`
- `outcome_service.py`
- `paper_trading_service.py`
- `portfolio_service.py`
- `rag_retrieval.py`
- `raw_storage_service.py`
- `replay_service.py`
- `report_generator.py`
- `scenario_data_service.py`
- `search_service.py`
- `signal_service.py`
- `signal_validator_impl.py`
- `summary_generator.py`
- `taxonomy_service.py`
- `thesis_generator_service.py`
- `thesis_review_service.py`

### Appendix B: Test File Naming Convention

For each module `X_service.py`, create:
- `tests/unit/test_X_service.py` (unit tests)
- `tests/integration/test_X_service_integration.py` (integration tests, if needed)
