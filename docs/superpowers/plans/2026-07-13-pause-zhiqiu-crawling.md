# Pause Zhiqiu Crawling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable all scheduled and startup-backfill crawling for Zhiqiu reports, WeChat articles, and meeting transcripts without affecting other sources or stored data.

**Architecture:** Keep the three Zhiqiu sources registered so connectors and historical retrieval remain available, but set each immutable `SourceSpec.enabled` flag to `False`. The existing registry-to-scheduler path already filters with `get_enabled()`, so a graceful scheduler restart is sufficient to remove recurring crawl, ordinary backfill, deep backfill, and startup gap-backfill jobs.

**Tech Stack:** Python 3.9, pytest, APScheduler, existing watchdog shell process

---

### Task 1: Encode the paused-source contract

**Files:**
- Modify: `tests/unit/test_source_connector_contracts.py`

- [x] **Step 1: Write the failing paused-source test and update the enabled-source expectation**

Add the three disabled-source assertions and remove the Zhiqiu entries from the dictionary that intentionally describes enabled document sources:

```python
def test_zhiqiu_sources_are_registered_but_disabled():
    from core.contracts.documents_v1 import SourceType
    from core.source_registry import get

    for source_type in (
        SourceType.ZHIQIU_REPORTS,
        SourceType.ZHIQIU_WECHAT,
        SourceType.ZHIQIU_TRANSCRIPT,
    ):
        spec = get(source_type)
        assert spec is not None
        assert spec.enabled is False
```

The enabled document-source expectation becomes:

```python
expected = {
    "cls": "telegram",
    "cnstock": "news",
    "cnstock_flash": "flash",
}
```

- [x] **Step 2: Run the focused test to verify it fails for the intended reason**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_source_connector_contracts.py::test_zhiqiu_sources_are_registered_but_disabled -v`

Expected: FAIL because each current Zhiqiu `SourceSpec.enabled` value is `True`.

### Task 2: Disable the three Zhiqiu source specs

**Files:**
- Modify: `data_sources/zhiqiu_reports.py`
- Modify: `data_sources/zhiqiu_wechat.py`
- Modify: `data_sources/zhiqiu_transcript.py`

- [x] **Step 1: Add the existing registry pause flag to each source**

Add this field beside the scheduling fields in each `SourceSpec`:

```python
enabled=False,
```

Do not change connector settings, backfill metadata, stored state, credentials, or historical files.

- [x] **Step 2: Run the source registry contract tests**

Run: `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_source_connector_contracts.py -v`

Expected: all tests PASS; the three Zhiqiu specs remain registered, while the enabled document-source set excludes them.

- [x] **Step 3: Verify scheduler configuration generation excludes Zhiqiu**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 - <<'PY'
from services.crawl_scheduler import DEFAULT_CRAWL_CONFIGS

values = {config.source_type.value for config in DEFAULT_CRAWL_CONFIGS}
blocked = {"zhiqiu_reports", "zhiqiu_wechat", "zhiqiu_transcript"}
assert values.isdisjoint(blocked), values & blocked
print("zhiqiu scheduler configs disabled")
PY
```

Expected: exit code 0 and `zhiqiu scheduler configs disabled`.

### Task 3: Reload and verify the live scheduler

**Files:**
- Runtime state only: `logs/scheduler.pid`, `logs/scheduler.heartbeat.json`, `logs/scheduler_stdout.log`

- [x] **Step 1: Record the current scheduler PID and log boundary, then send a graceful termination signal**

Run:

```bash
old_pid="$(tr -d '[:space:]' < logs/scheduler.pid)"
log_start="$(wc -l < logs/scheduler_stdout.log)"
kill -TERM "$old_pid"
```

Expected: `kill` exits 0; the watchdog retains ownership of scheduler lifecycle.

- [x] **Step 2: Confirm watchdog replaces the process**

Poll `logs/scheduler.pid` for up to 20 seconds and require a live PID different from `old_pid`.

Expected: a new `python -m workers.crawl_scheduler_worker` process is alive and its PID differs from the previous value.

- [x] **Step 3: Inspect the new scheduler's job set without starting another scheduler**

Run a read-only Python check that imports `DEFAULT_CRAWL_CONFIGS`, builds each enabled source's expected job identifiers, and asserts none contains `zhiqiu_reports`, `zhiqiu_wechat`, or `zhiqiu_transcript`. Then check the heartbeat timestamp is fresh.

Expected: exit code 0, fresh heartbeat, no Zhiqiu configurations.

- [x] **Step 4: Check post-reload logs for accidental Zhiqiu task startup**

Inspect only lines after the saved `log_start` boundary for `Running scheduled ZQ`, `Running scheduled crawl for SourceType.ZHIQIU`, or `[startup] zhiqiu_`.

Expected: no matches; existing historical log entries are left intact.

### Task 4: Final verification and focused commit

**Files:**
- Modify: `tests/unit/test_source_connector_contracts.py`
- Modify: `data_sources/zhiqiu_reports.py`
- Modify: `data_sources/zhiqiu_wechat.py`
- Modify: `data_sources/zhiqiu_transcript.py`

- [x] **Step 1: Run formatting and focused tests**

Run:

```bash
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 -m pytest tests/unit/test_source_connector_contracts.py -v
git diff --check -- tests/unit/test_source_connector_contracts.py data_sources/zhiqiu_reports.py data_sources/zhiqiu_wechat.py data_sources/zhiqiu_transcript.py
```

Expected: pytest reports zero failures and `git diff --check` exits 0 with no output.

- [x] **Step 2: Review the exact scoped diff**

Run: `git diff -- tests/unit/test_source_connector_contracts.py data_sources/zhiqiu_reports.py data_sources/zhiqiu_wechat.py data_sources/zhiqiu_transcript.py`

Expected: only the paused-source test, enabled-source expectation update, and three `enabled=False` fields appear.

- [x] **Step 3: Commit only the pause changes**

Run:

```bash
git add tests/unit/test_source_connector_contracts.py data_sources/zhiqiu_reports.py data_sources/zhiqiu_wechat.py data_sources/zhiqiu_transcript.py
git commit -m "chore: pause zhiqiu data sources"
```

Expected: a new commit containing exactly the four scoped files; unrelated dirty-worktree files remain untouched.
