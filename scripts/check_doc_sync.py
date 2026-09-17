#!/usr/bin/env python3
"""Check source-to-document ownership, governance, generated index and Research Web maps."""

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

# These rules map compatibility-platform Python areas to their narrow owner docs.
# Research Web uses architecture-map.json instead of this parallel table.
DOC_RULES = {
    "app/api/": ["docs/modules/app_api.md", "docs/REFERENCE.md"],
    "app/cli/": ["docs/modules/app_cli.md", "docs/REFERENCE.md"],
    "app/web/": ["docs/modules/app_web.md"],
    "core/contracts/": ["docs/modules/core_contracts.md"],
    "core/services/": ["docs/modules/core_services.md"],
    "data_layer/adapters/": ["docs/modules/data_layer_crawlers.md"],
    "data_layer/crawlers/": ["docs/modules/data_layer_crawlers.md"],
    "data_layer/parsers/": ["docs/modules/data_layer_crawlers.md"],
    "data_layer/normalizers/": ["docs/modules/data_layer_crawlers.md"],
    "data_layer/repositories/": ["docs/modules/data_layer_repositories.md", "docs/DATA_STORAGE.md"],
    "knowledge_layer/": ["docs/modules/knowledge_layer.md"],
    "reasoning/": ["docs/modules/reasoning.md"],
    "cognitive_agents/": ["docs/modules/cognitive_agents.md"],
    "timing_engine/": ["docs/modules/timing_engine.md"],
    "signal_lab/": ["docs/modules/signal_lab.md"],
    "memory_learning/": ["docs/modules/memory_learning.md"],
    "reporting/": ["docs/modules/reporting.md"],
    "storage/": ["docs/modules/storage.md", "docs/DATA_STORAGE.md"],
    "ingestion/": ["docs/modules/ingestion.md"],
    "cron_jobs/": ["docs/modules/cron_jobs.md"],
    "scripts/": ["docs/modules/scripts.md"],
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


def run_check(arguments: list[str], *, project: Path, label: str) -> int:
    result = subprocess.run(arguments, cwd=project, check=False)
    log.info("documentation_subcheck_finished check=%s status=%s", label, result.returncode)
    return 0 if result.returncode == 0 else 1


def check_research_docs(project: Path, changed: list[str]) -> int:
    arguments = [
        "node",
        str(PROJECT_ROOT / "scripts/check_research_architecture.mjs"),
        "--project",
        str(project),
    ]
    for file in changed or [ARCHITECTURE_MAP]:
        arguments.extend(["--changed-file", file])
    return run_check(arguments, project=project, label="research-architecture")


def check_governance(project: Path) -> int:
    return run_check(
        [
            "node",
            str(PROJECT_ROOT / "scripts/check_documentation_governance.mjs"),
            "--project",
            str(project),
        ],
        project=project,
        label="documentation-governance",
    )


def check_generated_index(project: Path) -> int:
    generator = project / "scripts/generate_py_file_index.py"
    if not generator.is_file():
        print("Python file index check failed: generator is missing.")
        return 1
    return run_check(
        [sys.executable, str(generator), "--check"],
        project=project,
        label="python-file-index",
    )


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
    except (OSError, ValueError) as exc:
        log.error("documentation_change_detection_failed error=%s", str(exc))
        return 1

    research_required = (project / ARCHITECTURE_MAP).exists() or any(
        file.startswith("app/research_web/") for file in changed
    )
    architecture_status = check_research_docs(project, changed) if research_required else 0
    governance_status = check_governance(project)
    index_status = check_generated_index(project)

    changed_set = set(changed)
    required_docs: set[str] = set()
    matched_source_files: list[str] = []
    for file in changed:
        if file.startswith(("docs/", ".ai/", ".claude/", ".agents/")) or not file.endswith(".py"):
            continue
        if file.startswith("app/research_web/"):
            continue
        for prefix, docs in DOC_RULES.items():
            if file.startswith(prefix):
                matched_source_files.append(file)
                required_docs.update(docs)

    missing = sorted(doc for doc in required_docs if doc not in changed_set)
    ownership_status = 0
    if missing:
        ownership_status = 1
        print("❌ Documentation ownership check failed.")
        print("\nChanged source files:")
        for file in sorted(set(matched_source_files)):
            print(f"  - {file}")
        print("\nRequired owner documents not changed:")
        for doc in missing:
            print(f"  - {doc}")

    status = architecture_status or governance_status or index_status or ownership_status
    if status:
        print("❌ Documentation sync check failed.")
        return 1
    if not changed:
        print("No changed files detected; documentation state is current.")
    else:
        print("✅ Documentation sync check passed.")
    return 0


if __name__ == "__main__":
    configure_logging()
    raise SystemExit(main())
