# Task: Fix Reporting + Reasoning Traces

**Status:** completed
**Assignee:** 蟹尚书 (subagent)
**Started:** 2026-05-05 20:13 GMT+8
**Completed:** 2026-05-05 20:14 GMT+8

## Subtasks
- [x] 1. Fix Word projection `NameError: name 'docx' is not defined` in `reporting/projections/word.py`
- [x] 2. Fix Pydantic V2 `.dict()` → `.model_dump()` in `reasoning/traces/writer.py`
- [x] 3. Verify tests pass

## Changes Made

### 1. `reporting/projections/word.py`
- Added `import docx as _docx_mod` at top of file with try/except protection
- Fixed `docx.shared.RGBColor(255, 0, 0)` → `from docx.shared import RGBColor; RGBColor(255, 0, 0)` inside `save()` method
  - Root cause: `save()` only did `from docx import Document`, etc. — the bare `docx` module name was not in scope when `docx.shared.RGBColor` was referenced

### 2. `reasoning/traces/writer.py`
- Changed `.dict()` / `.model_dump()` priority: now checks `model_dump` first, falls back to `dict`
- This eliminates Pydantic V2 deprecation warnings while maintaining backward compatibility

### 3. `pyproject.toml`
- No changes needed — `python-docx>=1.0.0` was already declared

## Test Results
- `pytest tests/unit/test_word_projection.py -q` → **6 passed**
- `pytest -q -k "word"` → **7 passed**
- No regressions
