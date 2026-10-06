import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from app.research_web import launch_runtime
from app.research_web.mcp_runtime.authorization import AuthorizationManager


def test_runtime_constants_share_the_machine_contract():
    from app.research_web import PINNED_DSH_COMMIT
    from app.research_web.runtime_contract import load_runtime_contract

    contract = load_runtime_contract()
    assert PINNED_DSH_COMMIT == contract.dsh_commit
    assert launch_runtime.PINNED_COMMIT == contract.dsh_commit
    assert launch_runtime.RUNTIME_CONTRACT == contract


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "packages/boot/app-boot/lib").mkdir(parents=True)
    (source / "packages/boot/app-boot/lib/index.js").write_text("// built")
    (source / "apps/cli/lib").mkdir(parents=True)
    (source / "apps/cli/package.json").write_text("{}")
    (source / "apps/cli/lib/bin.js").write_text("// cli")
    return source


def test_runtime_module_fallback_is_healed_inside_private_source(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    target = source / "packages/example"
    target.mkdir(parents=True)

    def run(*args, **kwargs):
        assert "loadProfile('dsh', 'web', anchor, home)" in args[0][3]
        assert "healProfilesModuleFallback({ installAnchor: anchor, profile })" in args[0][3]
        profile = home / "profiles/web"
        profile.mkdir(parents=True)
        (profile / "package.json").write_text(
            json.dumps(
                {
                    "name": "dsh-profile-web",
                    "private": True,
                    "dependencies": {},
                    "dsh": {
                        "profile": {
                            "bundles": [
                                "@deepseek-ai/dsh-base",
                                "@deepseek-ai/dsh-web-app",
                            ],
                            "patchReload": "live",
                        }
                    },
                }
            )
        )
        modules = home / "profiles/node_modules/@deepseek-ai"
        modules.mkdir(parents=True)
        (modules / "dsh-example").symlink_to(target)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1
    assert (home / "profiles/web/package.json").is_file()


def test_runtime_module_fallback_rejects_external_target(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    external = tmp_path / "external"
    external.mkdir()

    def run(*args, **kwargs):
        modules = home / "profiles/node_modules"
        modules.mkdir(parents=True)
        (modules / "external").symlink_to(external)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="越出项目私有源码目录"):
        launch_runtime.prepare_runtime_module_fallback(source, home, "/node")


def test_runtime_module_fallback_accepts_windows_junctions_inside_private_source(
    tmp_path, monkeypatch
):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    target = source / "packages/example"
    target.mkdir(parents=True)
    link = home / "profiles/node_modules/dsh-example"
    original_is_symlink = Path.is_symlink

    def run(*_args, **_kwargs):
        link.parent.mkdir(parents=True)
        link.symlink_to(target, target_is_directory=True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: False if path == link else original_is_symlink(path),
    )
    monkeypatch.setattr(Path, "is_junction", lambda path: path == link)
    monkeypatch.setattr(launch_runtime.os, "name", "nt")

    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1


def test_runtime_keeps_dsh_home_private_but_uses_host_home_for_tabbit(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    host_home = tmp_path / "host-user"
    local_app_data = host_home / "AppData/Local"
    monkeypatch.setenv("HOME", str(host_home))
    monkeypatch.setenv("USERPROFILE", str(host_home))
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )

    _, env, _ = launch_runtime.prepare(source, data, "/node", 3081)

    assert env["DSH_HOME"] == str(data.resolve() / "runtime/home")
    assert env["HOME"] == str(host_home)
    assert env["USERPROFILE"] == str(host_home)
    assert env["LOCALAPPDATA"] == str(local_app_data)


@pytest.mark.parametrize("marker", ["runtime", "web", "invalid", "runtime\nweb", ""])
def test_clean_runtime_exec_environment_retains_only_exact_runtime_role(
    tmp_path, monkeypatch, marker
):
    source = make_source(tmp_path)
    monkeypatch.setenv("RWB_SUPERVISOR_ROLE", marker)
    monkeypatch.setenv("UNRELATED_HOST_VALUE", "must-not-cross-exec-boundary")
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    _, env, _ = launch_runtime.prepare(source, tmp_path / "data", "/node", 3081)
    assert env.get("RWB_SUPERVISOR_ROLE") == ("runtime" if marker == "runtime" else None)
    assert "UNRELATED_HOST_VALUE" not in env
    assert "must-not-cross-exec-boundary" not in env.values()


def test_runtime_role_survives_real_exec_with_clean_environment(tmp_path):
    source = make_source(tmp_path)
    # Python stands in for Node only at the final executable boundary. The real
    # launcher prepare/main/execve path supplies the environment to this process.
    (source / "apps/cli/lib/bin.js").write_text(
        "import json,os\n"
        "print(json.dumps({'role':os.environ.get('RWB_SUPERVISOR_ROLE'),"
        "'host':os.environ.get('UNRELATED_HOST_VALUE')}))\n"
    )
    runner = """
import os, sys
from app.research_web import launch_runtime as launcher
launcher.setup_logging = lambda: None
launcher.subprocess.check_output = lambda *a, **k: launcher.PINNED_COMMIT
launcher.validate_tabbit_node = lambda node: '24.0.0'
launcher.prepare_runtime_module_fallback = lambda *a: 0
launcher.stage_tabbit_package = lambda *a: {'version':'fixture','source_commit':'fixture'}
launcher.stage_tabbit_adapter = lambda *a: None
os.environ['RWB_SUPERVISOR_ROLE'] = 'runtime'
os.environ['UNRELATED_HOST_VALUE'] = 'must-not-cross-exec-boundary'
sys.argv = ['launcher', '--source', sys.argv[1], '--data', sys.argv[2], '--node', sys.executable]
launcher.main()
"""
    completed = subprocess.run(
        [sys.executable, "-c", runner, str(source), str(tmp_path / "data")],
        capture_output=True, text=True, timeout=5, check=True,
    )
    assert json.loads(completed.stdout.splitlines()[-1]) == {"role": "runtime", "host": None}


@pytest.mark.parametrize("separate_state", [False, True])
def test_prepare_separates_persistent_data_from_runtime_state(
    tmp_path, monkeypatch, separate_state
):
    from app.research_web.client import _default_auth_path

    source = make_source(tmp_path)
    data = tmp_path / "data"
    state = tmp_path / "state" if separate_state else data / "runtime"
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    monkeypatch.setenv("RESEARCH_DATA_HOME", str(data))
    monkeypatch.setenv("RESEARCH_RUNTIME_AUTH", str(state / "auth.json"))
    options = {"state_root": state} if separate_state else {}
    command, env, work = launch_runtime.prepare(source, data, "/node", 3081, **options)
    assert env["DSH_HOME"] == str(data.resolve() / "runtime/home")
    assert work == data.resolve() / "runtime/work"
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--patch") + 1] == str(state.resolve() / "overlay.yml")
    assert (state / "build-lock.json").is_file()
    assert _default_auth_path() == state / "auth.json"
    if separate_state:
        assert not (data / "runtime/overlay.yml").exists()
        assert not (data / "runtime/build-lock.json").exists()
        assert not (state / "home").exists()


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="Legacy POSIX directory permissions")
@pytest.mark.parametrize("layout", ["legacy_native", "public_parent", "custom"])
def test_direct_prepare_legacy_native_state_requires_private_data(tmp_path, monkeypatch, layout):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    state = data / "runtime" if layout != "custom" else tmp_path / "state"
    state.mkdir(mode=0o755)
    state.chmod(0o755)
    if layout == "public_parent":
        data.chmod(0o755)
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *_args, **_kwargs: launch_runtime.PINNED_COMMIT,
    )
    if layout == "legacy_native":
        command, env, work = launch_runtime.prepare(source, data, "/node", 3081)
        assert command[command.index("--patch") + 1] == str(state / "overlay.yml")
        assert env["DSH_HOME"] == str(state / "home")
        assert work == state / "work"
        assert state.stat().st_mode & 0o777 == 0o755
    else:
        with pytest.raises(ValueError, match="runtime_state_unsafe"):
            launch_runtime.prepare(source, data, "/node", 3081, state_root=state)
        assert not (state / "overlay.yml").exists()
        assert not (state / "build-lock.json").exists()


@pytest.mark.parametrize("mode", ["default", "explicit_state", "data_alias"])
def test_launch_cli_accepts_state_and_preserves_historical_default(tmp_path, monkeypatch, mode):
    data = tmp_path / "data"
    state = tmp_path / "state" if mode == "explicit_state" else data / "runtime"
    if mode == "data_alias":
        data.mkdir()
        alias = tmp_path / "data-alias"
        alias.symlink_to(data, target_is_directory=True)
        data = alias
    argv = ["launch_runtime", "--source", str(tmp_path / "source"), "--data", str(data)]
    if mode == "explicit_state":
        argv += ["--state", str(state)]
    monkeypatch.setattr(launch_runtime.sys, "argv", argv)
    monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
    monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda _node: "24.0.0")
    observed = {}

    def prepare(*args, **kwargs):
        observed.update(kwargs)
        raise RuntimeError("stop before any service launch")

    monkeypatch.setattr(launch_runtime, "prepare", prepare)
    with pytest.raises(SystemExit) as failure:
        launch_runtime.main()
    assert failure.value.code == 1
    assert observed["state_root"] == state


@pytest.mark.parametrize(
    "unsafe", ["writable", "symlink", "ancestor_symlink", "ancestor_writable", "file"]
)
@pytest.mark.parametrize("entrypoint", ["prepare", "cli"])
def test_launch_rejects_unsafe_state_before_file_access(tmp_path, monkeypatch, unsafe, entrypoint):
    if launch_runtime.os.name == "nt" and unsafe != "file":
        pytest.skip("POSIX mode and symlink fixtures; Windows semantics tested separately")
    source = make_source(tmp_path)
    state = tmp_path / "state"
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    if unsafe == "writable":
        state.mkdir(mode=0o777)
        state.chmod(0o777)
    elif unsafe == "symlink":
        state.symlink_to(target, target_is_directory=True)
    elif unsafe == "ancestor_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(target, target_is_directory=True)
        state = alias / "state"
        (target / "state").mkdir(mode=0o700)
    elif unsafe == "ancestor_writable":
        target.chmod(0o777)
        state = target / "state"
        state.mkdir(mode=0o700)
    else:
        state.write_text("not a directory")
    original_open = Path.open

    def checked_open(path, *args, **kwargs):
        if path.parent == state:
            pytest.fail("state file accessed before rejecting unsafe directory")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    if entrypoint == "prepare":
        with pytest.raises((RuntimeError, ValueError), match="runtime_state_unsafe"):
            launch_runtime.prepare(source, tmp_path / "data", "/node", 3081, state_root=state)
    else:
        monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
        monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda _node: "24.0.0")
        monkeypatch.setattr(
            launch_runtime.sys,
            "argv",
            [
                "launch_runtime",
                "--source",
                str(source),
                "--data",
                str(tmp_path / "data"),
                "--state",
                str(state),
            ],
        )
        with pytest.raises(SystemExit) as error:
            launch_runtime.main()
        assert error.value.code == 1


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership and identity fixture")
def test_runtime_state_boundary_checks_owner_mode_and_identity(tmp_path, monkeypatch):
    import os

    from app.research_web import runtime_state

    state = tmp_path / "new" / "state"
    with runtime_state.runtime_state_directory(state, create=True):
        assert state.stat().st_mode & 0o777 == 0o700
        assert state.parent.stat().st_mode & 0o777 == 0o700
    original_lstat = Path.lstat

    def wrong_owner(path):
        identity = original_lstat(path)
        if path == state:
            fields = list(identity)
            fields[4] = os.getuid() + 1
            return os.stat_result(fields)
        return identity

    monkeypatch.setattr(Path, "lstat", wrong_owner)
    with pytest.raises(runtime_state.RuntimeStateError):
        with runtime_state.runtime_state_directory(state):
            pytest.fail("wrong owner accepted")
    monkeypatch.setattr(Path, "lstat", original_lstat)
    with pytest.raises(runtime_state.RuntimeStateError):
        with runtime_state.runtime_state_directory(state):
            state.rename(tmp_path / "old-state")
            state.mkdir(mode=0o700)


def test_runtime_state_windows_rejects_reparse_without_using_posix_mode_as_acl():
    import stat

    from app.research_web import runtime_state

    windows_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_file_attributes=0)
    runtime_state._validate_directory(windows_identity, leaf=True, platform_name="nt")
    windows_identity.st_file_attributes = 0x400
    with pytest.raises(runtime_state.RuntimeStateError):
        runtime_state._validate_directory(windows_identity, leaf=True, platform_name="nt")


def test_runtime_state_disappearance_during_open_is_rejected_before_body(tmp_path, monkeypatch):
    from app.research_web import runtime_state

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    original_lstat = Path.lstat
    calls = 0

    def disappear(path):
        nonlocal calls
        if path == state:
            calls += 1
            if calls == 2:
                raise FileNotFoundError("simulated concurrent replacement")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", disappear)
    with pytest.raises(runtime_state.RuntimeStateError, match="runtime_state_unsafe"):
        with runtime_state.runtime_state_directory(state):
            pytest.fail("changed directory accepted")


def test_runtime_state_boundary_preserves_caller_errors(tmp_path):
    from app.research_web.runtime_state import runtime_state_directory

    failure = ValueError("caller validation failed")
    with pytest.raises(ValueError) as raised:
        with runtime_state_directory(tmp_path / "state", create=True):
            raise failure
    assert raised.value is failure


def test_runtime_projects_only_active_host_verified_mcp_bindings(tmp_path, monkeypatch):
    installation_id = "mcp-installation-0123456789abcdef0123456789abcdef"
    authorization = AuthorizationManager(tmp_path)
    snapshot = authorization.register_tool(
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_filing",
        description="Read one filing",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        output_schema=None,
        risk_tier="read_only",
    )
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(exist_ok=True)
    active = runtime / "active.json"
    active.write_text(json.dumps({"schema_version": 1, "installation_ids": [installation_id]}))
    active.chmod(0o600)
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")

    bindings = launch_runtime.load_mcp_runtime_bindings(tmp_path)

    assert bindings[0]["schema_sha256"] == snapshot["schema_sha256"]
    assert bindings[0]["name"] == f"mcp__{installation_id}__read_filing"


def test_runtime_ignores_mcp_activation_when_feature_is_disabled(tmp_path, monkeypatch):
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(parents=True)
    (runtime / "active.json").write_text("not-json")
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")

    assert launch_runtime.load_mcp_runtime_bindings(tmp_path) == []


def test_runtime_launch_enables_mcp_bindings_by_default(monkeypatch):
    monkeypatch.delenv("RESEARCH_MCP_RUNTIME_ENABLED", raising=False)

    assert launch_runtime.mcp_runtime_enabled() is True


def test_research_runtime_readiness_accepts_only_python_312_with_required_packages(
    tmp_path, monkeypatch
):
    python = tmp_path / "python"
    python.touch()
    observed = {}

    def run(command, **options):
        observed["command"] = command
        observed["options"] = options
        return SimpleNamespace(
            returncode=0,
            stdout='{"version":[3,12],"packages":["numpy","pandas","matplotlib","openpyxl"]}\n',
            stderr="",
        )

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    launch_runtime.validate_research_python(python)

    assert observed["command"][0] == str(python)
    assert observed["options"]["env"] == {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}


@pytest.mark.parametrize(
    "stdout,returncode",
    [
        ('{"version":[3,11],"packages":["numpy","pandas","matplotlib","openpyxl"]}\n', 0),
        ('{"version":[3,12],"packages":["numpy","pandas","matplotlib"]}\n', 0),
        ("[]\n", 0),
        ("", 1),
    ],
)
def test_research_runtime_readiness_fails_closed_with_stable_code(
    tmp_path, monkeypatch, stdout, returncode
):
    python = tmp_path / "python"
    python.touch()
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=returncode, stdout=stdout, stderr="private provider detail"
        ),
    )

    with pytest.raises(RuntimeError, match="^runtime_not_ready$"):
        launch_runtime.validate_research_python(python)


def test_runtime_rejects_non_object_mcp_activation_without_leaking_parser_errors(
    tmp_path, monkeypatch
):
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(parents=True)
    active = runtime / "active.json"
    active.write_text("[]")
    active.chmod(0o600)
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")

    with pytest.raises(RuntimeError, match="激活清单无效"):
        launch_runtime.load_mcp_runtime_bindings(tmp_path)


def make_tabbit_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    vendor.mkdir(parents=True)
    archive = vendor / "dsh-tabbit-0.3.4.tgz"
    package = json.dumps({"name": "dsh-tabbit", "version": "0.3.4"}).encode()
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("package/package.json")
        info.size = len(package)
        bundle.addfile(info, io.BytesIO(package))
        module = b"export const name = 'tabbit';"
        info = tarfile.TarInfo("package/lib/core/index.js")
        info.size = len(module)
        bundle.addfile(info, io.BytesIO(module))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    license_path = vendor / "LICENSE"
    license_path.write_text("MIT test license\n")
    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "name": "dsh-tabbit",
                "version": "0.3.4",
                "source_commit": "361ef61f4d42ae51d657ca1351acacd6b5db5d44",
                "archive": archive.name,
                "sha256": digest,
                "license": "MIT",
                "license_sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
                "files": ["lib/core/index.js", "package.json"],
            }
        )
    )
    return vendor


def test_tabbit_archive_is_verified_and_staged_into_private_profile(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    home = tmp_path / "home"
    profile = home / "profiles/web"
    profile.mkdir(parents=True)
    (profile / "package.json").write_text(
        json.dumps(
            {
                "name": "dsh-profile-web",
                "private": True,
                "dependencies": {},
                "dsh": {
                    "profile": {
                        "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"],
                        "patchReload": "live",
                    }
                },
            }
        )
    )

    result = launch_runtime.stage_tabbit_package(vendor, home)

    installed = home / "profiles/node_modules/dsh-tabbit"
    assert json.loads((installed / "package.json").read_text())["version"] == "0.3.4"
    profile_package = json.loads((profile / "package.json").read_text())
    assert profile_package["dependencies"]["dsh-tabbit"] == "0.3.4"
    assert profile_package["dsh"]["profile"]["bundles"][-1] == "dsh-tabbit"
    assert result["source_commit"] == "361ef61f4d42ae51d657ca1351acacd6b5db5d44"


def test_tabbit_archive_hash_mismatch_fails_closed(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    manifest = json.loads((vendor / "manifest.json").read_text())
    manifest["sha256"] = "0" * 64
    (vendor / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="完整性"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")


def test_tabbit_license_or_file_manifest_mismatch_fails_closed(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    (vendor / "LICENSE").write_text("changed")
    with pytest.raises(RuntimeError, match="许可证"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")

    vendor = make_tabbit_vendor(tmp_path / "second")
    manifest = json.loads((vendor / "manifest.json").read_text())
    manifest["files"] = ["package.json"]
    (vendor / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="文件清单"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")


def test_tabbit_archive_member_paths_use_posix_manifest_semantics():
    assert launch_runtime._tabbit_archive_parts("package/lib/core/index.js") == (
        "package",
        "lib",
        "core",
        "index.js",
    )
    with pytest.raises(RuntimeError, match="不安全路径"):
        launch_runtime._tabbit_archive_parts(r"package\..\outside.js")


def test_runtime_atomic_json_uses_windows_compatible_permissions(tmp_path, monkeypatch):
    target = tmp_path / "profile" / "package.json"
    monkeypatch.delattr(launch_runtime.os, "fchmod", raising=False)
    monkeypatch.setattr(launch_runtime.os, "name", "nt")

    launch_runtime._atomic_json(target, {"name": "研究运行时"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"name": "研究运行时"}


def test_runtime_overlay_disables_installer_and_keeps_fetch_takeover_off_by_default(tmp_path):
    config = launch_runtime.load_tabbit_config(tmp_path)
    overlay = launch_runtime.tabbit_overlay(config, PureWindowsPath("/adapter.mjs"))

    assert config == {
        "browser_enabled": True,
        "web_fetch_enabled": False,
        "instance_id": None,
    }
    assert "id: tabbit-installer\n  disabled: true" in overlay
    assert "id: tabbit-tool-browser\n  disabled: false" in overlay
    assert "fetchProvider: http" in overlay
    assert 'name: "/adapter.mjs"' in overlay


@pytest.mark.parametrize("version", ["v22.19.0", "v22.20.1", "v24.0.0", "v24.19.0"])
def test_tabbit_node_supported_versions(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    assert launch_runtime.validate_tabbit_node("node") == version.removeprefix("v")


@pytest.mark.parametrize("version", ["v22.18.0", "v23.9.0", "v25.9.0", "v21.20.0"])
def test_tabbit_node_unsupported_versions_fail_closed(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    with pytest.raises(RuntimeError, match="22.19"):
        launch_runtime.validate_tabbit_node("node")


@pytest.mark.parametrize(("target", "stage"), [
    ("validate_tabbit_node", "launcher_node"),
    ("prepare", "launcher_prepare"),
    ("prepare_runtime_module_fallback", "launcher_modules"),
    ("stage_tabbit_package", "launcher_tabbit_package"),
    ("stage_tabbit_adapter", "launcher_tabbit_adapter"),
    ("_atomic_json", "launcher_config"),
    ("execve", "launcher_exec"),
])
def test_launcher_failure_emits_fixed_stage_without_exception_text(tmp_path, monkeypatch, target, stage):
    messages = []
    monkeypatch.setattr(sys, "argv", ["launcher", "--source", str(tmp_path), "--data", str(tmp_path)])
    monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
    monkeypatch.setattr(launch_runtime, "log", SimpleNamespace(
        error=lambda event, **fields: messages.append((event, fields)), info=lambda *args, **kwargs: None,
    ))
    monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda *args: "24.19.0")
    monkeypatch.setattr(launch_runtime, "prepare", lambda *args, **kwargs: (["node"], {}, tmp_path))
    monkeypatch.setattr(launch_runtime, "prepare_runtime_module_fallback", lambda *args: 1)
    monkeypatch.setattr(launch_runtime, "stage_tabbit_package", lambda *args: {"version": "fixture", "source_commit": "fixture"})
    monkeypatch.setattr(launch_runtime, "stage_tabbit_adapter", lambda *args: None)
    monkeypatch.setattr(launch_runtime, "load_tabbit_config", lambda *args: {})
    monkeypatch.setattr(launch_runtime, "_atomic_json", lambda *args: None)
    monkeypatch.setattr(launch_runtime.os, "chdir", lambda *args: None)
    def fail(*args, **kwargs):
        raise PermissionError(13, "fixture-private-path-command-token")
    if target == "execve":
        monkeypatch.setattr(launch_runtime.os, target, fail)
    else:
        monkeypatch.setattr(launch_runtime, target, fail)
    with pytest.raises(SystemExit) as error:
        launch_runtime.main()
    assert error.value.code == 1
    records = [json.loads(event.removeprefix("container_startup_failure "))
               for event, _ in messages if event.startswith("container_startup_failure ")]
    assert records == [{"stage": stage, "exception_class": "PermissionError", "errno": 13,
                        "runtime_returncode": None, "web_returncode": None}]
    assert "fixture-private" not in json.dumps(messages)
