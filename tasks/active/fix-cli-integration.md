# Task: Fix CLI Command Layer + Integration Test Failures

**Status:** completed ✅
**Assigned:** 鲸先锋 (Whale Vanguard)
**Started:** 2026-05-05 20:13 GMT+8
**Completed:** 2026-05-05 20:20 GMT+8

## Failed Tests (4)

1. `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_with_output_file`
2. `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_invalid_date`
3. `tests/unit/test_cli_analyze.py::TestAnalyzeCommand::test_analyze_handles_service_error`
4. `tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_vector_search_relevance`

## Root Causes & Fixes

### CLI Analyze Tests (1-3)

**Root Cause A (test_analyze_with_output_file):** Mock snapshot lacked `evidence_refs`, `event_impact`, `as_of` attributes. When `_build_sections()` ran, Pydantic's `SectionOutput` validation failed on `evidence_refs` (got `Mock` instead of `list`). The exception was caught silently, `projection.save()` was never called.

**Fix:** Added `mock_snapshot.evidence_refs = []`, `mock_snapshot.event_impact = []`, `mock_snapshot.as_of = "2026-05-05"` to the test mock.

**Root Cause B (test_analyze_invalid_date, test_analyze_handles_service_error):** The `analyze_command` used `return` on error paths, which in Click means exit_code=0. Tests expected non-zero exit codes.

**Fix:** Changed `return` to `ctx = click.get_current_context(); ctx.exit(1); return` on both error paths in `analyze.py`.

### Integration Test (4)

**Root Cause:** `InMemoryVectorStore._dummy_embedding()` used MD5 hashing to generate pseudo-embeddings. MD5 produces completely unrelated hashes for semantically similar texts, so "茅台财报" and "贵州茅台发布财报" got no similarity boost while "人工智能技术突破" could randomly rank higher.

**Fix:** Rewrote `_dummy_embedding()` to use character bigram + unigram + word-level bucketing with 256 dimensions, normalized to unit vector. This ensures texts sharing characters/words have overlapping bucket counts, producing meaningful cosine similarity.

## Files Modified

- `app/cli/commands/analyze.py` — Added `ctx.exit(1)` on invalid date and service error paths
- `tests/unit/test_cli_analyze.py` — Added missing mock attributes (`evidence_refs`, `event_impact`, `as_of`)
- `knowledge_layer/retrieval/vector_store.py` — Rewrote `_dummy_embedding()` with n-gram based embedding

## Verification

All 11 tests pass:
```
tests/unit/test_cli_analyze.py: 6 passed
tests/integration/test_end_to_end.py: 5 passed
```
