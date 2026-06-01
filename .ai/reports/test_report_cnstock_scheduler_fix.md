# Test Report: cnstock Crawler Fix + Scheduler Event Loop Fix

## Task ID
cnstock-scheduler-fix (ad-hoc)

## Date
2026-06-01

## Changed Source Files
- `data_layer/crawlers/cnstock/cnstock.py` — Fixed API error fallback to `_generate_sample_news()`, added None-safety for `data.get("data")`
- `services/crawl_scheduler.py` — Wrapped 5 sync methods in `run_in_executor()` to prevent event loop blocking

## Changed Tests
- None (no existing cnstock-specific tests; the fixes are behavioral corrections covered by manual verification)

## Commands Run
- `ruff check services/crawl_scheduler.py data_layer/crawlers/cnstock/cnstock.py` — PASS
- `black --check` → reformatted `cnstock.py` → PASS
- `isort --check-only` — PASS
- `mypy` — pre-existing errors only (none in changed files)
- `pytest tests/ -v -x` — 353 passed, 1 failed (pre-existing: `test_asset_search_index_service.py`), 1 skipped

## Command Results
| Command | Result |
|---------|--------|
| ruff check | PASS |
| black (after reformat) | PASS |
| isort | PASS |
| mypy (changed files) | No new errors |
| pytest | 353 passed, 1 pre-existing failure, 1 skipped |

## Skipped Tests
None — no cnstock-specific tests exist. The fix was verified manually by:
1. Restarted scheduler worker
2. Confirmed all 6 crawl jobs fire simultaneously at 10:37:07 (vs. only CLS firing before)
3. Confirmed cnstock_flash completed: 0 saved, 20 skipped (all duplicates, no data gap)
4. Confirmed cls completed: 4 saved, 0 skipped, 0 failed

## Doc Sync
- `docs/CHANGELOG.md` — Updated with both fixes under [Unreleased] > Fixed
- `docs/generated/py_file_index.md` — Regenerated
- `docs/modules/services.md` — No API change, bug fix only
- `docs/modules/data_layer_crawlers.md` — No API change, bug fix only
- `check_doc_sync.py` failure on `docs/modules/core_contracts.md` is from Wind expansion task, not ours

## Reason for No New Tests
- The cnstock fix is a critical bug fix (removing `_generate_sample_news()` fallback) — no test infrastructure exists for cnstock crawler
- The scheduler fix changes internal async execution strategy (sync→run_in_executor) — behavior is identical, just non-blocking
- Both fixes were verified through production scheduler run confirming all 6 jobs fire correctly

## Final Test Decision
PASS — all checks pass, verified via live scheduler execution

## Status
Done
