"""The HTTP browser fixture stays temporary, offline and outside app lifespan."""

import json
import logging
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
HELPER = PROJECT / "tests/e2e/research_web_dossiers_backend.py"
log = logging.getLogger(__name__)


def test_fixture_credentials_are_empty_and_reject_all_writes():
    fixture = runpy.run_path(str(HELPER))
    memory = fixture["MemoryCredentials"]()
    assert memory.get_password("fixture", "fixture") is None
    with pytest.raises(RuntimeError, match="fixture_credential_write_forbidden"):
        memory.set_password("fixture", "fixture", "never-installed")
    with pytest.raises(RuntimeError, match="fixture_credential_write_forbidden"):
        memory.delete_password("fixture", "fixture")


def test_fixture_self_check_uses_real_store_without_lifespan_or_native_prompts(tmp_path):
    try:
        result = subprocess.run(
            [sys.executable, str(HELPER), "--self-check", "--output", str(tmp_path)],
            cwd=PROJECT,
            env={"PATH": os.defpath, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.error("dossier_browser_fixture_failed error_type=%s", type(exc).__name__)
        pytest.fail("temporary backend fixture failed before completing its self-check")
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["self_check"] == "passed"
    assert receipt["state"]["native_prompt_calls"] == 0
    assert receipt["state"]["bound_receipts"] == 0
    assert receipt["state"]["automations"] == 0
    assert receipt["state"]["blocked_outbound"] == []
    assert (tmp_path / "backend-logs/fixture.log").is_file()
