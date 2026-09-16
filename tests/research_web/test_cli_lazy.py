import json
import logging
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner


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

    project_root = str(Path(research_workbench_entrypoint.__file__).resolve().parents[1])
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


def test_repository_launcher_ignores_shadow_package_in_calling_directory(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    launcher = project_root / "rwb"
    shadow = tmp_path / "research_workbench_entrypoint"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("", encoding="utf-8")
    (shadow / "__main__.py").write_text("print('shadow-entrypoint')\n", encoding="utf-8")

    completed = subprocess.run(
        [str(launcher), "--help"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "web" in completed.stdout
    assert "shadow-entrypoint" not in completed.stdout


def test_web_doctor_supports_safe_json_and_human_output(monkeypatch):
    from app.cli import main as cli_module

    report = {
        "schema_version": 1,
        "ok": True,
        "issues": [],
        "python": {"version": "Python 3.12.9", "lock_matches_manifest": True},
        "node": {"version": "v24.8.0"},
        "cjpy": {"version": "0.5.2", "ready": True},
        "dsh": {"ready": True},
        "services": {
            "runtime": {"port": 3081, "running": True, "healthy": True},
            "web": {"port": 8088, "running": True, "healthy": True},
        },
    }

    class Manager:
        def doctor(self):
            logging.getLogger("doctor-json-contract").warning("diagnostic warning")
            return report

    monkeypatch.setattr(cli_module, "WebServiceManager", Manager)
    json_result = CliRunner().invoke(cli_module.cli, ["web", "doctor", "--json"])
    human_result = CliRunner().invoke(cli_module.cli, ["web", "doctor"])

    assert json_result.exit_code == 0, json_result.output
    assert json.loads(json_result.stdout) == report
    assert "diagnostic warning" in json_result.stderr
    assert human_result.exit_code == 0, human_result.output
    assert "CJPY: 0.5.2" in human_result.output
    assert "DSH: ready" in human_result.output
