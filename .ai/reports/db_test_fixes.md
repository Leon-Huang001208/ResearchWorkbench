# Database Test Fixes

**Task**: rwb-auto-001-01c (Fix database test failures)
**Date**: 2026-05-11
**Status**: Completed

## Problem

The `get_db()` function was implemented as a generator (using `yield`) for FastAPI dependency injection, but it was also being used as a context manager with `with get_db() as db:`.

Generators don't support the context manager protocol directly, causing:
```
TypeError: 'generator' object does not support the context manager protocol
```

## Solution

Created a separate `db_session` context manager class for direct use, while keeping `get_db()` unchanged for FastAPI dependency injection.

### Changes Made

1. **data_layer/repositories/base.py**:
   - Added `db_session` context manager class
   - Kept original `get_db()` generator function for FastAPI dependencies

2. **core/services/outcome_journal_service.py**:
   - Changed import from `get_db` to `db_session`
   - Replaced all `with get_db() as db:` with `with db_session() as db:`

3. **core/services/failure_memory_service.py**:
   - Changed import from `get_db` to `db_session`
   - Replaced all `with get_db() as db:` with `with db_session() as db:`

4. **tests/unit/test_bootstrap_db.py**:
   - Changed import from `get_db` to `db_session`
   - Replaced all `with get_db() as db:` with `with db_session() as db:`

5. **tests/unit/test_outcome_journal.py**:
   - Changed import from `get_db` to `db_session`
   - Replaced all `with get_db() as db:` with `with db_session() as db:`

6. **tests/scripts/test_minimal_reingest.py**:
   - Changed import from `get_db` to `db_session`
   - Replaced all `with get_db() as db:` with `with db_session() as db:`

## Test Results

### Before
```
FAILED tests/unit/test_failure_memory.py::test_retrieve_similar_cases
FAILED tests/unit/test_failure_memory.py::test_retrieve_similar_failures
FAILED tests/unit/test_failure_memory.py::test_retrieve_similar_successes
FAILED tests/unit/test_failure_memory.py::test_get_all_categorized_failures
FAILED tests/unit/test_bootstrap_db.py::test_bootstrap_idempotent
```

### After
```
12 passed, 10 warnings in 2.39s
```

All database-related tests are now passing!
