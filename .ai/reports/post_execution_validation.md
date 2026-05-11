
# Post-Execution Artifact Validation

**Task ID**: af-auto-000-04h
**Date**: 2026-05-11
**Status**: ✅ Complete

## Overview

Added automatic validation after Claude Code execution to ensure task artifacts are properly written.

## Problem Solved

Previously, Claude could finish chatting and say the task was complete, but:
- task.json still showed "todo" or "doing"
- progress.md wasn't updated
- No report files created

## Solution Added

### 1. New Functions

`record_original_state()` - Records task status and progress.md mtime before Claude runs

`get_task_status()` - Gets current status of a task from task.json

`task_expects_report()` - Checks if a task likely needs a report file

`find_task_report()` - Looks for report files in .ai/reports/ and .ai/tasks/

`validate_task_artifacts()` - Performs 3 key checks:

1. **Task status check** - No longer "todo" or "doing"
2. **progress.md check** - File was modified or references the task
3. **Report file check** - Report exists if expected

### 2. Validation Flow

```
execute_task()
    ↓
record_original_state()
    ↓
[... run Claude ...]
    ↓
validate_task_artifacts()
    ↓
[3 checks: status, progress, report]
    ↓
SUCCESS or ERROR: "Claude finished, but task artifacts were not written"
```

### 3. Error Message

On validation failure, prints:

```
✗ CLAUDE FINISHED, BUT TASK ARTIFACTS WERE NOT WRITTEN

Issues found:
  - Task status not updated: still 'doing'
  - progress.md not found

Please manually verify and update the task artifacts.
Then mark as done with: .ai/scripts/run-automation.sh complete <ID>
```

## Changes Made

### File: `.ai/scripts/run-automation.sh`

**Added configuration:**
- `PROGRESS_FILE` variable
- `ORIGINAL_TASK_STATUS` tracking variable
- `ORIGINAL_PROGRESS_MTIME` tracking variable

**Added functions:**
- `get_task_status()`
- `task_expects_report()`
- `find_task_report()`
- `record_original_state()`
- `validate_task_artifacts()`

**Modified functions:**
- `execute_task()` - Now records state before, validates after

### File: `.ai/tasks/task.json`

**Added task:**
- `af-auto-000-04h` - This task itself

## Usage

The validation runs automatically as part of `execute`:

```bash
.ai/scripts/run-automation.sh execute af-auto-000-XX
```

If validation fails, the script exits with code 1 and shows:

```
✗ CLAUDE FINISHED, BUT TASK ARTIFACTS WERE NOT WRITTEN
```

## Benefits

1. **No more "chat says done, repo says todo"** - Explicit error when artifacts missing
2. **Clear validation feedback** - Shows exactly what checks failed
3. **Automatic validation** - No extra steps needed
4. **Graceful handling** - Still lets user manually complete if needed

## Verification

This task itself will test the validation!

- ✓ task.json will be updated
- ✓ progress.md will be updated
- ✓ This report file exists
