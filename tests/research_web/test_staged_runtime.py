"""Derived image inventory must not weaken the Native DSH source contract."""

import json
import os
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
