# Module: scripts

## Responsibility

`scripts` provides operational scripts, database bootstrap, backup/restore, smoke tests, and development governance checks.

---

## Design Rules

- Scripts should be self-documenting
- Provide --help for all scripts
- Make destructive operations explicit
- Add dry-run mode when feasible
- Add or update tests when script behavior changes

---

## Files

### `scripts/generate_py_file_index.py`

Purpose:
- Generates Python file index documentation
- Parses source files for classes, functions, imports
- Outputs to docs/generated/py_file_index.md

Update this section when:
- Parsing logic changes
- Output format changes
- Included directories change

### `scripts/check_task_completion.py`

Purpose:
- Verifies source changes have corresponding tests/docs/reports
- Checks git diff for changes
- Ensures CHANGELOG is updated

Update this section when:
- Check logic changes
- Required file patterns change
- Failure criteria change

### `scripts/check_doc_sync.py`

Purpose:
- Verifies source changes have corresponding documentation updates
- Maps source directories to required docs
- Ensures generated index is updated

Update this section when:
- DOC_RULES mapping changes
- Check logic changes
- Required docs change

### Other `scripts/*.py`

Purpose:
- Database bootstrap and migration
- Backup and restore operations
- Smoke tests and verification
- Data import and export
- Operational utilities

Update this section when:
- New scripts are added
- Script behavior changes
- Operational workflow changes
- Backup/restore behavior changes

---

## Required Tests

- Script behavior tests when feasible
- Dry-run mode tests
- Error path tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/scripts.md`
- `docs/REFERENCE.md` (when user-facing)
- `docs/backup_restore.md` (when backup/restore changes)
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`