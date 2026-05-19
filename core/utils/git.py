"""Git utilities shared by CI and task-completion check scripts."""
from __future__ import annotations

import subprocess


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def get_changed_files() -> list[str]:
    files: list[str] = []
    # tracked file modifications (unstaged + staged)
    files.extend(run_git(["diff", "--name-only"]))
    files.extend(run_git(["diff", "--cached", "--name-only"]))
    # new/untracked files not yet staged
    status_lines = run_git(["status", "--porcelain"])
    for line in status_lines:
        if line.startswith("??"):
            files.append(line[3:])  # skip "?? " prefix
    return sorted(set(files))
