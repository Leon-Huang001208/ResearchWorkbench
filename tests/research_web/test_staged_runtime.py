"""Derived image inventory must not weaken the Native DSH source contract."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.research_web import RUNTIME_CONTRACT


def facts():
    return {
        "commit": RUNTIME_CONTRACT.dsh_commit,
        "remote": RUNTIME_CONTRACT.dsh_remote,
        "pnpm": RUNTIME_CONTRACT.dsh_pnpm,
        "closure_sha256": "a" * 64,
        "closure_files": RUNTIME_CONTRACT.dsh_closure_files,
    }


def staged(tmp_path):
    from app.research_web.staged_runtime import write_staged_manifest

    root = tmp_path / "runtime"
    root.mkdir()
    for name in ("apps/cli/lib/bin.js", "apps/cli/package.json", "packages/boot/app-boot/lib/index.js"):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}" if name.endswith("json") else "// built runtime")
    modules = root / "apps/cli/node_modules"
    modules.mkdir()
    (modules / "boot").symlink_to("../../../packages/boot/app-boot")
    for name in ("objects", "refs"):
        (root / ".git" / name).mkdir(parents=True)
    (root / ".git/HEAD").write_text(RUNTIME_CONTRACT.dsh_commit + "\n")
    write_staged_manifest(root, facts())
    return root


def test_staged_manifest_returns_original_verified_closure(tmp_path):
    from app.research_web.staged_runtime import verify_staged_runtime

    assert verify_staged_runtime(staged(tmp_path)) == facts()


def test_launcher_uses_original_source_closure_for_staged_state_lock(tmp_path, monkeypatch):
    from app.research_web.launch_runtime import prepare

    source = staged(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    prepare(source, data, "/node", 3081)
    lock = json.loads((data / "runtime/build-lock.json").read_text())
    assert lock["closure_sha256"] == facts()["closure_sha256"]
    assert lock["closure_files"] == facts()["closure_files"]


def test_launcher_rejects_staged_tampering_before_data_mutation(tmp_path, monkeypatch):
    from app.research_web.launch_runtime import prepare

    source = staged(tmp_path)
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    (source / "apps/cli/lib/bin.js").write_text("tampered")
    data = tmp_path / "data"
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        prepare(source, data, "/node", 3081)
    assert not data.exists()


def test_container_launcher_requires_manifest_and_rejects_source_mode(tmp_path, monkeypatch):
    from app.research_web.launch_runtime import prepare
    from app.research_web.staged_runtime import MANIFEST

    source = staged(tmp_path)
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        prepare(source, tmp_path / "data", "/node", 3081, source_mode=True)
    (source / MANIFEST).unlink()
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        prepare(source, tmp_path / "data", "/node", 3081)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("flag", [None, "", "0", "invalid", "true", "01", " 1", "1 "])
def test_native_ignores_forged_staged_inventory_and_detects_changed_js(
    tmp_path, monkeypatch, flag
):
    from app.research_web.launch_runtime import calculate_build_closure, prepare
    from app.research_web.staged_runtime import MANIFEST, write_staged_manifest

    if flag is None:
        monkeypatch.delenv("RWB_DSH_STAGED", raising=False)
    else:
        monkeypatch.setenv("RWB_DSH_STAGED", flag)
    source = staged(tmp_path)
    data = tmp_path / "data"
    actual_hash, actual_count = calculate_build_closure(source)
    prepare(source, data, "/node", 3081)
    lock_path = data / "runtime/build-lock.json"
    original_lock = lock_path.read_bytes()
    lock = json.loads(original_lock)
    assert (lock["closure_sha256"], lock["closure_files"]) == (actual_hash, actual_count)

    # An attacker regenerates the inventory after editing JS, retaining stale
    # claimed source facts. Native must still detect the real closure change.
    (source / "apps/cli/lib/bin.js").write_text("// modified JS")
    (source / MANIFEST).unlink()
    write_staged_manifest(source, facts())
    with pytest.raises(RuntimeError, match="DSH 构建发生变化"):
        prepare(source, data, "/node", 3081)
    assert lock_path.read_bytes() == original_lock


@pytest.mark.parametrize("flag", [None, "", "0", "invalid", "true", "01", " 1", "1 "])
def test_native_does_not_read_or_validate_an_unselected_staged_manifest(
    tmp_path, monkeypatch, flag
):
    from app.research_web.launch_runtime import calculate_build_closure, prepare
    from app.research_web.staged_runtime import MANIFEST

    if flag is None:
        monkeypatch.delenv("RWB_DSH_STAGED", raising=False)
    else:
        monkeypatch.setenv("RWB_DSH_STAGED", flag)
    source = staged(tmp_path)
    (source / MANIFEST).write_text("not JSON")
    prepare(source, tmp_path / "data", "/node", 3081)
    lock = json.loads((tmp_path / "data/runtime/build-lock.json").read_text())
    assert (lock["closure_sha256"], lock["closure_files"]) == calculate_build_closure(source)


def test_staged_manifest_rejects_ambiguous_duplicate_keys(tmp_path):
    from app.research_web.staged_runtime import MANIFEST, verify_staged_runtime

    source = staged(tmp_path)
    path = source / MANIFEST
    path.write_text(path.read_text().replace('"schema_version":1', '"schema_version":2,"schema_version":1'))
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        verify_staged_runtime(source)


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra", "empty-directory", "mode", "outside-link", "dangling-link", "hardlink", "manifest-link", "root-link"])
def test_staged_manifest_rejects_tampering_and_aliases(tmp_path, mutation):
    from app.research_web.staged_runtime import MANIFEST, verify_staged_runtime

    root = staged(tmp_path)
    entry = root / "apps/cli/lib/bin.js"
    if mutation == "changed":
        entry.write_text("tampered")
    elif mutation == "missing":
        entry.unlink()
    elif mutation == "extra":
        (root / "unreviewed.js").write_text("unexpected")
    elif mutation == "empty-directory":
        (root / "unexpected").mkdir()
    elif mutation == "mode":
        entry.chmod(0o777)
    elif mutation in {"outside-link", "dangling-link"}:
        entry.unlink()
        entry.symlink_to(tmp_path / "outside" if mutation == "outside-link" else "missing.js")
    elif mutation == "hardlink":
        os.link(entry, tmp_path / "alias")
    elif mutation == "manifest-link":
        (root / MANIFEST).rename(tmp_path / "manifest")
        (root / MANIFEST).symlink_to(tmp_path / "manifest")
    elif mutation == "root-link":
        (tmp_path / "alias").symlink_to(root, target_is_directory=True)
        root = tmp_path / "alias"
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        verify_staged_runtime(root)


@pytest.mark.parametrize("field", ["commit", "remote", "pnpm", "closure_files", "closure_sha256", "schema_version", "assets_sha256", "asset_count"])
def test_staged_manifest_rejects_wrong_facts_and_schema(tmp_path, field):
    from app.research_web.staged_runtime import MANIFEST, verify_staged_runtime

    root = staged(tmp_path)
    path = root / MANIFEST
    value = json.loads(path.read_text())
    target = value["source"] if field in facts() else value
    target[field] = "wrong"
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        verify_staged_runtime(root)


def test_required_missing_and_oversized_manifest_fail_closed(tmp_path):
    from app.research_web.staged_runtime import MANIFEST, MAX_MANIFEST_BYTES, verify_staged_runtime

    root = staged(tmp_path)
    (root / MANIFEST).unlink()
    assert verify_staged_runtime(root) is None
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        verify_staged_runtime(root, required=True)
    with (root / MANIFEST).open("wb") as stream:
        stream.truncate(MAX_MANIFEST_BYTES + 1)
    with pytest.raises(RuntimeError, match="staged_runtime_invalid"):
        verify_staged_runtime(root)


def test_runtime_staging_copies_only_production_package_assets(tmp_path):
    from docker.stage_dsh import stage_assets
    from app.research_web.staged_runtime import verify_staged_runtime

    source = tmp_path / "source"
    cli = source / "apps/cli"
    boot = source / "packages/boot/app-boot"
    for folder in (cli, boot):
        (folder / "lib").mkdir(parents=True)
        (folder / "tests/fixtures").mkdir(parents=True)
        (folder / "tests/fixtures/secret.json").write_text("fixture")
        (folder / "README.md").write_text("developer docs")
    (cli / "package.json").write_text(json.dumps({"name": "cli", "files": ["lib"], "dependencies": {"boot": "1"}, "devDependencies": {"testkit": "1"}}))
    (boot / "package.json").write_text(json.dumps({"name": "boot", "files": ["lib"]}))
    (cli / "lib/bin.js").write_text("// bin")
    (boot / "lib/index.js").write_text("// boot")
    (cli / "node_modules").mkdir()
    (cli / "node_modules/boot").symlink_to("../../../packages/boot/app-boot")
    (source / "node_modules/testkit").mkdir(parents=True)
    (source / "node_modules/testkit/package.json").write_text('{"name":"testkit"}')
    for name in (".github/actions", "docs", "benchmarks", "website"):
        (source / name).mkdir(parents=True)
        (source / name / "unneeded.json").write_text("{}")
    (source / "package.json").write_text("{}")
    output = tmp_path / "staged"
    stage_assets(source, output, facts())
    assert verify_staged_runtime(output) == facts()
    names = [str(path.relative_to(output)) for path in output.rglob("*")]
    assert "apps/cli/lib/bin.js" in names
    assert "packages/boot/app-boot/lib/index.js" in names
    assert (output / "apps/cli/node_modules/boot/lib/index.js").is_file()
    assert not any(part in {"tests", "fixtures", "docs", "benchmarks", "website", ".github", "testkit"} for name in names for part in Path(name).parts)


def test_staging_refuses_unsafe_dependency_target(tmp_path):
    from docker.stage_dsh import stage_assets

    source = tmp_path / "source"
    cli = source / "apps/cli"
    (cli / "node_modules").mkdir(parents=True)
    (cli / "package.json").write_text('{"name":"cli","dependencies":{"escape":"1"}}')
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "package.json").write_text('{"name":"escape"}')
    (cli / "node_modules/escape").symlink_to(outside)
    with pytest.raises(RuntimeError, match="dsh_staging_invalid"):
        stage_assets(source, tmp_path / "staged", facts())


@pytest.mark.parametrize("platform_name", ["native-platform", "@fixture/native-platform"])
def test_staging_preserves_selected_pnpm_hoist_for_dynamic_native_loader(tmp_path, platform_name):
    from docker.stage_dsh import stage_assets
    from app.research_web.staged_runtime import verify_staged_runtime

    source = tmp_path / "source"
    cli = source / "apps/cli"
    boot = source / "packages/boot/app-boot"
    store = source / "node_modules/.pnpm"
    helper = store / "helper@1/node_modules/helper"
    dispatcher = store / "dispatcher@1/node_modules/dispatcher"
    platform = store / "native-platform@1/node_modules" / platform_name
    dev = store / "devkit@1/node_modules/devkit"
    for package, metadata, code in [
        (cli, {"name": "cli", "files": ["lib"], "dependencies": {"boot": "1", "helper": "1"}, "devDependencies": {"devkit": "1"}}, "module.exports = require('helper');"),
        (boot, {"name": "boot", "files": ["lib"]}, "module.exports = {};"),
        (helper, {"name": "helper", "dependencies": {"dispatcher": "1"}, "optionalDependencies": {platform_name: "1"}}, "module.exports = require('dispatcher')();"),
        (dispatcher, {"name": "dispatcher"}, f"module.exports = () => require({json.dumps(platform_name)});"),
        (platform, {"name": platform_name}, "module.exports = 'fixture-native-binding';"),
        (dev, {"name": "devkit"}, "module.exports = 'must-not-stage';"),
    ]:
        (package / "lib").mkdir(parents=True)
        metadata["main"] = "lib/index.js"
        (package / "package.json").write_text(json.dumps(metadata))
        (package / "lib/index.js").write_text(code)
    (cli / "lib/bin.js").write_text("// required cli asset")

    def link(alias, target):
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(os.path.relpath(target, alias.parent))

    link(cli / "node_modules/boot", boot)
    link(cli / "node_modules/helper", helper)
    link(helper.parent / "dispatcher", dispatcher)
    link(helper.parent / platform_name, platform)
    link(store / "node_modules" / platform_name, platform)
    link(store / "node_modules/devkit", dev)
    link(store / "node_modules/absent-dev-platform", store / "uninstalled-dev-platform")
    (source / "package.json").write_text("{}")
    output = tmp_path / "staged"
    stage_assets(source, output, facts())
    node = shutil.which("node")
    assert node is not None, "Node is required for the runtime packaging contract"
    probe = "console.log(require(process.argv[1]));"
    original = subprocess.run([node, "-e", probe, str(cli)], capture_output=True, text=True, timeout=10)
    assert original.returncode == 0 and original.stdout.strip() == "fixture-native-binding"
    derived = subprocess.run([node, "-e", probe, str(output / "apps/cli")], capture_output=True, text=True, timeout=10)
    assert derived.returncode == 0, derived.stderr
    assert derived.stdout.strip() == "fixture-native-binding"
    assert verify_staged_runtime(output) == facts()
    assert not os.path.lexists(output / "node_modules/.pnpm/node_modules/absent-dev-platform")
    assert not (output / "node_modules/.pnpm/node_modules/devkit").exists()
    assert not (output / dev.relative_to(source)).exists()


@pytest.mark.parametrize("peer_name", ["typescript", "@fixture/typescript"])
@pytest.mark.parametrize("mutation", [None, "root-link", "broken-peer", "outside-peer", "conflict", "replacement", "asset-escape"])
def test_staging_preserves_selected_root_optional_peer_for_virtual_alias_anchor(tmp_path, monkeypatch, peer_name, mutation):
    from docker.stage_dsh import stage_assets

    source = tmp_path / "source"
    cli = source / "apps/cli"
    boot = source / "packages/boot/app-boot"
    store = source / "node_modules/.pnpm"
    history = store / "history@1/node_modules/history"
    peer = store / "typescript@1/node_modules" / peer_name
    dev = store / "devkit@1/node_modules/devkit"
    for package, metadata in [
        (cli, {"name": "cli", "files": ["lib"], "dependencies": {"boot": "1", "history": "1"}}),
        (boot, {"name": "boot", "files": ["lib"]}),
        (history, {"name": "history", "peerDependencies": {peer_name: "1"}, "peerDependenciesMeta": {peer_name: {"optional": True}}}),
        (peer, {"name": peer_name}),
        (dev, {"name": "devkit"}),
    ]:
        (package / "lib").mkdir(parents=True)
        metadata["main"] = "lib/index.js"
        (package / "package.json").write_text(json.dumps(metadata))
        (package / "lib/index.js").write_text("module.exports = {};")
    (cli / "lib/bin.js").write_text("// required cli asset")

    def link(alias, target):
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(os.path.relpath(target, alias.parent))

    link(cli / "node_modules/boot", boot)
    link(cli / "node_modules/history", history)
    link(history.parent / peer_name, peer)
    link(source / "node_modules" / peer_name, peer)
    link(source / "node_modules/devkit", dev)
    link(source / "node_modules/absent-dev", store / "absent-dev")
    (source / "package.json").write_text('{"devDependencies":{"devkit":"1"}}')
    output = tmp_path / "staged"
    if mutation:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "package.json").write_text('{"name":"outside"}')
        if mutation == "root-link":
            (source / "node_modules").rename(source / "aliased-modules")
            (source / "node_modules").symlink_to("aliased-modules")
        elif mutation in {"broken-peer", "outside-peer"}:
            canonical = history.parent / peer_name
            canonical.unlink()
            canonical.symlink_to(outside if mutation == "outside-peer" else "missing")
        elif mutation == "asset-escape":
            (peer / "lib/index.js").unlink()
            (peer / "lib/index.js").symlink_to(outside / "package.json")
        elif mutation == "conflict":
            original_copy = shutil.copy2

            def conflicting_copy(src, dst, *args, **kwargs):
                result = original_copy(src, dst, *args, **kwargs)
                alias = output / "node_modules" / peer_name
                if Path(src) == peer / "lib/index.js":
                    alias.parent.mkdir(parents=True, exist_ok=True)
                    alias.write_text("conflict")
                return result

            monkeypatch.setattr(shutil, "copy2", conflicting_copy)
        elif mutation == "replacement":
            original_resolve = Path.resolve

            def replaced_resolve(path, strict=False):
                if path == source / "node_modules" / peer_name and strict:
                    return outside
                return original_resolve(path, strict=strict)

            monkeypatch.setattr(Path, "resolve", replaced_resolve)
        with pytest.raises(RuntimeError, match="dsh_staging_invalid"):
            stage_assets(source, output, facts())
        return
    stage_assets(source, output, facts())
    node = shutil.which("node")
    assert node is not None, "Node is required for the runtime packaging contract"
    # Pinned DSH searches paths from a virtual alias anchor, not the real package
    # directory. The canonical peer alias alone cannot satisfy this lookup.
    probe = "const {createRequire}=require('node:module'); const fs=require('node:fs'); const path=require('node:path'); const r=createRequire(process.argv[1]); const p=r.resolve.paths(process.argv[2]).map(p=>path.join(p,process.argv[2])).find(p=>fs.existsSync(path.join(p,'package.json'))); if(!p)process.exit(7); console.log(fs.realpathSync(p));"
    for tree in (source, output):
        result = subprocess.run(
            [node, "-e", probe, str(tree / "virtual/profile/modules/history/index.js"), peer_name],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(tree / peer.relative_to(source))
    alias = output / "node_modules" / peer_name
    assert alias.is_symlink() and not Path(os.readlink(alias)).is_absolute()
    assert alias.resolve(strict=True) == output / peer.relative_to(source)
    assert not os.path.lexists(output / "node_modules/devkit")
    assert not os.path.lexists(output / "node_modules/absent-dev")
    assert not (output / dev.relative_to(source)).exists()
