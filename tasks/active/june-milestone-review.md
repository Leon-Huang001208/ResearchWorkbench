# June Milestone Review - Progress

## Status: completed
## Started: 2026-05-05T20:27:00+08:00
## Completed: 2026-05-05T20:48:00+08:00

## Tasks
- [x] 1. ReviewService: auto-connect SQLite repos + add event methods
- [x] 2. EventRepository: add list_by_status / get_pending_review
- [x] 3. QualityGate enhancement: summary length, entities non-empty, evidence_spans, impact_direction downgrade
- [x] 4. End-to-end integration test
- [x] 5. Unit test updates for review_service
- [x] 6. Full test suite validation

## Summary of Changes

### 1. ReviewService 闭环 (`core/services/review_service.py`)
- Auto-connects `AssertionRepositoryImpl` and `EventRepositoryImpl` via `SessionLocal()` when repos not provided
- Fixed `get_by_id` → `get` and `list_by_status` → `get_pending_review` to match actual interface
- Added `list_pending_events()`, `approve_event()`, `reject_event()` methods
- Enhanced `get_statistics()` with event counts (pending/approved/rejected)

### 2. EventRepository 增强
- Added `reviewer_status`, `reviewer`, `reviewed_at` fields to `CanonicalEvent` contract (`core/contracts/events.py`)
- Added same fields to `CanonicalEvent` DB model (`data_layer/repositories/models.py`)
- Added `get_pending_review()` and `list_by_status()` to `EventRepository` interface
- Implemented both methods in `EventRepositoryImpl`
- Updated `_to_domain` / `_to_model` / `save` to handle new fields

### 3. QualityGate 增强 (`knowledge_layer/events/quality_gate.py`)
- Summary length check (min 5 chars by default, configurable)
- Entities non-empty check
- Evidence_spans non-empty check
- Impact direction unknown penalty: reduces confidence by configurable amount (default 0.15)
- Auto-sets `reviewer_status` = "approved"/"pending" and `reviewer` = "auto_quality_gate" on process_batch
- Removed circular `event.needs_review` dependency from validation logic

### 4. IngestService 增强 (`core/services/ingest_service.py`)
- Added `assertion_repo` and `event_repo` optional params
- Saves extracted assertions and events to repos after quality gate
- Enables full ingest→extract→quality gate→review-queue pipeline

### 5. Integration Tests (`tests/integration/test_end_to_end.py`)
- Added `TestIngestToReviewEndToEnd` class with 8 tests:
  - `test_ingest_extract_and_review_queue` — full pipeline
  - `test_approve_event_from_review_queue` — approve flow
  - `test_reject_event_from_review_queue` — reject flow
  - `test_quality_gate_sets_review_status` — auto-approve vs pending
  - `test_quality_gate_summary_length_check`
  - `test_quality_gate_entities_non_empty_check`
  - `test_quality_gate_evidence_spans_check`
  - `test_quality_gate_impact_direction_unknown_penalty`

### 6. Unit Tests (`tests/unit/test_review_service.py`)
- Reorganized into 3 test classes: Basic, Events, SQLite
- Added `TestReviewServiceEvents` with 7 event-specific tests
- Added `TestReviewServiceWithSQLite` with 3 lifecycle tests using real DB
- Fixed mock repos to return proper list values for `get_pending_review()`

## Test Results
- `python -m pytest tests/integration/test_end_to_end.py -v` → 13 passed
- `python -m pytest tests/unit/test_review_service.py -v` → 21 passed
- `python -m pytest -q --ignore=tests/unit/test_signal_lab.py` → 131 passed (no regressions)
- 1 pre-existing failure in `test_signal_lab.py::test_volatility` (unrelated dirty working tree)
