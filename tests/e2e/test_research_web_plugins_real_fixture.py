"""Isolated subprocess regression for the actual offline plugin Host/SDK lane."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Seatbelt")
def test_real_plugin_host_sdk_lifecycle(tmp_path):
    checkout = Path(__file__).resolve().parents[2]
    root = tmp_path / "state"
    environment = {
        "PATH": os.defpath,
        "PYTHONPATH": str(checkout),
        "PYTHONIOENCODING": "utf-8",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(checkout / "tests/e2e/research_web_plugins_fixture.py"),
            "--root",
            str(root),
            "--verify",
        ],
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    (tmp_path / "fixture-subprocess.log").write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, (completed.stdout + completed.stderr)[-2500:]
    evidence = json.loads((root / "lifecycle-evidence.json").read_text())
    assert evidence["status"] == "passed"
    assert evidence["audit"]["model_prompts"] == 0
    assert evidence["audit"]["host"] == "SDKHost"
    assert "actual-child" in json.dumps(evidence["real_sdk_result"])
