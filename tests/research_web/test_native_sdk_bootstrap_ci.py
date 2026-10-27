"""Execute the actual bootstrap Python block through its early failure boundary.

No package installation, SDK build, service, provider, or network is invoked.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def bootstrap_program(text=None):
    text = (
        text
        if text is not None
        else (ROOT / ".github/workflows/research-web-bootstrap.yml").read_text()
    )
    programs = text.split("          .venv/bin/python - <<'PY'\n")[1:]
    program = next(
        body.split("          PY\n", 1)[0] for body in programs if "native-sdk-receipt.json" in body
    )
    return textwrap.dedent(program)


def test_real_installer_public_constructor_and_fields_without_operations(tmp_path, monkeypatch):
    from scripts.setup_web import DSH_COMMIT, SetupWebInstaller

    def forbidden(*args, **kwargs):
        raise AssertionError("constructor must not run processes or install anything")

    monkeypatch.setattr(subprocess, "run", forbidden)
    installer = SetupWebInstaller(project_root=tmp_path)
    assert installer.project_root == tmp_path.resolve()
    assert installer.dsh_source == installer.data_home / "runtime" / "dsh" / DSH_COMMIT
    assert isinstance(installer.node_executable, Path)
    assert installer.venv == tmp_path / ".venv"
    assert "from scripts.setup_web import SetupWebInstaller" in bootstrap_program()


@pytest.mark.parametrize(
    "failure,stage,code,error_type",
    [
        ("runner_temp", "environment", "native_sdk_environment_failed", "AssertionError"),
        ("import", "installer_import", "native_sdk_installer_import_failed", "ImportError"),
        (
            "git",
            "candidate_preflight",
            "native_sdk_candidate_preflight_failed",
            "CalledProcessError",
        ),
    ],
)
def test_early_preflight_failure_always_persists_failed_receipt(
    tmp_path, failure, stage, code, error_type
):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if failure == "runner_temp":
        env.pop("RUNNER_TEMP", None)
    else:
        registered = tmp_path / "registered-ci-temp"
        registered.mkdir()
        env["RUNNER_TEMP"] = str(registered)
    prelude = (
        "import sys,subprocess,builtins\n"
        f"sys.path.insert(0,{str(ROOT)!r})\n"
        "_run=subprocess.run\n"
        "def no_install(args,*a,**k):\n"
        " if isinstance(args,list) and 'pip' in args:raise AssertionError('test must never install')\n"
        " return _run(args,*a,**k)\n"
        "subprocess.run=no_install\n"
    )
    if failure == "import":
        prelude += (
            "_import=builtins.__import__\n"
            "def blocked(name,*a,**k):\n"
            " if name=='scripts.setup_web':raise ImportError('synthetic-private-sentinel')\n"
            " return _import(name,*a,**k)\n"
            "builtins.__import__=blocked\n"
        )
    program = bootstrap_program()
    if sys.platform != "darwin":
        # This test proves failure persistence, not native platform acceptance.
        guard = "assert sys.platform == 'darwin', 'Native SDK contract belongs to macOS Bootstrap'"
        assert program.count(guard) == 1
        program = program.replace(guard, "assert True  # test-only platform counterfactual", 1)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    result = subprocess.run(
        [sys.executable, "-c", prelude + program],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert error_type in result.stderr
    receipt = json.loads((tmp_path / "native-sdk-receipt.json").read_text())
    assert receipt["status"] == "FAILED"
    assert (receipt["stage"], receipt["code"], receipt["error_type"]) == (stage, code, error_type)
    assert "synthetic-private-sentinel" not in json.dumps(receipt)
    assert not list(tmp_path.glob("native-sdk-preflight.json"))
    assert not (tmp_path / "native-sdk-tools-install.json").exists()
    assert not list(tmp_path.glob("rwb-native-sdk-*"))
