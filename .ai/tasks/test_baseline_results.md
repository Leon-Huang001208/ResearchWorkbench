# Test Baseline Results - af-auto-000-01

**Execution Date**: 2026-05-10  
**Task**: af-auto-000-01 - Run Existing Tests to Establish Baseline

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 840 |
| Passed | 765 |
| Failed | 70 |
| Errors | 5 |
| Pass Rate | 91% |
| Test Coverage | 49% |

---

## Detailed Results

### By Test Type

| Type | Status | Count |
|------|--------|-------|
| Integration Tests | Most passed, some failed | ~ |
| Unit Tests | Mostly passed | ~ |
| Script Tests | Some failures | ~ |

### Coverage Statistics

Total lines: 18,934  
Missing lines: 9,731  
Coverage: 49%

#### High Coverage Modules (>80%)
- `core/contracts/` - 100%
- `signal_lab/backtests/event_study.py` - 88%
- `signal_lab/backtests/simple.py` - 93%
- `signal_lab/features/groups/price_volume.py` - 88%
- Many services have high coverage

#### Low Coverage Modules (<50%)
- `signal_lab/labels/event_driven.py` - 23%
- `signal_lab/features/groups/valuation.py` - 53%

---

## Common Failure Patterns

1. **LLM Gateway Related** - Some tests require real LLM API
2. **Database Initialization** - Some tests need specific environment setup
3. **File System Paths** - Some tests assume specific directory structures
4. **Type Hints Issues** - A few tests have typing-related errors

---

## Next Steps

1. Fix the lowest-hanging failures first (simple path issues, etc.)
2. Add tests for uncovered modules
3. Start working on af-auto-000-02 (core service audit)
