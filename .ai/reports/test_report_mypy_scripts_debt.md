# Test Report: mypy scripts debt cleanup

Date: 2026-06-04

## Scope

- Reduced script-level mypy debt in recovery, restore, import, and factor seeding utilities.
- Verified explicit-package-base mypy coverage for app code, tests, workers, and scripts.

## Commands

- `black --check .` — passed
- `isort --check-only .` — passed
- `ruff check .` — passed
- `/Users/leon/opt/anaconda3/bin/python3.11 -m mypy --explicit-package-bases app cognitive_agents connectors core data_layer ingestion knowledge_layer reporting services signal_lab storage workers tests scripts` — passed, 669 files checked
- `/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/ -q` — passed, 1619 passed, 4 skipped

## Notes

- `mypy .` is not the correct full-repo entry because standalone scripts can be discovered under duplicate module names; use `--explicit-package-bases` when including `scripts/`.
- pytest still emits existing deprecation/runtime warnings around FastAPI lifecycle handlers and mocked async publishing paths; no test failures.
