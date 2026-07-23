#!/usr/bin/env python3
"""Check whether changed source files triggered required documentation updates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils.git import get_changed_files

DOC_RULES = {
    "app/api/": [
        "docs/modules/app_api.md",
        "docs/REFERENCE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "app/cli/": [
        "docs/modules/app_cli.md",
        "docs/REFERENCE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "app/web/": [
        "docs/modules/app_web.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "core/contracts/": [
        "docs/modules/core_contracts.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "core/services/": [
        "docs/modules/core_services.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "data_layer/adapters/": [
        "docs/modules/data_layer_crawlers.md",
        "docs/DATA_SOURCES.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "data_layer/crawlers/": [
        "docs/modules/data_layer_crawlers.md",
        "docs/DATA_SOURCES.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "data_layer/parsers/": [
        "docs/modules/data_layer_crawlers.md",
        "docs/DATA_SOURCES.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "data_layer/normalizers/": [
        "docs/modules/data_layer_crawlers.md",
        "docs/DATA_SOURCES.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "data_layer/repositories/": [
        "docs/modules/data_layer_repositories.md",
        "docs/DATA_STORAGE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "knowledge_layer/": [
        "docs/modules/knowledge_layer.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "reasoning/": [
        "docs/modules/reasoning.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "cognitive_agents/": [
        "docs/modules/cognitive_agents.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "timing_engine/": [
        "docs/modules/timing_engine.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "signal_lab/": [
        "docs/modules/signal_lab.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "memory_learning/": [
        "docs/modules/memory_learning.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "reporting/": [
        "docs/modules/reporting.md",
        "docs/REFERENCE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "storage/": [
        "docs/modules/storage.md",
        "docs/DATA_STORAGE.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "ingestion/": [
        "docs/modules/ingestion.md",
        "docs/DATA_SOURCES.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "cron_jobs/": [
        "docs/modules/cron_jobs.md",
        "docs/ARCHITECTURE.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
    "scripts/": [
        "docs/modules/scripts.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
    ],
}


def main() -> int:
    changed = get_changed_files()

    if not changed:
        print("No changed files detected.")
        return 0

    changed_set = set(changed)
    required_docs: set[str] = set()
    matched_source_files: list[str] = []

    for file in changed:
        if file.startswith("docs/") or file.startswith(".ai/") or file.startswith(".claude/"):
            continue

        if not file.endswith(".py"):
            continue

        for prefix, docs in DOC_RULES.items():
            if file.startswith(prefix):
                matched_source_files.append(file)
                required_docs.update(docs)

    if not matched_source_files:
        print("No source files requiring doc sync were changed.")
        return 0

    required_docs.add("docs/generated/py_file_index.md")

    missing = sorted(doc for doc in required_docs if doc not in changed_set)

    if missing:
        print("❌ Documentation sync check failed.")
        print()
        print("Changed source files:")
        for file in matched_source_files:
            print(f"  - {file}")

        print()
        print("Required documentation files not changed:")
        for doc in missing:
            print(f"  - {doc}")

        print()
        print("Update required docs, or document a justified exception in the test report.")
        return 1

    print("✅ Documentation sync check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
