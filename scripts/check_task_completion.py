#!/usr/bin/env python3
"""Check whether a task changed code without tests/docs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils.git import get_changed_files

SOURCE_DIRS = [
    "app/",
    "core/",
    "data_layer/",
    "knowledge_layer/",
    "reasoning/",
    "cognitive_agents/",
    "timing_engine/",
    "signal_lab/",
    "memory_learning/",
    "reporting/",
    "storage/",
    "ingestion/",
    "cron_jobs/",
    "scripts/",
]


def is_source_py(path: str) -> bool:
    return path.endswith(".py") and any(path.startswith(prefix) for prefix in SOURCE_DIRS)


def main() -> int:
    changed = get_changed_files()

    if not changed:
        print("No changed files detected.")
        return 0

    changed_source = [file for file in changed if is_source_py(file)]
    changed_tests = [file for file in changed if file.startswith("tests/") and file.endswith(".py")]
    changed_docs = [file for file in changed if file.startswith("docs/") and file.endswith(".md")]
    changed_reports = [
        file for file in changed if file.startswith(".ai/reports/") and file.endswith(".md")
    ]
    changed_changelog = "docs/CHANGELOG.md" in changed

    failed = False

    if changed_source and not changed_tests:
        print("❌ Source Python files changed, but no tests were changed.")
        print("Changed source files:")
        for file in changed_source:
            print(f"  - {file}")
        print("Expected: add or update tests under tests/.")
        failed = True

    if changed_source and not changed_docs:
        print("❌ Source Python files changed, but no docs were changed.")
        print(
            "Expected: update docs/modules, docs/FILE_GUIDE.md, docs/ARCHITECTURE.md, or related docs."
        )
        failed = True

    if changed_source and not changed_changelog:
        print("❌ Source Python files changed, but docs/CHANGELOG.md was not updated.")
        failed = True

    if changed_source and not changed_reports:
        print("❌ Source Python files changed, but no .ai/reports/*.md report was updated.")
        print("Expected: create or update .ai/reports/test_report_<task_id>.md.")
        failed = True

    if failed:
        return 1

    print("✅ Task completion check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
