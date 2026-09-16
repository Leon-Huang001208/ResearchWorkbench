"""Public one-click Web bootstrap contracts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.setup_web import SetupWebInstaller


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


def test_repository_exposes_mac_windows_and_cross_platform_setup_entrypoints() -> None:
    project_root = Path(__file__).resolve().parents[2]

    shell = (project_root / "setup-web.sh").read_text(encoding="utf-8")
    windows = (project_root / "setup-web.cmd").read_text(encoding="utf-8")
    windows_cli = (project_root / "rwb.cmd").read_text(encoding="utf-8")

    assert "scripts/setup_web.py" in shell
    assert '"%PROJECT_ROOT%\\scripts\\setup_web.py"' in windows
    assert "%PROJECT_ROOT%\\.venv\\Scripts\\python.exe" in windows_cli
    assert "research_workbench_entrypoint" in windows_cli
    assert "exit /b %errorlevel%" not in windows
    assert windows.count("if errorlevel 1 exit /b 1") == 2


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
    installer = SetupWebInstaller(project_root=tmp_path, data_home=tmp_path / "data")
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
    assert all("core.longpaths=true" in command for command in git_commands)
