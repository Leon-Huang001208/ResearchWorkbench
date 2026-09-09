import subprocess
import sys
from pathlib import Path


def test_web_help_does_not_import_legacy_research_stack():
    project_root = Path(__file__).resolve().parents[2]
    script = """
import sys
from click.testing import CliRunner
from app.cli.main import cli

assert "services.ask_factory" not in sys.modules
result = CliRunner().invoke(cli, ["--help"])
assert result.exit_code == 0, result.output
assert "web" in result.output
assert "migrate-research-data" in result.output
assert "services.ask_factory" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_stable_entrypoint_prioritizes_current_repository(monkeypatch):
    import research_workbench_entrypoint

    project_root = str(
        Path(research_workbench_entrypoint.__file__).resolve().parents[1]
    )
    monkeypatch.setattr(sys, "path", ["/sibling-project", *sys.path])

    class StopAfterImport(RuntimeError):
        pass

    monkeypatch.setattr(
        "app.cli.main.cli",
        lambda *args, **kwargs: (_ for _ in ()).throw(StopAfterImport),
    )
    try:
        research_workbench_entrypoint.main()
    except StopAfterImport:
        pass

    assert sys.path[0] == project_root


def test_repository_launcher_does_not_depend_on_editable_site_path():
    project_root = Path(__file__).resolve().parents[2]
    launcher = project_root / "rwb"

    completed = subprocess.run(
        [str(launcher), "--help"],
        cwd=project_root,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "/missing-project"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "web" in completed.stdout
