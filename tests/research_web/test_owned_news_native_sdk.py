"""Mandatory built-SDK contract, selected by macOS Bootstrap after clean install.

The ordinary Checks job runs all Host compat tests without pretending it owns a
built SDK. This file never skips: an explicitly selected missing prerequisite fails.
"""

import os
import subprocess
from pathlib import Path

import test_owned_method_compat as compat

from app.research_web import RUNTIME_CONTRACT

api = compat.api


def test_native_news_wrapper_real_host_provider_and_bounded_snapshot(api, monkeypatch, tmp_path):
    configured = os.environ.get("RWB_DSH_TEST_SOURCE")
    assert configured, "RWB_DSH_TEST_SOURCE must identify the already-built fixed SDK"
    source = Path(configured).resolve(strict=True)
    actual = subprocess.check_output(
        ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "rev-parse", "HEAD"],
        cwd=source,
        text=True,
    ).strip()
    assert actual == RUNTIME_CONTRACT.dsh_commit, "Native SDK must match the current runtime pin"
    for relative in (
        "packages/core/tools/lib/index.js",
        "packages/core/system-prompt/lib/index.js",
        "vendor/cordis/lib/index.js",
    ):
        assert (source / relative).is_file(), "Native SDK must already be compiled"
    compat._native_node_executable()
    compat._exercise_native_news_wrapper_real_host_provider_and_bounded_snapshot(
        api, monkeypatch, tmp_path
    )
