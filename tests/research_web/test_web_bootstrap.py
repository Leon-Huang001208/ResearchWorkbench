"""Dependency-free diagnostics for a missing or broken Web environment."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from research_workbench_entrypoint import web_bootstrap
from research_workbench_entrypoint.web_contract import HttpFact, ProcessFact


def _run_capture(argv: list[str], project_root: Path) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = web_bootstrap.run(argv, project_root=project_root)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _environment_marker(project_root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "owner": "research-workbench-web-installer",
        "project_root_sha256": hashlib.sha256(str(project_root.resolve()).encode()).hexdigest(),
        "python": "Python 3.12.13",
        "created_at": "2026-09-29T12:00:00+00:00",
    }


def _write_environment(project_root: Path, *, executable: bool, marker: bool = True) -> Path:
    interpreter = project_root / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("fixture", encoding="utf-8")
    interpreter.chmod(0o755 if executable else 0o644)
    if marker:
        (project_root / ".venv" / ".rwb-web-environment.json").write_text(
            json.dumps(_environment_marker(project_root)), encoding="utf-8"
        )
    return interpreter


@pytest.mark.parametrize(
    ("arrange", "expected"),
    [
        ("missing", "python_environment_missing"),
        ("incomplete", "python_environment_incomplete"),
        ("unusable", "python_environment_unusable"),
    ],
)
def test_doctor_json_classifies_broken_python_without_disclosing_paths(
    tmp_path: Path,
    arrange: str,
    expected: str,
) -> None:
    project_root = tmp_path / "private-checkout"
    project_root.mkdir()
    if arrange == "incomplete":
        (project_root / ".venv").mkdir()
    elif arrange == "unusable":
        _write_environment(project_root, executable=False)

    exit_code, stdout, stderr = _run_capture(["web", "doctor", "--json"], project_root)

    report = json.loads(stdout)
    assert exit_code == 0
    assert report["schema_version"] == 2
    assert report["ok"] is False
    assert report["installation_ok"] is False
    assert report["product_ready"] is False
    assert report["model_ready"] is False
    assert report["issues"] == [expected]
    assert "warnings" in report
    assert set(report["services"]) == {"runtime", "web"}
    assert str(tmp_path) not in stdout
    assert stderr == ""


def test_doctor_honors_safe_launcher_probe_failure_override(tmp_path: Path) -> None:
    _write_environment(tmp_path, executable=True)

    report = web_bootstrap.diagnose(
        tmp_path,
        environment={"RWB_BOOTSTRAP_PYTHON_ISSUE": "python_environment_unusable"},
    )

    assert report["issues"][0] == "python_environment_unusable"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["web"],
        ["web", "start"],
        ["web", "restart"],
        ["web", "stop"],
        ["web", "status", "--json"],
        ["web", "doctor", "--verbose"],
        ["web", "doctor", "--json", "extra"],
        ["--help"],
    ],
)
def test_bootstrap_rejects_every_command_outside_the_exact_allowlist(
    tmp_path: Path,
    argv: list[str],
) -> None:
    exit_code, stdout, stderr = _run_capture(argv, tmp_path)

    assert exit_code == 1
    assert stdout == ""
    assert "python_environment_missing" in stderr
    assert "./setup-web.sh --repair --no-start" in stderr
    assert "setup-web.cmd --repair --no-start" in stderr
    assert str(tmp_path) not in stderr


@pytest.mark.parametrize(
    "argv",
    [["web", "status"], ["web", "doctor"], ["web", "doctor", "--json"]],
)
def test_bootstrap_allowlist_commands_are_read_only_and_exit_zero_with_issues(
    tmp_path: Path,
    argv: list[str],
) -> None:
    exit_code, stdout, stderr = _run_capture(argv, tmp_path)

    assert exit_code == 0
    assert "python_environment_missing" in stdout
    assert stderr == ""


def _service_state(project_root: Path, data_home: Path, role: str) -> dict[str, object]:
    if role == "runtime":
        source = data_home.parent / "runtime" / "dsh" / "pinned"
        command = [
            "/python",
            "-m",
            "app.research_web.launch_runtime",
            "--source",
            str(source),
            "--data",
            str(data_home),
            "--node",
            "/node",
            "--port",
            "3081",
            "--datahub-url",
            "http://127.0.0.1:8088",
            "--research-tools",
        ]
        signature = [
            str(source / "apps/cli/lib/bin.js"),
            str(data_home / "runtime/overlay.yml"),
            "3081",
        ]
        port = 3081
    else:
        command = [
            "/python",
            "-m",
            "uvicorn",
            "app.research_web.main:app",
            "--app-dir",
            str(project_root),
            "--host",
            "127.0.0.1",
            "--port",
            "8088",
        ]
        signature = ["app.research_web.main:app", str(project_root), "8088"]
        port = 8088
    payload = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
    return {
        "version": 1,
        "role": role,
        "pid": 4242 if role == "runtime" else 4343,
        "port": port,
        "started_at": 1.0,
        "project_root": str(project_root.resolve()),
        "data_root": str(data_home),
        "command": command,
        "fingerprint": hashlib.sha256(payload.encode()).hexdigest(),
        "signature": signature,
    }


def _write_state(project_root: Path, data_home: Path, role: str) -> dict[str, object]:
    state = _service_state(project_root, data_home, role)
    run_root = data_home.parent / "run"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / f"{role}.json").write_text(json.dumps(state), encoding="utf-8")
    return state


def test_service_facts_keep_state_process_ownership_port_and_protocol_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    data_home = tmp_path / "private" / "research-web"
    runtime = _write_state(project_root, data_home, "runtime")
    web = _write_state(project_root, data_home, "web")

    def process(pid: int) -> ProcessFact:
        state = runtime if pid == runtime["pid"] else web
        return ProcessFact("alive", " ".join(state["signature"]), None)

    monkeypatch.setattr(web_bootstrap, "probe_process", process)
    monkeypatch.setattr(web_bootstrap, "port_listening", lambda _port: True)
    monkeypatch.setattr(
        web_bootstrap,
        "http_get",
        lambda _port, path: HttpFact(
            200,
            "application/javascript" if path.endswith(".mjs") else "text/html; charset=utf-8",
            b"ignored",
            None,
        ),
    )

    services = web_bootstrap.bootstrap_service_facts(project_root, data_home)

    assert services["runtime"] == {
        "state": "valid",
        "process": "alive",
        "ownership": "owned",
        "port_state": "listening",
        "protocol": "not_run",
        "ready": False,
        "running": True,
        "healthy": False,
        "pid": 4242,
        "port": 3081,
        "issues": [],
    }
    assert services["web"] == {
        "state": "valid",
        "process": "alive",
        "ownership": "owned",
        "port_state": "listening",
        "protocol": "passed",
        "ready": True,
        "running": True,
        "healthy": True,
        "pid": 4343,
        "port": 8088,
        "issues": [],
    }


@pytest.mark.parametrize("content", ["not-json", "x" * (64 * 1024 + 1)])
def test_service_facts_reject_malformed_or_oversized_state_without_disclosure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: str,
) -> None:
    data_home = tmp_path / "private" / "research-web"
    run_root = data_home.parent / "run"
    run_root.mkdir(parents=True)
    (run_root / "web.json").write_text(content, encoding="utf-8")
    monkeypatch.setattr(web_bootstrap, "port_listening", lambda _port: False)

    services = web_bootstrap.bootstrap_service_facts(tmp_path, data_home)

    assert services["web"]["state"] == "invalid"
    assert services["web"]["process"] == "inaccessible"
    assert services["web"]["ownership"] == "unknown"
    assert services["web"]["pid"] is None
    assert services["web"]["issues"] == ["web_state_invalid"]
    assert str(tmp_path) not in json.dumps(services)


def test_service_facts_distinguish_dead_foreign_and_listener_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_home = tmp_path / "private" / "research-web"
    runtime = _write_state(tmp_path, data_home, "runtime")
    _write_state(tmp_path, data_home, "web")

    def process(pid: int) -> ProcessFact:
        if pid == runtime["pid"]:
            return ProcessFact("missing", None, None)
        return ProcessFact("alive", "python unrelated.py", None)

    monkeypatch.setattr(web_bootstrap, "probe_process", process)
    monkeypatch.setattr(web_bootstrap, "port_listening", lambda port: port == 3081)

    services = web_bootstrap.bootstrap_service_facts(tmp_path, data_home)

    assert services["runtime"]["process"] == "missing"
    assert services["runtime"]["ownership"] == "unknown"
    assert services["runtime"]["port_state"] == "listening"
    assert services["runtime"]["running"] is False
    assert services["runtime"]["issues"] == [
        "runtime_process_missing",
        "runtime_port_in_use_unknown",
    ]
    assert services["web"]["process"] == "alive"
    assert services["web"]["ownership"] == "foreign"
    assert services["web"]["pid"] is None
    assert services["web"]["running"] is False
    assert services["web"]["issues"] == ["web_process_foreign"]


def test_listener_without_state_is_never_reported_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_bootstrap, "port_listening", lambda _port: True)
    monkeypatch.setattr(
        web_bootstrap,
        "http_get",
        lambda _port, _path: HttpFact(200, "text/html", b"ignored", None),
    )

    services = web_bootstrap.bootstrap_service_facts(
        tmp_path, tmp_path / "private" / "research-web"
    )

    for service in services.values():
        assert service["state"] == "missing"
        assert service["process"] == "missing"
        assert service["ownership"] == "unknown"
        assert service["port_state"] == "listening"
        assert service["ready"] is False
        assert service["running"] is False
        assert service["healthy"] is False
        assert service["pid"] is None
        role = "runtime" if service["port"] == 3081 else "web"
        assert service["issues"] == [f"{role}_port_in_use_unknown"]


def test_bootstrap_diagnostics_never_unlink_kill_or_create_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_home = tmp_path / "private" / "research-web"
    state = _write_state(tmp_path, data_home, "web")
    monkeypatch.setattr(
        Path,
        "unlink",
        lambda *_args, **_kwargs: pytest.fail("bootstrap diagnostics must not unlink"),
    )
    monkeypatch.setattr(
        os,
        "kill",
        lambda *_args, **_kwargs: pytest.fail("bootstrap diagnostics must not signal"),
    )
    monkeypatch.setattr(
        web_bootstrap,
        "probe_process",
        lambda _pid: ProcessFact("missing", None, None),
    )
    monkeypatch.setattr(web_bootstrap, "port_listening", lambda _port: False)

    services = web_bootstrap.bootstrap_service_facts(tmp_path, data_home)

    assert services["web"]["process"] == "missing"
    assert json.loads((data_home.parent / "run" / "web.json").read_text()) == state


def test_proxy_warning_is_safe_and_does_not_echo_the_proxy_value(tmp_path: Path) -> None:
    secret_proxy = "http://username:secret@proxy.private:7890"

    report = web_bootstrap.diagnose(
        tmp_path,
        environment={"HTTPS_PROXY": secret_proxy, "NO_PROXY": "localhost"},
    )

    serialized = json.dumps(report)
    assert report["warnings"] == ["loopback_proxy_bypass_missing"]
    assert secret_proxy not in serialized
    assert "username" not in serialized


def _temporary_launcher_checkout(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    source_root = Path(__file__).resolve().parents[2]
    checkout = tmp_path / "checkout"
    package = checkout / "research_workbench_entrypoint"
    package.mkdir(parents=True)
    shutil.copy2(source_root / "rwb", checkout / "rwb")
    for name in ("__init__.py", "web_contract.py", "web_bootstrap.py"):
        shutil.copy2(source_root / "research_workbench_entrypoint" / name, package / name)
    binary_root = tmp_path / "bin"
    binary_root.mkdir()
    (binary_root / "python3").symlink_to(sys.executable)
    environment = {
        "PATH": f"{binary_root}:/usr/bin:/bin",
        "RESEARCH_DATA_HOME": str(tmp_path / "private" / "research-web"),
    }
    return checkout, environment


@pytest.mark.skipif(os.name == "nt", reason="POSIX launcher contract")
def test_posix_launcher_falls_back_to_bootstrap_for_an_incomplete_environment(
    tmp_path: Path,
) -> None:
    checkout, environment = _temporary_launcher_checkout(tmp_path)
    (checkout / ".venv").mkdir()

    completed = subprocess.run(
        [str(checkout / "rwb"), "web", "doctor", "--json"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    report = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert report["issues"][0] == "python_environment_incomplete"
    assert str(tmp_path) not in completed.stdout


@pytest.mark.skipif(os.name == "nt", reason="POSIX launcher contract")
def test_posix_launcher_falls_back_when_owned_interpreter_cannot_import_cli(
    tmp_path: Path,
) -> None:
    checkout, environment = _temporary_launcher_checkout(tmp_path)
    interpreter = _write_environment(checkout, executable=True)
    interpreter.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    completed = subprocess.run(
        [str(checkout / "rwb"), "web", "doctor", "--json"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    report = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert report["issues"][0] == "python_environment_unusable"
