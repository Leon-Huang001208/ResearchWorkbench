"""Public one-click Web bootstrap contracts."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from scripts.setup_web import DSH_COMMIT, DSH_REMOTE, SetupWebInstaller


def test_runtime_parser_defaults_to_native_and_accepts_explicit_selection() -> None:
    from scripts.setup_web import build_parser

    parser = build_parser()
    assert parser.parse_args([]).runtime == "native"
    assert parser.parse_args(["--runtime", "native"]).runtime == "native"
    docker = parser.parse_args(["--runtime", "docker", "--no-start"])
    assert docker.runtime == "docker"
    assert docker.no_start is True


def test_docker_install_writes_summary_and_mode_only_after_verified_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "requirements").mkdir()
    (project / "requirements/web.lock").write_text("locked\n", encoding="utf-8")
    (project / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    environment = project / ".venv"
    environment.mkdir()
    sentinel = environment / "user.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(setup_web.Path, "home", classmethod(lambda _cls: home))
    events: list[tuple[str, object]] = []

    def build(_controller: object) -> dict[str, object]:
        events.append(("build", None))
        assert not (home / ".research-workbench/install/docker-manifest.json").exists()
        assert RuntimeModeStore(home / ".research-workbench").read().mode == "native"
        return {"ok": True, "issues": [], "image_id": "sha256:" + "a" * 64}

    def start(_controller: object, *, open_browser: bool = True) -> dict[str, object]:
        events.append(("start", open_browser))
        return {"ok": True, "issues": []}

    monkeypatch.setattr(setup_web._DockerRuntimeController, "install", build)
    monkeypatch.setattr(setup_web._DockerRuntimeController, "start", start)
    monkeypatch.setattr(
        SetupWebInstaller,
        "prepare_environment",
        lambda *_args, **_kwargs: pytest.fail("Docker must not prepare Native .venv"),
    )

    arguments = setup_web.build_parser().parse_args(["--runtime", "docker", "--no-start"])
    summary = setup_web.install_selected_runtime(arguments, project_root=project)

    assert events == [("build", None)]
    assert summary["status"] == "installed"
    assert summary["image_id"] == "sha256:" + "a" * 64
    assert RuntimeModeStore(home / ".research-workbench").read().mode == "docker"
    persisted = json.loads(
        (home / ".research-workbench/install/docker-manifest.json").read_text(encoding="utf-8")
    )
    assert persisted["image_id"] == summary["image_id"]
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_docker_failed_build_preserves_native_mode_and_previous_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    data_home = home / ".research-workbench"
    record = RuntimeModeStore(data_home).write("native")
    summary_path = data_home / "install/docker-manifest.json"
    summary_path.write_text('{"previous":true}\n', encoding="utf-8")
    summary_path.chmod(0o600)
    monkeypatch.setattr(setup_web.Path, "home", classmethod(lambda _cls: home))

    monkeypatch.setattr(
        setup_web._DockerRuntimeController,
        "install",
        lambda _self: {"ok": False, "issues": ["docker_build_failed"]},
    )
    arguments = setup_web.build_parser().parse_args(["--runtime", "docker", "--repair"])
    with pytest.raises(RuntimeError, match="^docker_build_failed$"):
        setup_web.install_selected_runtime(arguments, project_root=tmp_path)

    assert RuntimeModeStore(data_home).read() == record
    assert json.loads(summary_path.read_text(encoding="utf-8")) == {"previous": True}


def test_docker_check_only_is_read_only_and_outputs_safe_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web

    project = tmp_path / "checkout"
    (project / "scripts").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    monkeypatch.setattr(setup_web.Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setattr(setup_web, "__file__", str(project / "scripts/setup_web.py"))
    monkeypatch.setattr(setup_web, "_configure_logging", lambda _root: None)

    class RecordingDocker:
        def __init__(self, *_args) -> None:
            pass

        def preflight(self, *, require_image: bool = True) -> dict[str, object]:
            assert require_image is False
            return {"schema_version": 1, "ok": True, "issues": [], "mode": "docker"}

        def install(self) -> None:
            pytest.fail("check-only must not build")

    monkeypatch.setattr(setup_web, "DockerRuntime", RecordingDocker, raising=False)
    captured = StringIO()
    with redirect_stdout(captured):
        assert setup_web.main(["--runtime", "docker", "--check-only"]) == 0
    output = captured.getvalue()
    assert json.loads(output)["mode"] == "docker"
    assert str(tmp_path) not in output
    assert not (home / ".research-workbench").exists()
    assert not (project / "logs").exists()


@pytest.mark.parametrize(
    "code",
    [
        "docker_cli_missing",
        "docker_daemon_unavailable",
        "docker_compose_missing",
        "docker_architecture_unsupported",
        "docker_data_home_unsafe",
        "docker_port_8088_occupied",
        "docker_port_3081_conflict",
        "docker_ownership_mismatch",
        "docker_build_not_ready",
    ],
)
def test_docker_check_only_keeps_stable_codes_and_strips_unsafe_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    from scripts import setup_web

    project = tmp_path / "checkout"
    (project / "scripts").mkdir(parents=True)
    monkeypatch.setattr(setup_web, "__file__", str(project / "scripts/setup_web.py"))

    class FailingDocker:
        def __init__(self, *_args) -> None:
            pass

        def preflight(self, *, require_image: bool = True) -> dict[str, object]:
            assert require_image is False
            return {"ok": False, "issues": [code], "unsafe_path": str(tmp_path)}

    monkeypatch.setattr(setup_web, "DockerRuntime", FailingDocker)
    captured = StringIO()
    with redirect_stdout(captured):
        assert setup_web.main(["--runtime", "docker", "--check-only"]) == 1
    output = captured.getvalue()
    assert json.loads(output)["issues"] == [code]
    assert str(tmp_path) not in output


def test_docker_start_failure_preserves_native_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web
    from research_workbench_entrypoint.runtime_mode import RuntimeModeStore

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    project = tmp_path / "checkout"
    (project / "requirements").mkdir(parents=True)
    (project / "requirements/web.lock").write_text("locked\n", encoding="utf-8")
    (project / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(setup_web.Path, "home", classmethod(lambda _cls: home))

    monkeypatch.setattr(
        setup_web._DockerRuntimeController,
        "install",
        lambda _self: {"ok": True, "issues": [], "image_id": "sha256:" + "a" * 64},
    )
    monkeypatch.setattr(
        setup_web._DockerRuntimeController,
        "start",
        lambda _self: {"ok": False, "issues": ["docker_port_8088_occupied"]},
    )
    arguments = setup_web.build_parser().parse_args(["--runtime", "docker", "--repair"])
    with pytest.raises(RuntimeError, match="^docker_port_8088_occupied$"):
        setup_web.install_selected_runtime(arguments, project_root=project)
    data_home = home / ".research-workbench"
    assert RuntimeModeStore(data_home).read().mode == "native"
    assert not (data_home / "install/docker-manifest.json").exists()


def test_docker_failure_uses_platform_remediation_without_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web

    project = tmp_path / "checkout"
    (project / "scripts").mkdir(parents=True)
    monkeypatch.setattr(setup_web, "__file__", str(project / "scripts/setup_web.py"))
    monkeypatch.setattr(setup_web, "_configure_logging", lambda _root: None)

    monkeypatch.setattr(
        setup_web._DockerRuntimeController,
        "install",
        lambda _self: {"ok": False, "issues": ["docker_cli_missing"]},
    )
    captured = StringIO()
    with redirect_stderr(captured):
        assert setup_web.main(["--runtime", "docker", "--no-start"]) == 1
    assert "docker_cli_missing" in captured.getvalue()
    assert "Docker Desktop" in captured.getvalue()
    assert str(tmp_path) not in captured.getvalue()


def test_explicit_native_selection_keeps_legacy_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web

    calls: list[tuple[bool, bool]] = []

    class RecordingNative:
        def __init__(self, *, project_root: Path) -> None:
            assert project_root == tmp_path

        def install(self, *, repair: bool, start: bool) -> dict[str, object]:
            calls.append((repair, start))
            return {"status": "installed"}

    monkeypatch.setattr(setup_web, "SetupWebInstaller", RecordingNative)
    for flags in ([], ["--runtime", "native"], ["--runtime", "native", "--repair", "--no-start"]):
        arguments = setup_web.build_parser().parse_args(flags)
        assert setup_web.install_selected_runtime(arguments, project_root=tmp_path) == {"status": "installed"}
    assert calls == [(False, True), (False, True), (True, False)]


def test_no_argument_main_keeps_native_json_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web

    project = tmp_path / "checkout"
    (project / "scripts").mkdir(parents=True)
    monkeypatch.setattr(setup_web, "__file__", str(project / "scripts/setup_web.py"))
    monkeypatch.setattr(setup_web, "_configure_logging", lambda _root: None)

    class RecordingNative:
        def __init__(self, *, project_root: Path) -> None:
            assert project_root == project

        def install(self, *, repair: bool, start: bool) -> dict[str, object]:
            assert (repair, start) == (False, True)
            return {
                "status": "installed",
                "code_commit": "a" * 40,
                "cjpy_version": "0.5.2",
                "dsh_commit": DSH_COMMIT,
            }

    monkeypatch.setattr(setup_web, "SetupWebInstaller", RecordingNative)
    captured = StringIO()
    with redirect_stdout(captured):
        assert setup_web.main([]) == 0
    assert json.loads(captured.getvalue()) == {
        "status": "installed",
        "code_commit": "a" * 40,
        "cjpy_version": "0.5.2",
        "dsh_commit": DSH_COMMIT,
        "started": True,
    }


def test_docker_success_main_prints_only_public_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import setup_web

    project = tmp_path / "checkout"
    (project / "scripts").mkdir(parents=True)
    monkeypatch.setattr(setup_web, "__file__", str(project / "scripts/setup_web.py"))
    monkeypatch.setattr(setup_web, "_configure_logging", lambda _root: None)
    monkeypatch.setattr(
        setup_web,
        "install_selected_runtime",
        lambda arguments, *, project_root: {
            "status": "installed",
            "code_commit": "a" * 40,
            "image_id": "sha256:" + "b" * 64,
            "private_path": str(tmp_path),
        },
    )
    captured = StringIO()
    with redirect_stdout(captured):
        assert setup_web.main(["--runtime", "docker", "--no-start"]) == 0
    assert json.loads(captured.getvalue()) == {
        "status": "installed",
        "runtime": "docker",
        "code_commit": "a" * 40,
        "image_id": "sha256:" + "b" * 64,
        "started": False,
    }
    assert str(tmp_path) not in captured.getvalue()


def test_runtime_constants_share_the_machine_contract() -> None:
    from app.research_web.runtime_contract import load_runtime_contract
    from scripts import setup_web

    contract = load_runtime_contract()
    assert setup_web.CJPY_VERSION == contract.cjpy_version
    assert setup_web.CJPY_WHEEL == f"cjpy-{contract.cjpy_version}-py3-none-any.whl"
    assert setup_web.CJPY_SHA256 == contract.cjpy_sha256
    assert setup_web.DSH_REMOTE == contract.dsh_remote
    assert setup_web.DSH_COMMIT == contract.dsh_commit
    assert setup_web.DSH_PNPM == contract.dsh_pnpm
    assert setup_web.DSH_CLOSURE_FILES == contract.dsh_closure_files
    assert setup_web.RUNTIME_CONTRACT == contract
    assert SetupWebInstaller._node_supported("v22.19.0")
    assert SetupWebInstaller._node_supported("v24.0.0")
    assert not SetupWebInstaller._node_supported("v22.18.0")
    assert not SetupWebInstaller._node_supported("v25.0.0")


def test_installer_prefers_configured_node_over_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "node-24"
    configured.write_text("fixture", encoding="utf-8")
    path_node = tmp_path / "node-25"
    path_node.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("RESEARCH_NODE_BINARY", str(configured))
    monkeypatch.setattr(shutil, "which", lambda name: str(path_node) if name == "node" else None)

    installer = SetupWebInstaller(project_root=tmp_path)

    assert installer.node_executable == configured.resolve()


def test_installer_prefers_codex_bundled_node_over_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    bundled = home / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("fixture", encoding="utf-8")
    bundled.chmod(0o755)
    path_node = tmp_path / "node-25"
    path_node.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("RESEARCH_NODE_BINARY", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: str(path_node) if name == "node" else None)

    installer = SetupWebInstaller(project_root=tmp_path)

    assert installer.node_executable == bundled.resolve()


def test_check_only_rejects_an_unowned_virtual_environment_without_mutating_it(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "checkout"
    data_home = tmp_path / "private-data"
    environment = project_root / ".venv"
    environment.mkdir(parents=True)
    sentinel = environment / "belongs-to-user.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    installer = SetupWebInstaller(
        project_root=project_root,
        data_home=data_home,
        python_executable=Path(sys.executable),
        node_executable=Path(shutil.which("node") or "/missing-node"),
        git_executable=Path(shutil.which("git") or "/missing-git"),
        version_reader=lambda _path: "3.12.9",
        node_version_reader=lambda _path: "v24.8.0",
    )

    report = installer.check()

    assert report["ok"] is False
    assert report["issues"] == ["unowned_virtual_environment"]
    assert sentinel.read_text(encoding="utf-8") == "preserve me"
    assert not data_home.exists()


def test_vendored_cjpy_bundle_matches_the_approved_release() -> None:
    project_root = Path(__file__).resolve().parents[2]
    installer = SetupWebInstaller(project_root=project_root)

    bundle = installer.verify_cjpy_bundle()

    assert bundle == {
        "version": "0.5.2",
        "wheel": "cjpy-0.5.2-py3-none-any.whl",
        "sha256": "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94",
    }


def test_dependency_plan_uses_the_hash_lock_and_never_resolves_cjpy_from_pypi() -> None:
    project_root = Path(__file__).resolve().parents[2]
    installer = SetupWebInstaller(project_root=project_root)
    environment_python = project_root / ".venv" / "bin" / "python"

    commands = installer.dependency_install_commands(environment_python)

    assert commands[0] == [
        str(environment_python),
        "-m",
        "pip",
        "uninstall",
        "--yes",
        "research-workbench",
    ]
    assert commands[1] == [
        str(environment_python),
        "-m",
        "pip",
        "install",
        "--index-url",
        "https://pypi.org/simple",
        "--require-hashes",
        "-r",
        str(project_root / "requirements" / "web.lock"),
    ]
    assert commands[2][-3:] == ["--no-build-isolation", "--no-deps", str(project_root)]
    assert commands[3][-3:] == [
        "--no-deps",
        str(project_root / "vendor" / "cjpy" / "0.5.2" / "cjpy-0.5.2-py3-none-any.whl"),
        "--force-reinstall",
    ]
    assert "--no-index" in commands[3]
    lock_text = (project_root / "requirements" / "web.lock").read_text(encoding="utf-8")
    assert "cjpy==" not in lock_text.lower()


def test_web_import_readiness_uses_the_project_source_with_a_bounded_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    installer = SetupWebInstaller(project_root=project_root, data_home=tmp_path / "data")
    environment_python = installer._environment_python(project_root / ".venv")
    recorded: dict[str, object] = {}

    def record(command, *, cwd, environment, failure_code, timeout):
        recorded.update(
            command=command,
            cwd=cwd,
            environment=environment,
            failure_code=failure_code,
            timeout=timeout,
        )

    monkeypatch.setattr(installer, "_run_checked", record)

    installer.verify_web_import(environment_python)

    assert recorded["command"] == [
        str(environment_python),
        "-B",
        "-c",
        "from app.research_web.main import app; assert app is not None",
    ]
    assert recorded["cwd"] == project_root
    assert recorded["failure_code"] == "python_web_import_failed"
    assert recorded["timeout"] == 300
    assert "PYTHONPATH" not in recorded["environment"]


def test_dsh_verifier_rejects_a_repository_at_the_wrong_commit(tmp_path: Path) -> None:
    source = tmp_path / "dsh"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/Leon-Huang001208/deepseek-harness.git",
        ],
        cwd=source,
        check=True,
    )
    (source / "package.json").write_text('{"packageManager":"pnpm@11.7.0"}', encoding="utf-8")
    subprocess.run(["git", "add", "package.json"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=source,
        check=True,
    )
    installer = SetupWebInstaller(project_root=tmp_path)

    try:
        installer.verify_dsh_source(source, require_build=False)
    except RuntimeError as exc:
        assert str(exc) == "dsh_commit_mismatch"
    else:
        raise AssertionError("wrong DSH commit was accepted")


def test_installer_creates_and_reuses_only_its_owned_virtual_environment(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    installer = SetupWebInstaller(
        project_root=project_root,
        data_home=tmp_path / "private-data",
        python_executable=Path(sys.executable),
    )

    environment_python = installer.prepare_environment()
    reused_python = installer.prepare_environment()

    assert environment_python == reused_python
    assert environment_python.is_file()
    marker = json.loads((project_root / ".venv" / ".rwb-web-environment.json").read_text())
    assert marker["schema_version"] == 1
    assert marker["owner"] == "research-workbench-web-installer"
    assert "secret" not in json.dumps(marker).lower()


def test_repair_replaces_an_owned_environment_when_pip_is_unresponsive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    installer = SetupWebInstaller(
        project_root=project_root,
        data_home=tmp_path / "private-data",
        python_executable=Path(sys.executable),
        version_reader=lambda _path: "Python 3.12.13",
    )
    installer.prepare_environment()
    sentinel = project_root / ".venv" / "stalled-environment.txt"
    sentinel.write_text("preserve for rollback", encoding="utf-8")
    recorded: list[tuple[list[str], int]] = []

    def run(command, **options):
        recorded.append((list(command), int(options["timeout"])))
        if command[1:] == ["-m", "pip", "--version"]:
            raise subprocess.TimeoutExpired(command, options["timeout"])
        destination = Path(command[-1])
        environment_python = installer._environment_python(destination)
        environment_python.parent.mkdir(parents=True)
        environment_python.write_text("replacement", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)

    environment_python = installer.prepare_environment(repair=True)

    backups = list(project_root.glob(".venv.failed-*"))
    assert environment_python == installer._environment_python(project_root / ".venv")
    assert not (project_root / ".venv" / sentinel.name).exists()
    assert len(backups) == 1
    assert (backups[0] / sentinel.name).read_text(encoding="utf-8") == "preserve for rollback"
    assert recorded[0] == (
        [str(installer._environment_python(project_root / ".venv")), "-m", "pip", "--version"],
        15,
    )


def test_repository_exposes_mac_windows_and_cross_platform_setup_entrypoints() -> None:
    project_root = Path(__file__).resolve().parents[2]

    shell = (project_root / "setup-web.sh").read_text(encoding="utf-8")
    windows = (project_root / "setup-web.cmd").read_text(encoding="utf-8")
    windows_cli = (project_root / "rwb.cmd").read_text(encoding="utf-8")
    attributes = (project_root / ".gitattributes").read_text(encoding="utf-8")

    assert "scripts/setup_web.py" in shell
    assert '"$@"' in shell
    assert '"%PROJECT_ROOT%\\scripts\\setup_web.py"' in windows
    assert windows.count(" %*") == 2
    assert "%PROJECT_ROOT%\\.venv\\Scripts\\python.exe" in windows_cli
    assert "research_workbench_entrypoint" in windows_cli
    assert "exit /b %errorlevel%" not in windows
    assert windows.count("if errorlevel 1 exit /b 1") == 2
    assert "/vendor/dsh-tabbit/0.3.4/** -text" in attributes


def test_private_corepack_shim_is_added_to_the_child_build_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corepack = tmp_path / "corepack"
    corepack.write_text("fixture", encoding="utf-8")
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "private-data",
        corepack_executable=corepack,
    )
    recorded: dict[str, object] = {}

    def fake_run_checked(command, *, cwd, environment, failure_code, timeout):
        recorded.update(
            command=command,
            cwd=cwd,
            environment=environment,
            failure_code=failure_code,
            timeout=timeout,
        )
        shim_directory = Path(command[-1])
        shim_directory.mkdir(parents=True, exist_ok=True)
        (shim_directory / ("pnpm.cmd" if os.name == "nt" else "pnpm")).write_text(
            "fixture", encoding="utf-8"
        )

    monkeypatch.setattr(installer, "_run_checked", fake_run_checked)

    environment = installer.prepare_pnpm_shims({"PATH": "original-path"})

    shim_directory = installer.data_home / "runtime" / "corepack-shims" / "11.7.0"
    assert recorded["command"] == [
        str(corepack.resolve()),
        "enable",
        "pnpm",
        "--install-directory",
        str(shim_directory),
    ]
    assert recorded["failure_code"] == "corepack_shim_install_failed"
    assert environment["PATH"] == f"{shim_directory}{os.pathsep}original-path"


@pytest.mark.parametrize(
    ("python_version", "node_version", "expected"),
    [
        ("3.11.9", "v24.8.0", "python_version_unsupported"),
        ("3.12.9", "v22.18.0", "node_version_unsupported"),
        ("3.12.9", "v23.9.0", "node_version_unsupported"),
        ("3.12.9", "v25.9.0", "node_version_unsupported"),
    ],
)
def test_check_rejects_unsupported_python_and_node_versions_without_writes(
    tmp_path: Path,
    python_version: str,
    node_version: str,
    expected: str,
) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    data_home = tmp_path / "private-data"
    installer = SetupWebInstaller(
        project_root=project_root,
        data_home=data_home,
        python_executable=Path(sys.executable),
        node_executable=Path(shutil.which("node") or sys.executable),
        git_executable=Path(shutil.which("git") or sys.executable),
        version_reader=lambda _path: python_version,
        node_version_reader=lambda _path: node_version,
    )

    report = installer.check()

    assert report["ok"] is False
    assert expected in report["issues"]
    assert not data_home.exists()
    assert not (project_root / ".venv").exists()


def test_subprocess_environment_drops_application_secrets_and_update_notices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CJ_KEY", "must-not-escape")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-escape")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:18080")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")

    environment = installer._subprocess_environment()

    assert "CJ_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["HTTPS_PROXY"] == "http://127.0.0.1:18080"
    assert environment["NO_UPDATE_NOTIFIER"] == "1"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"


def test_node_subprocess_environment_drops_proxy_protocols_corepack_cannot_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("all_proxy", "socks5h://127.0.0.1:1080")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:18080")
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")

    git_environment = installer._subprocess_environment()
    node_environment = installer._node_subprocess_environment()

    assert git_environment["ALL_PROXY"].startswith("socks5:")
    assert "ALL_PROXY" not in node_environment
    assert "all_proxy" not in node_environment
    assert node_environment["HTTPS_PROXY"] == "http://127.0.0.1:18080"


def test_python_dependency_install_drops_proxy_protocols_pip_cannot_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTP_PROXY", "socks5h://127.0.0.1:1080")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:18080")
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("http_proxy", "ftp://127.0.0.1:2121")
    monkeypatch.setenv("https_proxy", "https://127.0.0.1:18443")
    monkeypatch.setenv("all_proxy", "socks5h://127.0.0.1:1080")
    project_root = tmp_path / "checkout"
    lock = project_root / "requirements" / "web.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("fixture --hash=sha256:" + "a" * 64, encoding="utf-8")
    installer = SetupWebInstaller(project_root=project_root, data_home=tmp_path / "data")
    monkeypatch.setattr(
        installer,
        "verify_cjpy_bundle",
        lambda: {"version": "0.5.2", "sha256": "b" * 64},
    )
    monkeypatch.setattr(
        installer,
        "dependency_install_commands",
        lambda _python: [[f"command-{index}"] for index in range(4)],
    )
    environments: list[dict[str, str]] = []

    def record_environment(_command, *, environment, **_kwargs) -> None:
        environments.append(dict(environment))

    monkeypatch.setattr(installer, "_run_checked", record_environment)
    caplog.set_level(logging.WARNING, logger="research_workbench.setup_web")

    installer.install_python_dependencies(project_root / ".venv" / "bin" / "python")

    git_environment = installer._subprocess_environment()
    assert git_environment["ALL_PROXY"].startswith("socks5:")
    assert git_environment["all_proxy"].startswith("socks5h:")
    assert environments
    assert all("HTTP_PROXY" not in environment for environment in environments)
    assert all("http_proxy" not in environment for environment in environments)
    assert all("ALL_PROXY" not in environment for environment in environments)
    assert all("all_proxy" not in environment for environment in environments)
    assert all(
        environment["HTTPS_PROXY"] == "http://127.0.0.1:18080" for environment in environments
    )
    assert all(
        environment["https_proxy"] == "https://127.0.0.1:18443" for environment in environments
    )
    assert "setup_web_python_proxy_protocol_filtered" in caplog.messages
    assert "127.0.0.1:1080" not in caplog.text


def test_node_subprocess_environment_puts_selected_node_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node = tmp_path / "node-24" / "bin" / "node"
    node.parent.mkdir(parents=True)
    node.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "data",
        node_executable=node,
    )

    environment = installer._node_subprocess_environment()

    assert environment["PATH"].split(os.pathsep)[0] == str(node.parent.resolve())


def test_windows_node_environment_preserves_standard_toolchain_discovery_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {
        "PSMODULEPATH": r"C:\Program Files\WindowsPowerShell\Modules",
        "PROGRAMFILES": r"C:\Program Files",
        "PROGRAMFILES(X86)": r"C:\Program Files (x86)",
        "PROGRAMDATA": r"C:\ProgramData",
        "SYSTEMDRIVE": "C:",
        "COMMONPROGRAMFILES": r"C:\Program Files\Common Files",
        "COMMONPROGRAMFILES(X86)": r"C:\Program Files (x86)\Common Files",
    }
    for key, value in expected.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-escape")
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "data",
        platform_name="nt",
    )

    environment = installer._node_subprocess_environment()

    assert {key: environment.get(key) for key in expected} == expected
    assert "OPENAI_API_KEY" not in environment


def test_node_subprocess_environment_uses_discovered_macos_sdk_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cpp_headers = tmp_path / "MacOSX.sdk" / "usr" / "include" / "c++" / "v1"
    cpp_headers.mkdir(parents=True)
    (cpp_headers / "memory").write_text("fixture", encoding="utf-8")
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")
    monkeypatch.setattr(installer, "_macos_cpp_include", lambda: cpp_headers)

    environment = installer._node_subprocess_environment()

    assert environment["CPLUS_INCLUDE_PATH"] == str(cpp_headers)


def test_cjpy_bundle_rejects_a_modified_manifest_file(tmp_path: Path) -> None:
    real_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "checkout"
    destination = project_root / "vendor" / "cjpy" / "0.5.2"
    shutil.copytree(real_root / "vendor" / "cjpy" / "0.5.2", destination)
    (destination / "SOURCE.md").write_text("tampered", encoding="utf-8")

    with pytest.raises(RuntimeError, match="^cjpy_bundle_invalid$"):
        SetupWebInstaller(project_root=project_root).verify_cjpy_bundle()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_dsh_verifier_rejects_the_source_path_symlink_before_resolving_it(tmp_path: Path) -> None:
    target = tmp_path / "real-source"
    target.mkdir()
    alias = tmp_path / "source-alias"
    alias.symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="^dsh_source_unsafe$"):
        SetupWebInstaller(project_root=tmp_path).verify_dsh_source(alias, require_build=False)


def test_install_manifest_is_an_allowlist_and_never_serializes_secrets(tmp_path: Path) -> None:
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "data",
        python_executable=Path(sys.executable),
        node_executable=Path(shutil.which("node") or sys.executable),
        git_executable=Path(shutil.which("git") or sys.executable),
        version_reader=lambda _path: "3.12.9",
        node_version_reader=lambda _path: "v24.8.0",
    )

    manifest = installer.write_install_manifest(
        python_state={
            "lock_sha256": "lock",
            "cjpy_version": "0.5.2",
            "cjpy_sha256": "wheel",
            "CJ_KEY": "must-not-escape",
        },
        dsh_state={
            "commit": "commit",
            "closure_sha256": "closure",
            "closure_files": 11084,
            "secret": "must-not-escape",
        },
        status="installed",
    )
    serialized = installer.install_manifest.read_text(encoding="utf-8")

    assert set(manifest) == {
        "schema_version",
        "status",
        "code_commit",
        "python_version",
        "node_version",
        "web_lock_sha256",
        "cjpy_version",
        "cjpy_sha256",
        "dsh_commit",
        "dsh_closure_sha256",
        "dsh_closure_files",
        "installed_at",
        "last_diagnosis",
    }
    assert "must-not-escape" not in serialized


def test_install_invalidates_a_stale_manifest_before_web_import_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = SetupWebInstaller(
        project_root=tmp_path / "checkout",
        data_home=tmp_path / "data",
        python_executable=Path(sys.executable),
        node_executable=Path(sys.executable),
        git_executable=Path(shutil.which("git") or sys.executable),
        version_reader=lambda _path: "3.12.13",
        node_version_reader=lambda _path: "v24.8.0",
    )
    installer.install_manifest.parent.mkdir(parents=True)
    installer.install_manifest.write_text(
        json.dumps({"schema_version": 1, "status": "installed", "sentinel": "stale"}),
        encoding="utf-8",
    )
    environment_python = installer._environment_python(installer.venv)
    monkeypatch.setattr(installer, "check", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(installer, "_code_commit", lambda: "a" * 40)
    monkeypatch.setattr(installer, "prepare_environment", lambda repair=False: environment_python)
    monkeypatch.setattr(
        installer,
        "install_python_dependencies",
        lambda _python: {
            "lock_sha256": "lock",
            "cjpy_version": "0.5.2",
            "cjpy_sha256": "wheel",
        },
    )
    monkeypatch.setattr(
        installer,
        "verify_web_import",
        lambda _python: (_ for _ in ()).throw(RuntimeError("python_web_import_failed")),
    )
    monkeypatch.setattr(
        installer,
        "provision_dsh",
        lambda repair=False: (_ for _ in ()).throw(AssertionError("DSH must not be provisioned")),
    )

    with pytest.raises(RuntimeError, match="^python_web_import_failed$"):
        installer.install(start=False)

    manifest = json.loads(installer.install_manifest.read_text(encoding="utf-8"))
    assert manifest == {
        "schema_version": 1,
        "status": "installing",
        "code_commit": "a" * 40,
        "started_at": manifest["started_at"],
        "last_diagnosis": "installing",
    }
    assert "sentinel" not in manifest


def test_install_refreshes_runtime_build_lock_from_verified_dsh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = SetupWebInstaller(
        project_root=tmp_path / "checkout",
        data_home=tmp_path / "data",
        python_executable=Path(sys.executable),
        node_executable=Path(sys.executable),
        git_executable=Path(shutil.which("git") or sys.executable),
        version_reader=lambda _path: "3.12.9",
        node_version_reader=lambda _path: "v24.8.0",
    )
    environment_python = tmp_path / "checkout/.venv/bin/python"
    web_imports: list[Path] = []
    dsh_state = {
        "commit": DSH_COMMIT,
        "remote": DSH_REMOTE,
        "pnpm": "11.7.0",
        "closure_sha256": "b" * 64,
        "closure_files": 11084,
    }
    monkeypatch.setattr(installer, "check", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(installer, "prepare_environment", lambda repair=False: environment_python)
    monkeypatch.setattr(
        installer,
        "install_python_dependencies",
        lambda _python: {
            "lock_sha256": "lock",
            "cjpy_version": "0.5.2",
            "cjpy_sha256": "wheel",
        },
    )
    monkeypatch.setattr(installer, "verify_web_import", web_imports.append)
    monkeypatch.setattr(installer, "provision_dsh", lambda repair=False: dsh_state)
    runtime_lock = installer.data_home / "research-web/runtime/build-lock.json"
    runtime_lock.parent.mkdir(parents=True)
    runtime_lock.write_text('{"closure_sha256":"stale"}', encoding="utf-8")
    runtime_lock.chmod(0o600)

    installer.install(start=False)

    assert web_imports == [environment_python]
    assert json.loads(runtime_lock.read_text(encoding="utf-8")) == {
        "source_commit": DSH_COMMIT,
        "closure_sha256": "b" * 64,
        "closure_files": 11084,
        "mode": "build",
    }
    assert runtime_lock.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_writer_rejects_a_linked_runtime_directory(
    tmp_path: Path,
) -> None:
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")
    research_web = installer.data_home / "research-web"
    research_web.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (research_web / "runtime").symlink_to(external, target_is_directory=True)

    with pytest.raises(RuntimeError, match="^runtime_build_lock_unsafe$"):
        installer.write_runtime_build_lock(
            dsh_state={
                "commit": DSH_COMMIT,
                "closure_sha256": "b" * 64,
                "closure_files": 11084,
            }
        )

    assert not (external / "build-lock.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_writer_rejects_a_preexisting_data_home_alias(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external-data"
    external.mkdir()
    alias = tmp_path / "data-alias"
    alias.symlink_to(external, target_is_directory=True)
    installer = SetupWebInstaller(project_root=tmp_path, data_home=alias)

    with pytest.raises(RuntimeError, match="^runtime_build_lock_unsafe$"):
        installer.write_runtime_build_lock(
            dsh_state={
                "commit": DSH_COMMIT,
                "closure_sha256": "b" * 64,
                "closure_files": 11084,
            }
        )

    assert not (external / "research-web/runtime/build-lock.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX private modes do not model Windows ACLs")
def test_runtime_build_lock_writer_makes_the_owned_data_home_private(
    tmp_path: Path,
) -> None:
    data_home = tmp_path / "data"
    data_home.mkdir(mode=0o755)
    installer = SetupWebInstaller(project_root=tmp_path, data_home=data_home)

    installer.write_runtime_build_lock(
        dsh_state={
            "commit": DSH_COMMIT,
            "closure_sha256": "b" * 64,
            "closure_files": 11084,
        }
    )

    assert data_home.stat().st_mode & 0o777 == 0o700


def test_runtime_build_lock_writer_requires_an_integer_file_count(tmp_path: Path) -> None:
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")

    with pytest.raises(RuntimeError, match="^dsh_runtime_lock_invalid$"):
        installer.write_runtime_build_lock(
            dsh_state={
                "commit": DSH_COMMIT,
                "closure_sha256": "b" * 64,
                "closure_files": 11084.0,
            }
        )


def test_owned_dsh_source_requires_a_well_formed_local_closure_attestation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "data" / "runtime" / "dsh" / ("c919b2a460753859665db3f60143d525fb9140cf")
    source.mkdir(parents=True)
    marker = source / ".rwb-dsh-source.json"
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "research-workbench-web-installer",
                "remote": "https://github.com/Leon-Huang001208/deepseek-harness.git",
                "commit": "c919b2a460753859665db3f60143d525fb9140cf",
                "closure_sha256": "a" * 64,
                "closure_files": 11084,
            }
        ),
        encoding="utf-8",
    )
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")

    assert installer._owned_dsh_source(source) is True

    value = json.loads(marker.read_text(encoding="utf-8"))
    value["closure_sha256"] = "not-a-digest"
    marker.write_text(json.dumps(value), encoding="utf-8")
    assert installer._owned_dsh_source(source) is False


def test_provision_dsh_recovers_a_completed_installer_staging_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")
    staging = installer.dsh_root / (
        ".c919b2a460753859665db3f60143d525fb9140cf.staging-" "0123456789abcdef0123456789abcdef"
    )
    staging.mkdir(parents=True)
    verified = {
        "commit": "c919b2a460753859665db3f60143d525fb9140cf",
        "remote": "https://github.com/Leon-Huang001208/deepseek-harness.git",
        "pnpm": "11.7.0",
        "closure_sha256": "b" * 64,
        "closure_files": 11084,
    }
    monkeypatch.setattr(installer, "verify_dsh_source", lambda _source: verified)

    result = installer.provision_dsh()

    assert result == verified
    assert installer.dsh_source.is_dir()
    marker = json.loads((installer.dsh_source / ".rwb-dsh-source.json").read_text(encoding="utf-8"))
    assert marker["closure_sha256"] == "b" * 64
    assert marker["closure_files"] == 11084


def test_dsh_checkout_enables_git_long_paths_for_windows_compatible_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "data",
        platform_name="nt",
    )
    commands: list[list[str]] = []
    verified = {
        "commit": "c919b2a460753859665db3f60143d525fb9140cf",
        "remote": "https://github.com/Leon-Huang001208/deepseek-harness.git",
        "pnpm": "11.7.0",
        "closure_sha256": "b" * 64,
        "closure_files": 11084,
    }

    def record(command, **_kwargs):
        commands.append(command)

    monkeypatch.setattr(installer, "_run_checked", record)
    monkeypatch.setattr(installer, "verify_dsh_source", lambda *_args, **_kwargs: verified)
    monkeypatch.setattr(installer, "prepare_pnpm_shims", lambda environment: environment)
    monkeypatch.setattr(installer, "dsh_build_commands", lambda _source: [])
    monkeypatch.setattr(installer, "_publish_dsh_build", lambda _source, state: state)

    assert installer.provision_dsh() == verified

    git_commands = [command for command in commands if command[0] == str(installer.git_executable)]
    assert len(git_commands) == 2
    expected_options = [
        "-c",
        "core.longpaths=true",
        "-c",
        "core.symlinks=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
    ]
    assert all(command[1:9] == expected_options for command in git_commands)


def test_windows_dsh_verification_uses_the_checkout_worktree_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "dsh"
    source.mkdir()
    (source / "package.json").write_text('{"packageManager":"pnpm@11.7.0"}', encoding="utf-8")
    installer = SetupWebInstaller(
        project_root=tmp_path,
        data_home=tmp_path / "data",
        platform_name="nt",
    )
    commands: list[list[str]] = []

    def check_output(command, **_kwargs):
        commands.append(command)
        if "get-url" in command:
            return DSH_REMOTE
        if "rev-parse" in command:
            return DSH_COMMIT
        return ""

    monkeypatch.setattr(subprocess, "check_output", check_output)

    installer.verify_dsh_source(source, require_build=False)

    status = next(command for command in commands if "status" in command)
    assert status[1:9] == [
        "-c",
        "core.longpaths=true",
        "-c",
        "core.symlinks=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
    ]
