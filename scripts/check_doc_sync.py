#!/usr/bin/env python3
"""Check whether changed source files triggered required documentation updates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.observability import configure_logging, get_logger

log = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_MAP = "docs/architecture/research-web/architecture-map.json"

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


def collect_changes(project: Path, base: str | None = None) -> list[str]:
    """Use NUL-delimited Git output, including individual untracked files."""
    commands = [
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ]
    if base:
        commands.append(["diff", "--name-only", "-z", base, "HEAD", "--"])
    files: set[str] = set()
    for arguments in commands:
        result = subprocess.run(
            ["git", *arguments], cwd=project, capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise ValueError("git change detection failed; check project and base revision")
        files.update(filter(None, result.stdout.split("\0")))
    return sorted(files)


def check_research_docs(project: Path, changed: list[str]) -> int:
    """Invoke the repository-owned Node core used by project-constraints CI."""
    arguments = [
        "node",
        str(PROJECT_ROOT / "scripts/check_research_architecture.mjs"),
        "--project",
        str(project),
    ]
    # An unchanged document is an explicit empty-source check, not automatic Git discovery.
    for file in changed or [ARCHITECTURE_MAP]:
        arguments.extend(["--changed-file", file])
    result = subprocess.run(arguments, check=False)
    log.info("research_architecture_gate_finished status=%s", result.returncode)
    return 0 if result.returncode == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--base")
    parser.add_argument("--changed-file", action="append", default=[])
    options = parser.parse_args(argv)
    project = options.project.resolve()
    try:
        changed = options.changed_file
        if options.base or not changed:
            changed = sorted(set(changed + collect_changes(project, options.base)))
        research_required = (project / ARCHITECTURE_MAP).exists() or any(
            file.startswith("app/research_web/") for file in changed
        )
        architecture_status = check_research_docs(project, changed) if research_required else 0
    except (OSError, ValueError) as exc:
        log.error("documentation_check_failed error=%s", str(exc))
        return 1

    if not changed:
        print("No changed files detected.")
        return architecture_status

    changed_set = set(changed)
    required_docs: set[str] = set()
    matched_source_files: list[str] = []

    for file in changed:
        if file.startswith(("docs/", ".ai/", ".claude/")):
            continue

        if not file.endswith(".py"):
            continue

        for prefix, docs in DOC_RULES.items():
            if file.startswith(prefix):
                matched_source_files.append(file)
                required_docs.update(docs)

    if not matched_source_files:
        print("No source files requiring doc sync were changed.")
        return architecture_status

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

    if architecture_status:
        print("❌ Research Web architecture documentation sync check failed.")
        return architecture_status
    print("✅ Documentation sync check passed.")
    return architecture_status


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
