"""Check the public Native bootstrap without installing or building anything."""

import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def bootstrap_command():
    workflow = (ROOT / ".github/workflows/research-web-bootstrap.yml").read_text()
    step = workflow.split("      - name: Install Web stack on macOS\n", 1)[1].split(
        "\n      - name:", 1
    )[0]
    command = next(
        line.strip()[5:] for line in step.splitlines() if line.strip().startswith("run: ")
    )
    return shlex.split(command)


def test_real_installer_public_constructor_and_fields_without_operations(tmp_path, monkeypatch):
    from scripts.setup_web import DSH_COMMIT, SetupWebInstaller, build_parser

    def forbidden(*args, **kwargs):
        raise AssertionError("constructor must not run processes or install anything")

    monkeypatch.setattr(subprocess, "run", forbidden)
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")
    assert installer.project_root == tmp_path.resolve()
    assert installer.dsh_source == installer.data_home / "runtime" / "dsh" / DSH_COMMIT
    assert isinstance(installer.node_executable, Path)
    assert installer.venv == tmp_path / ".venv"
    command = bootstrap_command()
    assert command == ["./setup-web.sh", "--no-start"]
    flags = build_parser().parse_args(command[1:])
    assert flags.runtime == "native" and flags.no_start is True


@pytest.mark.parametrize(
    "failure,code",
    [
        ("python", "python_version_unsupported"),
        ("node", "node_version_unsupported"),
        ("git", "git_missing"),
    ],
)
def test_public_preflight_failure_is_logged_without_installing(tmp_path, failure, code):
    program = textwrap.dedent(f"""
        import subprocess, sys
        from pathlib import Path
        sys.path.insert(0, {str(ROOT)!r})
        from scripts import setup_web

        root = Path.cwd()
        for name in ('python', 'node', 'git'):
            (root / name).write_text('fixture executable')
        if {failure!r} == 'git':
            (root / 'git').unlink()
        installer = setup_web.SetupWebInstaller(
            project_root=root, data_home=root / 'data',
            python_executable=root / 'python', node_executable=root / 'node',
            git_executable=root / 'git',
            version_reader=lambda _path: '3.11.9' if {failure!r} == 'python' else '3.12.13',
            node_version_reader=lambda _path: 'v20.0.0' if {failure!r} == 'node' else 'v24.19.0',
        )
        def forbidden(*args, **kwargs):
            raise AssertionError('preflight failure must not run an installation process')
        subprocess.run = forbidden
        subprocess.Popen = forbidden
        installer._prepare_data_home = forbidden
        # Isolate runtime selection; exercise the real Native install/check and
        # the public command's existing error logging in this clean process.
        setup_web.__file__ = str(root / 'scripts/setup_web.py')
        setup_web._maybe_reexec_native = lambda *_args: None
        setup_web.install_selected_runtime = lambda args, **kwargs: installer.install(start=not args.no_start)
        raise SystemExit(setup_web.main(['--no-start']))
        """)
    result = subprocess.run(
        [sys.executable, "-B", "-c", program],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 1
    assert code in result.stderr
    assert "setup_web_failed" in (tmp_path / "logs/setup-web.log").read_text()
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / "data").exists()
