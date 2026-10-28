"""Only byte-identical managed-prefix relocation may publish builtin successors."""

import copy
import json
from pathlib import Path

import pytest

from app.research_web.capabilities import seeds
from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.pack_resources import (
    MANIFEST_PATH,
    canonical,
    closure,
    pack_packages,
)
from app.research_web.capabilities.packages import decode_file, encode_file

CID = "research-pack-research-prep"


def runtime_value(value):
    return json.loads(
        decode_file(
            next(file for file in value["files"] if file["path"] == "references/runtime.json")
        )
    )


def replace_runtime(value, runtime):
    value["files"] = [
        (
            encode_file(file["path"], canonical(runtime))
            if file["path"] == "references/runtime.json"
            else file
        )
        for file in value["files"]
    ]
    manifest = json.loads(
        decode_file(next(file for file in value["files"] if file["path"] == MANIFEST_PATH))
    )
    manifest["files"] = [
        {"path": f["path"], "sha256": f["sha256"]}
        for f in sorted(value["files"], key=lambda item: item["path"])
        if f["path"] != MANIFEST_PATH
    ]
    manifest["closure_sha256"] = closure(value["files"])
    value["files"] = [
        encode_file(MANIFEST_PATH, canonical(manifest)) if file["path"] == MANIFEST_PATH else file
        for file in value["files"]
    ]


def historical_catalog(tmp_path, monkeypatch):
    def old_packages():
        values = list(pack_packages())
        for cid, value in values:
            if cid != CID:
                continue
            runtime = runtime_value(value)
            previous = Path(runtime["environment"])
            old = tmp_path / "old-managed-install"
            runtime["environment"] = str(old)
            for package in runtime["dependencies"]:
                package["origin"] = str(old / Path(package["origin"]).relative_to(previous))
            if Path(runtime["python"]).is_relative_to(previous):
                runtime["python"] = str(old / Path(runtime["python"]).relative_to(previous))
            replace_runtime(value, runtime)
        return values

    with monkeypatch.context() as startup:
        startup.setattr(seeds, "pack_packages", old_packages)
        return CapabilityCatalog(tmp_path / "account")


@pytest.mark.parametrize("disabled", [False, True])
def test_exact_curated_prefix_relocation_creates_version_and_preserves_old(
    disabled, tmp_path, monkeypatch
):
    catalog = historical_catalog(tmp_path, monkeypatch)
    # Publication mechanics only; this is not a historical-read certificate.
    monkeypatch.setattr(
        CapabilityCatalog, "_pack_read_equivalence_ready", lambda *_args: True, raising=False
    )
    if disabled:
        catalog.transition(CID, "disable")
    before = copy.deepcopy(catalog.row(CID)["versions"]["1"])
    old_files = {
        path.relative_to(catalog.version_path(CID, 1)).as_posix(): path.read_bytes()
        for path in catalog.version_path(CID, 1).rglob("*")
        if path.is_file()
    }
    restored = CapabilityCatalog(catalog.data_root)
    row = restored.row(CID)
    assert row["version"] == 2
    assert row["versions"]["1"] == before
    assert row["status"] == ("disabled" if disabled else "enabled")
    assert row["runtime_binding"]["status"] == "relocated"
    assert all(
        (restored.version_path(CID, 1) / name).read_bytes() == raw
        for name, raw in old_files.items()
    )
    assert (restored.native_root / CID).exists() is not disabled


@pytest.mark.parametrize(
    "changed",
    [
        "metadata",
        "tools",
        "policy",
        "instructions",
        "code",
        "dependency",
        "interpreter",
        "abi",
        "platform",
        "entry_policy",
        "runtime_schema",
        "validation_profile",
        "extra_file",
        "source",
        "draft",
    ],
)
def test_any_nonrelocation_change_blocks_without_overwriting_history(
    changed, tmp_path, monkeypatch
):
    catalog = historical_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(
        CapabilityCatalog, "_pack_read_equivalence_ready", lambda *_args: True, raising=False
    )
    row = catalog.row(CID)
    if changed == "draft":
        row["has_draft"] = True
    elif changed == "metadata":
        row["draft"]["metadata"]["description"] += " user edit"
    elif changed == "tools":
        row["draft"]["metadata"]["required_tools"].append("web_search")
    elif changed == "policy":
        row["draft"]["metadata"]["method_policy"]["recommended"] = ["first-principles"]
    elif changed == "instructions":
        row["draft"]["instructions"] += "\nuser edit\n"
    elif changed == "code":
        for body in (row["draft"], row["versions"]["1"]):
            body["files"] = [
                (
                    encode_file(f["path"], decode_file(f) + b"\n# user edit\n")
                    if f["path"] == "scripts/calculate.py"
                    else f
                )
                for f in body["files"]
            ]
    elif changed in {
        "dependency",
        "interpreter",
        "abi",
        "platform",
        "entry_policy",
        "runtime_schema",
        "validation_profile",
    }:
        for body in (row["draft"], row["versions"]["1"]):
            runtime = runtime_value(body)
            if changed == "dependency":
                runtime["dependencies"][0]["closure_sha256"] = "0" * 64
            elif changed == "runtime_schema":
                runtime["schema"] = "research_pack_runtime_v2"
            elif changed == "validation_profile":
                runtime["validation_profile"]["sha256"] = "0" * 64
            else:
                runtime[
                    {
                        "interpreter": "python_sha256",
                        "abi": "python_abi",
                        "platform": "platform",
                        "entry_policy": "entry_policy",
                    }[changed]
                ] = "different"
            replace_runtime(body, runtime)
    elif changed == "extra_file":
        directory = catalog.version_path(CID, 1) / "references"
        directory.chmod(0o700)
        try:
            (directory / "unlisted.json").write_text("{}")
        finally:
            directory.chmod(0o555)
    else:
        row["source"] = "manual"
    catalog.save()
    old = copy.deepcopy(row["versions"])
    restored = CapabilityCatalog(catalog.data_root)
    assert restored.row(CID)["version"] == 1
    assert restored.row(CID)["versions"] == old
    assert restored.row(CID)["runtime_binding"]["status"] == "blocked"


def test_user_copy_is_never_relocated_or_rewritten(tmp_path, monkeypatch):
    catalog = historical_catalog(tmp_path, monkeypatch)
    copied = catalog.copy(CID, "用户历史副本", "historical-user-copy")
    before = copy.deepcopy(catalog.row(copied["id"]))
    restored = CapabilityCatalog(catalog.data_root)
    assert restored.row(copied["id"]) == before


def test_production_relocation_is_blocked_until_historical_read_certificate_exists(
    tmp_path, monkeypatch
):
    catalog = historical_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(CapabilityCatalog, "_pack_read_equivalence_ready", lambda *_args: False)
    before = copy.deepcopy(catalog.row(CID)["versions"])
    restored = CapabilityCatalog(catalog.data_root)
    row = restored.row(CID)
    assert row["version"] == 1
    assert row["versions"] == before
    assert row["runtime_binding"] == {
        "status": "blocked",
        "code": "pack_runtime_read_equivalence_pending",
    }


def test_multiple_relocations_issue_direct_facts_and_never_accept_transitive_only(
    tmp_path, monkeypatch
):
    from app.research_web.capabilities import pack_dependencies, pack_resources
    from app.research_web.capabilities.models import CapabilityError
    from app.research_web.capabilities.pack_equivalence import verify

    original = historical_catalog(tmp_path, monkeypatch)
    first = original.selection(CID)
    first = {key: first[key] for key in ("id", "version", "sha256", "native_name", "resource_path")}
    second = CapabilityCatalog(original.data_root)
    assert second.row(CID)["version"] == 2
    third_runtime = copy.deepcopy(pack_dependencies.runtime_identity())
    prefix = Path(third_runtime["environment"])
    new = tmp_path / "third-managed-prefix"
    third_runtime["environment"] = str(new)
    for dependency in third_runtime["dependencies"]:
        dependency["origin"] = str(new / Path(dependency["origin"]).relative_to(prefix))
    if Path(third_runtime["python"]).is_relative_to(prefix):
        third_runtime["python"] = str(new / Path(third_runtime["python"]).relative_to(prefix))
    monkeypatch.setattr(pack_dependencies, "runtime_identity", lambda: copy.deepcopy(third_runtime))
    monkeypatch.setattr(pack_resources, "runtime_identity", lambda: copy.deepcopy(third_runtime))
    third = CapabilityCatalog(original.data_root)
    assert third.row(CID)["version"] == 3
    assert verify(third, first)["version"] == 3
    direct = next(
        key
        for key, value in third.data["pack_read_equivalences"].items()
        if value["capability_id"] == CID and value["from_version"] == 1 and value["to_version"] == 3
    )
    del third.data["pack_read_equivalences"][direct]
    with pytest.raises(CapabilityError):
        verify(third, first)


def test_terminal_certificate_commit_failure_leaves_no_usable_certificate(tmp_path, monkeypatch):
    import app.research_web.capabilities.catalog as catalog_module
    from app.research_web.capabilities.models import CapabilityError

    catalog = historical_catalog(tmp_path, monkeypatch)
    old = copy.deepcopy(catalog.row(CID)["versions"]["1"])
    original = catalog_module.os.replace
    failed = []

    def fail_once(source, target, *args, **kwargs):
        if (
            Path(target) == catalog.index
            and catalog.data.get("pending") is None
            and catalog.data.get("pack_read_equivalences")
            and not failed
        ):
            failed.append(True)
            raise OSError("simulated terminal disk replace failure")
        return original(source, target, *args, **kwargs)

    monkeypatch.setattr(catalog_module.os, "replace", fail_once)
    with pytest.raises(CapabilityError):
        catalog._migrate_pack_runtime_relocations(dict(seeds.seed_packages()))
    assert failed
    on_disk = json.loads(catalog.index.read_bytes())
    assert on_disk["items"][CID]["version"] == 1
    assert on_disk["items"][CID]["versions"]["1"] == old
    assert not on_disk["pack_read_equivalences"]
    restored = CapabilityCatalog(catalog.data_root)
    assert restored.row(CID)["version"] == 1
    assert not restored.data["pack_read_equivalences"]
