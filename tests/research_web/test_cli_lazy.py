import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.mark.parametrize("action", ["start", "restart"])
def test_native_public_port_options_reach_lifecycle(monkeypatch, action):
    from app.cli import main as module

    ports = []
    class Manager:
        def __init__(self, **options):
            ports.append(options)
        def start(self, **options):
            return {"services": {role: {"running": True, "healthy": True, "port": port,
                    "pid": None} for role, port in (("web", 48001), ("runtime", 48002))},
                    "url": "http://127.0.0.1:48001/#/fingpt"}
        restart = start
    monkeypatch.setattr(module, "WebServiceManager", Manager)
    output = CliRunner().invoke(module.cli, ["web", action, "--web-port", "48001",
                                           "--runtime-port", "48002", "--no-open"])
    assert output.exit_code == 0, output.output
    assert ports == [{"web_port": 48001, "runtime_port": 48002}]


def test_native_status_json_preserves_public_shape_and_hides_paths(monkeypatch):
    from app.cli import main as module

    class Manager:
        def status(self):
            return {"url": "http://127.0.0.1:8088/#/fingpt", "services": {
                role: {"running": False, "healthy": False, "pid": None, "port": port,
                       "log": "/private/SECRET.log"}
                for role, port in (("web", 8088), ("runtime", 3081))}}

    monkeypatch.setattr(module, "WebServiceManager", Manager)
    result = CliRunner().invoke(module.cli, ["web", "status", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["schema_version"] == 2 and report["mode"] == "native"
    assert report["ok"] is True and report["issues"] == []
    assert report["services"]["web"]["running"] is False
    assert report["url"] == "http://127.0.0.1:8088/#/fingpt"
    assert "SECRET" not in result.output


def test_native_web_logs_cli_options(monkeypatch):
    from app.cli import main as module
    calls = []
    class Manager:
        def logs(self, *, tail, follow):
            calls.append((tail, follow))
            return 0
    monkeypatch.setattr(module, "WebServiceManager", Manager)
    result = CliRunner().invoke(module.cli, ["web", "logs", "--tail", "7", "--follow"])
    assert result.exit_code == 0, result.output
    assert calls == [(7, True)]
    assert "logs" in CliRunner().invoke(module.cli, ["web", "--help"]).output


def _isolated_launcher(tmp_path):
    root = Path(__file__).resolve().parents[2]
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    shutil.copy2(root / "rwb", checkout / "rwb")
    shutil.copytree(root / "research_workbench_entrypoint", checkout / "research_workbench_entrypoint", ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    environment = {"HOME": str(home), "PATH": os.environ["PATH"], "PYTHONPATH": "/foreign"}
    return checkout, home, environment


def _docker_missing_environment(tmp_path, environment):
    """Give the launcher its shell tools without exposing host Docker binaries."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(sys.executable)
    for tool in ("dirname", "readlink"):
        executable = shutil.which(tool, path=os.defpath)
        if executable is None:
            pytest.fail(f"required launcher tool unavailable: {tool}")
        (bindir / tool).symlink_to(executable)
    environment["PATH"] = str(bindir)
    return bindir


def test_missing_docker_path_is_isolated_in_the_child(tmp_path):
    _, _, environment = _isolated_launcher(tmp_path)
    bindir = _docker_missing_environment(tmp_path, environment)
    completed = subprocess.run(
        [str(bindir / "python3"), "-S", "-c",
         "import json,os,shutil,sys; print(json.dumps({"
         "'path': os.environ['PATH'], 'docker': shutil.which('docker'),"
         "'click_loaded': 'click' in sys.modules}))"],
        env=environment, capture_output=True, text=True, timeout=10, check=True,
    )
    value = json.loads(completed.stdout)
    assert value == {"path": str(bindir), "docker": None, "click_loaded": False}


def test_docker_bootstrap_runs_without_site_packages_or_click(tmp_path):
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore

    checkout, home, environment = _isolated_launcher(tmp_path)
    bindir = _docker_missing_environment(tmp_path, environment)
    RuntimeModeStore(home / ".research-workbench").write("docker")
    script = (
        "import sys; from pathlib import Path; "
        "from research_workbench_entrypoint.bootstrap import dispatch; "
        "status=dispatch(['web','status','--json'], Path.cwd()); "
        "assert status == 1; "
        "assert 'click' not in sys.modules and 'app.cli.main' not in sys.modules"
    )
    completed = subprocess.run(
        [str(bindir / "python3"), "-S", "-c", script], cwd=checkout,
        env=environment, capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(completed.stdout)["issues"] == ["docker_cli_missing"]


def _mark_test_environment_owned(checkout):
    (checkout / ".venv/.rwb-web-environment.json").write_text(json.dumps({
        "schema_version": 1, "owner": "research-workbench-web-installer",
        "project_root_sha256": hashlib.sha256(str(checkout.resolve()).encode()).hexdigest(),
        "python": "Python 3.12.0", "created_at": "2026-10-05T00:00:00Z",
    }))


def test_runtime_status_without_venv_is_read_only(tmp_path):
    checkout, home, environment = _isolated_launcher(tmp_path)
    result = subprocess.run([str(checkout / "rwb"), "runtime", "status", "--json"], env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "native"
    assert not (home / ".research-workbench").exists()


@pytest.mark.parametrize("native_environment", ["missing", "unowned", "unusable"])
def test_docker_web_status_without_venv_is_stdlib_only(tmp_path, native_environment):
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore
    checkout, home, environment = _isolated_launcher(tmp_path)
    if native_environment != "missing":
        python = checkout / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("not an executable Native environment")
        if native_environment == "unusable":
            _mark_test_environment_owned(checkout)
    RuntimeModeStore(home / ".research-workbench").write("docker")
    _docker_missing_environment(tmp_path, environment)
    result = subprocess.run([str(checkout / "rwb"), "web", "status", "--json"], env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["issues"] == ["docker_cli_missing"]
    assert "Python 环境不存在" not in result.stderr


def test_native_and_legacy_exec_exact_venv_argv_environment_exit(tmp_path):
    checkout, home, environment = _isolated_launcher(tmp_path)
    python = checkout / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nif [ \"$1\" = -c ]; then exit 0; fi\nprintf '%s\\n' \"$@\"\nprintf '%s\\n' \"$PYTHONPATH\" \"$RESEARCH_NODE_BINARY\"\nexit 37\n")
    python.chmod(0o755)
    _mark_test_environment_owned(checkout)
    node = home / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node.parent.mkdir(parents=True)
    node.write_text("")
    node.chmod(0o755)
    for args in (["web", "status"], ["legacy-command", "space value", "$literal"]):
        result = subprocess.run([str(checkout / "rwb"), *args], env=environment, capture_output=True, text=True, timeout=10)
        assert result.returncode == 37, result.stderr
        assert result.stdout.splitlines() == ["-m", "research_workbench_entrypoint", *args, str(checkout) + ":/foreign", str(node)]


def test_legacy_delegation_does_not_read_unrelated_mode_record(tmp_path):
    checkout, home, environment = _isolated_launcher(tmp_path)
    python = checkout / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nif [ \"$1\" = -c ]; then exit 0; fi\nexit 37\n")
    python.chmod(0o755)
    _mark_test_environment_owned(checkout)
    record = home / ".research-workbench" / "install" / "runtime.json"
    record.parent.mkdir(parents=True, mode=0o700)
    record.write_text("corrupt")
    record.chmod(0o600)
    completed = subprocess.run([str(checkout / "rwb"), "legacy-command"], env=environment,
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 37


@pytest.mark.parametrize("prefix", [
    ["--log-level", "DEBUG"], ["--log-level=WARNING"],
    ["--log-file", "ignored.log"], ["--log-file=ignored.log"],
    ["--log-level=INFO", "--log-file", "ignored.log"],
])
@pytest.mark.parametrize("command", ["web", "runtime"])
def test_prefixed_docker_commands_without_venv(tmp_path, prefix, command):
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore
    checkout, home, environment = _isolated_launcher(tmp_path)
    RuntimeModeStore(home / ".research-workbench").write("docker")
    _docker_missing_environment(tmp_path, environment)
    completed = subprocess.run([str(checkout / "rwb"), *prefix, command, "status", "--json"],
                               env=environment, capture_output=True, text=True, timeout=10)
    value = json.loads(completed.stdout)
    assert value["mode"] == "docker"
    assert value["issues"] == (["docker_cli_missing"] if command == "web" else [])
    assert not (checkout / "ignored.log").exists()


@pytest.mark.parametrize("prefix", [
    ["--log-level"], ["--log-level="], ["--log-level", "--log-file=x"],
    ["--log-level=bogus"], ["--log-file"], ["--log-file="],
])
def test_malformed_root_options_fail_with_clean_json(tmp_path, prefix):
    checkout, _, environment = _isolated_launcher(tmp_path)
    completed = subprocess.run([str(checkout / "rwb"), *prefix], env=environment,
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["issues"] == ["runtime_root_option_invalid"]


def test_native_prefix_argv_is_preserved_exactly(tmp_path):
    checkout, _, environment = _isolated_launcher(tmp_path)
    python = checkout / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nif [ \"$1\" = -c ]; then exit 0; fi\nprintf '%s\\n' \"$@\"\nexit 37\n")
    python.chmod(0o755)
    _mark_test_environment_owned(checkout)
    args = ["--log-level=DEBUG", "--log-file", "space name.log", "web", "status"]
    completed = subprocess.run([str(checkout / "rwb"), *args], env=environment,
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 37
    assert completed.stdout.splitlines() == ["-m", "research_workbench_entrypoint", *args]


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
    from research_workbench_entrypoint import bootstrap

    monkeypatch.setattr(bootstrap, "dispatch", lambda *_args: None)

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
        "schema_version": 2,
        "ok": True,
        "installation_ok": True,
        "product_ready": False,
        "model_ready": False,
        "issues": ["web_state_invalid"],
        "warnings": ["loopback_proxy_bypass_missing"],
        "python": {"version": "Python 3.12.9", "lock_matches_manifest": True},
        "node": {"version": "v24.8.0"},
        "cjpy": {"version": "0.5.2", "ready": True},
        "dsh": {"ready": True},
        "services": {
            "runtime": {
                "state": "valid",
                "process": "alive",
                "ownership": "owned",
                "port_state": "listening",
                "protocol": "passed",
                "ready": True,
                "port": 3081,
                "running": True,
                "healthy": True,
                "pid": 101,
                "issues": [],
            },
            "web": {
                "state": "invalid",
                "process": "inaccessible",
                "ownership": "unknown",
                "port_state": "closed",
                "protocol": "not_run",
                "ready": False,
                "port": 8088,
                "running": False,
                "healthy": False,
                "pid": None,
                "issues": ["web_state_invalid"],
            },
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
    assert "Installation: ready" in human_result.output
    assert "Product: not ready" in human_result.output
    assert "Model: not ready" in human_result.output
    assert "CJPY: 0.5.2" in human_result.output
    assert "DSH: ready" in human_result.output
    assert "issues: web_state_invalid" in human_result.output
    assert "warnings: loopback_proxy_bypass_missing" in human_result.output


def test_web_status_exits_zero_with_safe_service_issues(monkeypatch):
    from app.cli import main as cli_module

    private_path = "/private/project/secret-token"

    class Manager:
        def status(self):
            return {
                "url": "http://127.0.0.1:8088/#/fingpt",
                "product_ready": False,
                "warnings": [],
                "services": {
                    "runtime": {
                        "state": "invalid",
                        "process": "inaccessible",
                        "ownership": "unknown",
                        "port_state": "closed",
                        "protocol": "not_run",
                        "ready": False,
                        "running": False,
                        "healthy": False,
                        "pid": None,
                        "port": 3081,
                        "issues": ["runtime_state_invalid"],
                        "log": private_path,
                    },
                    "web": {
                        "state": "missing",
                        "process": "missing",
                        "ownership": "unknown",
                        "port_state": "closed",
                        "protocol": "not_run",
                        "ready": False,
                        "running": False,
                        "healthy": False,
                        "pid": None,
                        "port": 8088,
                        "issues": [],
                        "log": private_path,
                    },
                },
            }

    monkeypatch.setattr(cli_module, "WebServiceManager", Manager)

    result = CliRunner().invoke(cli_module.cli, ["web", "status"])

    assert result.exit_code == 0, result.output
    assert "runtime_state_invalid" in result.output
    assert private_path not in result.output
