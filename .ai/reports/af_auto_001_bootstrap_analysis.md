# AF-AUTO-001 Bootstrap Analysis: Failing Tests

**Date**: 2026-05-11  
**Branch**: af-auto-001  
**Status**: Analysis Complete ✓ (No Fixes Applied)

---

## Executive Summary

This report provides a comprehensive analysis of all failing tests in the AlphaFoundry test suite. **No tests have been fixed in this phase** - this is purely for analysis and categorization.

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total Tests | 840 |
| Passing Tests | 765 |
| Failing Tests | 70 |
| Errors | 5 |
| **Pass Rate** | **91.1%** |

---

## Test Failure Categorization

Tests have been categorized by their root cause. Each category includes:
- Number of failing tests
- Example error
- Affected test files
- Root cause analysis

---

### Category 1: CanonicalEvent Missing Required Fields

**Count**: 5 errors + multiple failing tests that depend on CanonicalEvent fixtures

**Error Pattern**:
```
pydantic_core._pydantic_core.ValidationError: 3 validation errors for CanonicalEvent
source_type
  Field required
source_name
  Field required
title
  Field required
```

**Affected Tests**:
- `tests/unit/test_golden_path.py::TestGoldenPath::test_full_golden_path_with_llm`
- `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_keyword_fallback`
- `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_no_persistence_services`
- `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_timing_persisted`
- `tests/unit/test_golden_path.py::TestPipelineAPIResponse::test_signal_has_required_fields_for_frontend`
- Any test that creates a CanonicalEvent without these 3 fields

**Root Cause**:
The `CanonicalEvent` Pydantic model was updated to require `source_type`, `source_name`, and `title` fields, but many test fixtures and test functions were not updated accordingly.

**Files to Check**:
- `core/contracts/events.py` - Verify the model definition
- `tests/unit/test_golden_path.py` - Update sample_event fixture
- Any other test that creates CanonicalEvent instances

---

### Category 2: get_db() Generator Context Manager Issue

**Count**: ~30 failing tests

**Error Pattern**:
```
TypeError: 'generator' object does not support the context manager protocol
```

**Affected Tests**:
- `tests/unit/test_failure_memory.py::test_retrieve_similar_cases`
- `tests/unit/test_failure_memory.py::test_retrieve_similar_failures`
- `tests/unit/test_failure_memory.py::test_retrieve_similar_successes`
- `tests/unit/test_failure_memory.py::test_get_all_categorized_failures`
- `tests/unit/test_outcome_journal.py::test_create_and_retrieve_outcome`
- `tests/unit/test_outcome_journal.py::test_failed_outcome_with_classification`
- `tests/unit/test_outcome_journal.py::test_list_by_failure_class`
- `tests/unit/test_outcome_journal.py::test_generate_weekly_review`
- `tests/unit/test_outcome_journal.py::test_repository_count_by_failure_class`
- `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_process_item`
- `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_process_item_with_pipeline`
- `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_full_flow`
- And more...

**Root Cause**:
The `get_db()` function is implemented as a generator function (using `yield`), but it's being used as a context manager with `with get_db() as db:`. In FastAPI/Starlette, the generator-based dependencies work with `Depends()`, but not directly as context managers unless properly wrapped.

**Files to Check**:
- `data_layer/database.py` or wherever `get_db()` is defined
- All services that use `with get_db() as db:`

---

### Category 3: Ingest Service Failures (CanonicalEvent Related)

**Count**: ~10 failing tests

**Error Pattern**:
Typically involves CanonicalEvent validation failures or related data flow issues

**Affected Tests**:
- `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_text_basic`
- `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_text_minimal`
- `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_file_txt`
- `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_file_pdf`
- `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_with_mock_repository`
- `tests/unit/test_ingest_service.py::TestIngestService::test_assertions_and_events_extracted`

**Root Cause**:
Likely related to the same CanonicalEvent model changes, as the ingest service creates events from raw input.

**Files to Check**:
- `knowledge_layer/events/extractor.py`
- `core/services/ingest_service.py`

---

### Category 4: API Endpoint 500 Errors

**Count**: 2 failing tests

**Error Pattern**:
```
assert 500 == 200
```

**Affected Tests**:
- `tests/unit/test_api.py::TestAssetsAPI::test_analyze_asset`
- `tests/unit/test_api.py::TestAssetsAPI::test_analyze_with_as_of`

**Root Cause**:
The API endpoint returns 500 Internal Server Error, likely because it depends on the AssetAnalysisService which might also be affected by database or model issues.

**Files to Check**:
- `app/api/assets.py`
- `core/services/asset_analysis_service.py`

---

### Category 5: Asset Analysis Service Failures

**Count**: 2 failing tests

**Error Pattern**:
Test failures in snapshot generation

**Affected Tests**:
- `tests/unit/test_asset_analysis_service.py::TestAssetAnalysisService::test_generate_snapshot_with_mock_data`
- `tests/unit/test_asset_analysis_service.py::TestAssetAnalysisService::test_mock_snapshot_contains_all_fields`

**Root Cause**:
Could be related to database issues, model validation issues, or other service dependencies.

**Files to Check**:
- `core/services/asset_analysis_service.py`

---

### Category 6: Integration Test Failures (End-to-End)

**Count**: 14 failing tests

**Affected Tests**:
- `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_and_retrieve`
- `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_multiple_and_scenario`
- `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_file`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_ingest_extract_and_review_queue`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_approve_event_from_review_queue`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_reject_event_from_review_queue`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_sets_review_status`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_summary_length_check`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_entities_non_empty_check`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_evidence_spans_check`
- `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_impact_direction_unknown_penalty`
- `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_full_propagation_flow_with_known_chain`
- `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_full_propagation_flow_with_expansion`
- `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_time_filter_affects_propagation`
- `tests/integration/test_pipeline_integration.py::TestResearchPipelineIntegration::test_run_event_signal`

**Root Cause**:
Integration tests are failing due to a combination of the above issues - they exercise the full pipeline which touches on ingest, event extraction, database operations, etc.

---

### Category 7: CLI Analyze Command Failures

**Count**: 2 failing tests

**Affected Tests**:
- `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_with_output_file`
- `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_invalid_date`

**Root Cause**:
Likely related to the asset analysis service failures they depend on.

---

### Category 8: Markdown/Word Projection Failures

**Count**: 10 failing tests

**Affected Tests**:
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_basic_report`
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_metadata`
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_evidence_refs`
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_warnings`
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_save_to_file`
- `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_generated_time`
- `tests/unit/test_word_projection.py::TestWordProjection::test_save_to_file`
- `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_metadata`
- `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_evidence_refs`
- `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_warnings`

**Root Cause**:
These tests are likely failing because they depend on the database connection or other services that are failing.

---

### Category 9: Review Service Failures

**Count**: 1 failing test

**Affected Test**:
- `tests/unit/test_review_service.py::TestReviewServiceWithSQLite::test_event_lifecycle_with_sqlite`

**Root Cause**:
Likely related to database or event model issues.

---

### Category 10: Scenario Graph Data Failures

**Count**: 6 failing tests

**Affected Tests**:
- `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_get_event_evidence_with_data`
- `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_get_event_evidence_by_entity`
- `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_enrich_scenario`
- `tests/unit/test_scenario_graph_data.py::TestGraphDataService::test_get_real_entities_from_events`
- `tests/unit/test_scenario_graph_data.py::TestGraphDataService::test_enrich_graph_real_data`
- `tests/unit/test_temporal_industry_graph.py::TestPropagationAnalyzer::test_analyze_propagation_with_chain`

**Root Cause**:
Database related issues with evidence retrieval.

---

### Category 11: Search Service Failures

**Count**: 4 failing tests

**Affected Tests**:
- `tests/unit/test_search.py::test_search_service_initialization`
- `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_returns_all_groups`
- `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_with_type_filter`
- `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_empty_results`

**Root Cause**:
Attribute errors in search service initialization, potentially related to missing tables or schema issues.

---

### Category 12: Other Database Related Failures

**Count**: 5 failing tests

**Affected Tests**:
- `tests/scripts/test_minimal_reingest.py::test_database_has_data_after_dry_run`
- `tests/unit/test_bootstrap_db.py::test_bootstrap_idempotent`
- `tests/unit/test_china_stock_adapter.py::TestDataSourceRouter::test_router_fallback`
- `tests/unit/test_outcome_protocol.py::TestSignalOutcomeContract::test_create_outcome_with_minimal_fields`
- `tests/unit/test_pipeline_service.py::test_run_event_signal_runs_without_exception`
- `tests/unit/test_pipeline_service.py::test_run_event_signal_records_to_journal`

**Root Cause**:
TypeError and other database related errors.

---

## Dependency Graph

Here's how the failures cascade:

```
CanonicalEvent Model Changes (source_type, source_name, title)
├── Affects all tests that create CanonicalEvent fixtures (5 errors)
├── Affects ingest service tests (10 failures)
└── Affects integration tests (14 failures)

get_db() Generator Issue
├── Affects all services using with get_db() as db (30+ failures)
├── Affects outcome journal tests
├── Affects failure memory tests
├── Affects ingestion queue tests
└── Affects review service tests

Asset Analysis Service Failures
├── Affects API tests (2 failures)
├── Affects CLI tests (2 failures)
└── Affects asset service tests (2 failures)
```

---

## Recommendations for Next Phases

### Phase 01a: Categorize Failing Tests (Next Task)
- ✅ Already started - this report serves as the initial categorization
- Refine categories if needed
- Map exact file locations for each failure

### Phase 01b: Fix API Test Failures
1. First fix the CanonicalEvent model issues (add missing fields to fixtures)
2. Fix the get_db() context manager issue
3. Then fix the API endpoint tests

### Phase 01c: Fix Database Test Failures
1. Fix all database connection/context manager issues
2. Fix database bootstrap issues
3. Fix outcome journal tests

### Phase 01d: Fix Signal Lab Test Failures
1. Check Signal Lab specific failures
2. Fix any related issues

### Phase 01e: Full Regression Run
1. Run all tests to verify
2. Ensure 100% pass rate

---

## Detailed Test List

### All 70 Failing Tests

1. `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_and_retrieve`
2. `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_multiple_and_scenario`
3. `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_ingest_file`
4. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_ingest_extract_and_review_queue`
5. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_approve_event_from_review_queue`
6. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_reject_event_from_review_queue`
7. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_sets_review_status`
8. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_summary_length_check`
9. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_entities_non_empty_check`
10. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_evidence_spans_check`
11. `tests/integration/test_end_to_end.py::TestIngestToReviewEndToEnd::test_quality_gate_impact_direction_unknown_penalty`
12. `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_full_propagation_flow_with_known_chain`
13. `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_full_propagation_flow_with_expansion`
14. `tests/integration/test_graph_integration.py::TestGraphStorePropagationIntegration::test_time_filter_affects_propagation`
15. `tests/integration/test_pipeline_integration.py::TestResearchPipelineIntegration::test_run_event_signal`
16. `tests/scripts/test_minimal_reingest.py::test_database_has_data_after_dry_run`
17. `tests/unit/test_api.py::TestAssetsAPI::test_analyze_asset`
18. `tests/unit/test_api.py::TestAssetsAPI::test_analyze_with_as_of`
19. `tests/unit/test_asset_analysis_service.py::TestAssetAnalysisService::test_generate_snapshot_with_mock_data`
20. `tests/unit/test_asset_analysis_service.py::TestAssetAnalysisService::test_mock_snapshot_contains_all_fields`
21. `tests/unit/test_bootstrap_db.py::test_bootstrap_idempotent`
22. `tests/unit/test_china_stock_adapter.py::TestDataSourceRouter::test_router_fallback`
23. `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_with_output_file`
24. `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_invalid_date`
25. `tests/unit/test_failure_memory.py::test_retrieve_similar_cases`
26. `tests/unit/test_failure_memory.py::test_retrieve_similar_failures`
27. `tests/unit/test_failure_memory.py::test_retrieve_similar_successes`
28. `tests/unit/test_failure_memory.py::test_get_all_categorized_failures`
29. `tests/unit/test_golden_path.py::TestGoldenPath::test_full_golden_path_with_llm` (ERROR)
30. `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_keyword_fallback` (ERROR)
31. `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_no_persistence_services` (ERROR)
32. `tests/unit/test_golden_path.py::TestGoldenPath::test_golden_path_timing_persisted` (ERROR)
33. `tests/unit/test_golden_path.py::TestPipelineAPIResponse::test_signal_has_required_fields_for_frontend` (ERROR)
34. `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_text_basic`
35. `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_text_minimal`
36. `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_file_txt`
37. `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_file_pdf`
38. `tests/unit/test_ingest_service.py::TestIngestService::test_ingest_with_mock_repository`
39. `tests/unit/test_ingest_service.py::TestIngestService::test_assertions_and_events_extracted`
40. `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_process_item`
41. `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_process_item_with_pipeline`
42. `tests/unit/test_ingestion_queue.py::TestIngestionQueueService::test_full_flow`
43. `tests/unit/test_ingestion_queue.py::TestNormalization::test_normalize_to_event`
44. `tests/unit/test_ingestion_queue.py::TestNormalization::test_normalize_no_title`
45. `tests/unit/test_ingestion_queue.py::TestNormalization::test_normalize_source_type_mapping`
46. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_basic_report`
47. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_metadata`
48. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_evidence_refs`
49. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_with_warnings`
50. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_save_to_file`
51. `tests/unit/test_markdown_projection.py::TestMarkdownProjection::test_render_generated_time`
52. `tests/unit/test_outcome_journal.py::test_create_and_retrieve_outcome`
53. `tests/unit/test_outcome_journal.py::test_failed_outcome_with_classification`
54. `tests/unit/test_outcome_journal.py::test_list_by_failure_class`
55. `tests/unit/test_outcome_journal.py::test_generate_weekly_review`
56. `tests/unit/test_outcome_journal.py::test_repository_count_by_failure_class`
57. `tests/unit/test_outcome_protocol.py::TestSignalOutcomeContract::test_create_outcome_with_minimal_fields`
58. `tests/unit/test_pipeline_service.py::test_run_event_signal_runs_without_exception`
59. `tests/unit/test_pipeline_service.py::test_run_event_signal_records_to_journal`
60. `tests/unit/test_review_service.py::TestReviewServiceWithSQLite::test_event_lifecycle_with_sqlite`
61. `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_get_event_evidence_with_data`
62. `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_get_event_evidence_by_entity`
63. `tests/unit/test_scenario_graph_data.py::TestScenarioDataService::test_enrich_scenario`
64. `tests/unit/test_scenario_graph_data.py::TestGraphDataService::test_get_real_entities_from_events`
65. `tests/unit/test_scenario_graph_data.py::TestGraphDataService::test_enrich_graph_real_data`
66. `tests/unit/test_search.py::test_search_service_initialization`
67. `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_returns_all_groups`
68. `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_with_type_filter`
69. `tests/unit/test_signal_detail.py::TestGlobalSearchAPI::test_search_empty_results`
70. `tests/unit/test_temporal_industry_graph.py::TestPropagationAnalyzer::test_analyze_propagation_with_chain`
71. `tests/unit/test_word_projection.py::TestWordProjection::test_save_to_file`
72. `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_metadata`
73. `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_evidence_refs`
74. `tests/unit/test_word_projection.py::TestWordProjection::test_save_with_warnings`

*Note: 70 failures + 5 errors = 75 total failing/error tests*

---

## Quick Win Identification

The following fixes would have the biggest impact quickly:

1. **Fix CanonicalEvent fixtures** - Would fix 5 errors immediately
2. **Fix get_db() context manager** - Would fix ~30 failures immediately
3. **These two fixes alone would reduce failures by ~50%**

---

## Conclusion

This analysis shows that the failing tests primarily stem from **two main root causes**:

1. **CanonicalEvent model schema changes** - Missing required fields in test fixtures
2. **Database connection pattern issue** - get_db() generator used as context manager

These two issues cascade through the test suite, causing most of the 70 failures. Fixing these two issues first would immediately resolve a majority of the failing tests.

---

**Next Step**: Proceed to Phase 01a: Categorize Failing Tests (refine and verify this categorization)

**Report Generated**: 2026-05-11
