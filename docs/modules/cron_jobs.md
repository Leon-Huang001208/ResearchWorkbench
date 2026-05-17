# Module: cron_jobs

## Responsibility

`cron_jobs` provides scheduled ingestion, scheduled signal generation, and background automation.

---

## Design Rules

- Scheduled jobs should be idempotent
- Failure handling should be explicit
- Dependencies should be clear
- Add or update tests when job behavior changes

---

## Files

### `cron_jobs/*.py`

Purpose:
- Scheduled job definitions
- Automation scripts
- Background processing logic

Update this section when:
- New scheduled jobs are added
- Schedule frequency changes
- Job dependency changes
- Failure/retry behavior changes

---

## Required Tests

- Scheduling logic tests
- Mocked job execution tests
- Failure handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/cron_jobs.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`