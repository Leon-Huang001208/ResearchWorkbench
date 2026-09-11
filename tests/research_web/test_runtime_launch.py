import hashlib
import io
import json
import tarfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from app.research_web import launch_runtime
from app.research_web.mcp_runtime.authorization import AuthorizationManager


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
        assert "healProfilesModuleFallback({ installAnchor: anchor, home })" in args[0][3]
        modules = home / "profiles/node_modules/@deepseek-ai"
        modules.mkdir(parents=True)
        (modules / "dsh-example").symlink_to(target)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1


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


@pytest.mark.parametrize("version", ["v22.19.0", "v22.20.1", "v24.0.0", "v25.9.0"])
def test_tabbit_node_supported_versions(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    assert launch_runtime.validate_tabbit_node("node") == version.removeprefix("v")


@pytest.mark.parametrize("version", ["v22.18.0", "v23.9.0", "v21.20.0"])
def test_tabbit_node_unsupported_versions_fail_closed(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    with pytest.raises(RuntimeError, match="22.19"):
        launch_runtime.validate_tabbit_node("node")
