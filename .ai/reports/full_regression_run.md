# Full Regression Run

**任务**: rwb-auto-001-01e (Full regression run)
**日期**: 2026-05-11
**状态**: Done (partial success)

## Test Results

```
778 passed, 57 failed, 5 errors in 11.75s
```

## Comparison to Bootstrap

| Metric | Bootstrap (rwb-auto-001-bootstrap) | Now (rwb-auto-001-01e) | Improvement |
|--------|-----------------------------------|-----------------------|-------------|
| Passed | 765 | 778 | +13 |
| Failed | 70 | 57 | -13 |
| Errors | 5 | 5 | 0 |
| Pass Rate | 91.1% | 92.6% | +1.5% |

## Tests Successfully Fixed by Previous Tasks

### API Tests (rwb-auto-001-01b)
- `test_analyze_asset` - Fixed by using AsyncMock
- `test_analyze_with_as_of` - Fixed by using datetime objects

### Database Tests (rwb-auto-001-01c)
- `test_retrieve_similar_cases`
- `test_retrieve_similar_failures`
- `test_retrieve_similar_successes`
- `test_get_all_categorized_failures`
- `test_bootstrap_idempotent`
- And more database-related tests

### Signal Lab Tests (rwb-auto-001-01d)
- All 54 signal_lab tests pass (no fixes needed - they were already passing)

## Remaining Failures (57 failed, 5 errors)

### Root Cause #1: CanonicalEvent Missing Required Fields (~30+ failures)
- Missing: `source_type`, `source_name`, `title`
- Affects: ingest_service tests, integration tests, markdown/word projection, scenario graph data, etc.

### Root Cause #2: SignalOutcomeDB Missing event_type Field (~10 failures)
- Affects: outcome protocol tests, some pipeline tests

### Root Cause #3: Other Assorted Failures (~17 failures)
- Various test setup/mocking issues

## Conclusion

The regression run shows PROGRESS! We've successfully fixed 13 more tests compared to the bootstrap. The pass rate increased from 91.1% to 92.6%.

The remaining failures are mostly due to the CanonicalEvent field issue identified in the bootstrap analysis, which is a larger fix that would need its own task.
