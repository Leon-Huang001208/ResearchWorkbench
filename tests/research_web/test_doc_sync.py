"""The Python delivery entry must call the same portable architecture checker."""

import subprocess
import sys
from pathlib import Path


def test_doc_sync_explicit_changes_fail_closed_on_missing_architecture_map(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_doc_sync.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(tmp_path),
            "--changed-file",
            "app/research_web/ui/new.mjs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "reference_missing" in result.stdout


def test_doc_sync_git_error_is_not_a_successful_empty_change_set(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_doc_sync.py"
    result = subprocess.run(
        [sys.executable, str(script), "--project", str(tmp_path), "--base", "missing-base"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "git" in (result.stdout + result.stderr).lower()


def test_architecture_failure_never_prints_overall_doc_sync_pass(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_doc_sync.py"
    arguments = [sys.executable, str(script), "--project", str(tmp_path)]
    for file in (
        "app/research_web/ui/new.mjs",
        "scripts/helper.py",
        "docs/modules/scripts.md",
        "docs/FILE_GUIDE.md",
        "docs/CHANGELOG.md",
        "docs/generated/py_file_index.md",
    ):
        arguments.extend(["--changed-file", file])
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "sync check passed" not in result.stdout
