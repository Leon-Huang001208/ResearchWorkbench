# Test Report: Test Suite Regression Fix

## Task
Fix all failing tests in the Research Workbench test suite.

## Summary
Reduced test failures from 52 failures + 5 errors → 1243 passed, 1 skipped, 3 environmental failures (E2E requiring Playwright browser + template API timeout).

## Changed Source Files
- `app/cli/commands/analyze.py` — Added required `title` field to `SectionOutput` constructions
- `core/services/ingestion_queue_service.py` — Added `source_type`/`source_name`/`title` to `CanonicalEvent` construction
- `core/services/rag_retrieval.py` — Fixed `HybridSearcher.search()` parameter names (`query_text`→`query`, `limit`→`top_k`)

## Changed Test Files (17 files)
- `tests/integration/test_end_to_end.py` — 8 CanonicalEvent fixture fixes
- `tests/integration/test_graph_integration.py` — CanonicalEvent fixture
- `tests/integration/test_pipeline_integration.py` — CanonicalEvent fixture
- `tests/unit/test_china_stock_adapter.py` — Import case fix (AKShareAdapter)
- `tests/unit/test_cli_analyze.py` — Added `get_db()` patch
- `tests/unit/test_closed_loop_service.py` — Removed invalid ORM columns
- `tests/unit/test_dashboard.py` — Rewrote mock strategy for DashboardDataRepository
- `tests/unit/test_failure_memory.py` — Unique thesis marker for isolation
- `tests/unit/test_golden_path.py` — CanonicalEvent fixture
- `tests/unit/test_markdown_projection.py` — Added `title` to SectionOutput
- `tests/unit/test_outcome_protocol.py` — Updated defaults (0.0→None)
- `tests/unit/test_pipeline_service.py` — CanonicalEvent fixtures
- `tests/unit/test_review_service.py` — CanonicalEvent fixture
- `tests/unit/test_scenario_graph_data.py` — Fixed API response assertions
- `tests/unit/test_search.py` — Rewrote for SearchRepository constructor
- `tests/unit/test_signal_detail.py` — Rewrote search tests
- `tests/unit/test_signal_lab.py` — VectorBT fallback adaptation

## Root Causes Fixed
1. **CanonicalEvent required fields**: Pydantic contract added `source_type`/`source_name`/`title` as required, but source code and test fixtures weren't updated
2. **GlobalSearchService constructor**: Changed from `session` to `search_repo` parameter
3. **DashboardService**: Now uses `DashboardDataRepository` internally
4. **SectionOutput required `title`**: New required field in contract
5. **HybridSearcher.search() API**: Parameter name mismatch in calling code
6. **SignalOutcome defaults**: Changed from `0.0` to `None`

## Commands Run
- `ruff check .` — All checks passed
- `black . --check` — 621 files unchanged
- `isort . --check-only` — Skipped 2 files, no errors
- `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/` — Pre-existing errors only (in data_layer/crawlers/zq/zhiqiu/)
- `python -m pytest tests/ --ignore=tests/e2e --ignore=tests/test_template_api.py -v` — 1243 passed, 1 skipped
- `python scripts/generate_py_file_index.py` — Generated
- `python scripts/check_doc_sync.py` — Failed (see below)

## Doc Sync Justification
The three source file changes are internal bug fixes that do NOT change any public API, CLI command behavior, or module responsibility:
- `analyze.py`: Added `title` parameter to internal `SectionOutput()` calls — no CLI change
- `ingestion_queue_service.py`: Added required fields to `CanonicalEvent()` — internal normalization, no API change
- `rag_retrieval.py`: Fixed internal method parameter names — no API change

`docs/CHANGELOG.md` updated with `[Unreleased] > Fixed` entry.
`docs/generated/py_file_index.md` regenerated (no structural changes).

## Skipped/Environmental Failures
- `tests/e2e/test_asset_search.py` — Requires Playwright browser (environmental)
- `tests/e2e/test_sse_realtime.py` — Requires Playwright browser (environmental)
- `tests/test_template_api.py` — httpx.ReadTimeout (needs live dev server)

## Final Test Decision
- All unit and integration tests pass ✅
- E2E tests skipped (require browser environment)
- Ready for merge
