"""Real frozen writer and independent file readback; no LLM or data source."""

import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def test_native_writer_keeps_full_child_rows_and_bounded_stdout(tmp_path):
    from app.research_web.capabilities.pack_native import run
    from app.research_web.scenarios.packs import execute_pack_bundle

    vectors = json.loads(
        (
            Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
        ).read_bytes()
    )
    vector = next(item for item in vectors if item["id"] == "deduplicate_source_versions.success")
    row = vector["records_by_kind"]["source-version"][0]
    records = []
    for index in range(256):
        copy = json.loads(json.dumps(row))
        copy["row_id"] = str(index)
        copy["document_id"] = str(index)
        copy["version_id"] = str(index)
        copy["parent_version_id"] = None
        copy["content_sha256"] = hashlib.sha256(str(index).encode()).hexdigest()
        records.append(copy)
    parameters = {"as_of": vector["parameters"]["as_of"], "deduplicate_source_versions": {}}
    source = {
        "schema": "research_pack_input_v1",
        "pack_id": "research-prep",
        "records_by_kind": {"source-version": records},
        "parameters": parameters,
        "source_coverage": {},
    }
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(source))
    binding = {
        "execution_id": "a" * 32,
        "call_id": "call-1",
        "task_id": "b" * 24,
        "capability_id": "research-pack-research-prep",
        "version": 1,
        "context_sha256": "c" * 64,
        "closure_sha256": "d" * 64,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "pack_id": "research-prep",
    }
    output_root = "outputs/scenario-results/" + "a" * 32
    target = tmp_path / output_root / "v1"
    target.parent.mkdir(parents=True)
    result = run(input_path, target, binding, calculator=execute_pack_bundle)
    assert len(json.dumps(result).encode()) < 65536
    full = json.loads((target / "full-result.json").read_bytes())
    assert len(full["components"][0]["rows"]) == 256
    assert full["components"][0]["rows"][-1]
    assert result["status"] == "partial"
    for name in ("full-result", "receipt", "manifest"):
        path = target / (name + ".json")
        assert result["artifacts"][name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    from app.research_web.scenario_pack_execution import read_artifacts

    observed = read_artifacts(
        tmp_path,
        {"output_root": output_root, "binding": binding, "scope": {"input_path": "input.json"}},
    )
    assert observed["counts"] == {"root": 1, "components": {"deduplicate_source_versions": 256}}
    assert (
        observed["artifacts"]["full-result"]["sha256"]
        == result["artifacts"]["full-result"]["sha256"]
    )
    from app.research_web.capabilities.pack_resources import canonical
    from app.research_web.store import StoreError

    proof = tmp_path / "before-count-tamper"
    proof.mkdir()
    for name in ("full-result.json", "receipt.json", "manifest.json"):
        (proof / name).write_bytes((target / name).read_bytes())
    full["components"][0]["rows"].pop()
    changed = canonical(full)
    (target / "full-result.json").chmod(0o600)
    (target / "full-result.json").write_bytes(changed)
    manifest = json.loads((target / "manifest.json").read_bytes())
    manifest["artifacts"]["full-result"].update(
        sha256=hashlib.sha256(changed).hexdigest(), bytes=len(changed)
    )
    (target / "manifest.json").chmod(0o600)
    (target / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(StoreError) as counts:
        read_artifacts(
            tmp_path,
            {"output_root": output_root, "binding": binding, "scope": {"input_path": "input.json"}},
        )
    assert counts.value.code == "pack_output_count_or_schema_invalid"
    with pytest.raises(ValueError, match="output_exists"):
        run(input_path, target, binding, calculator=execute_pack_bundle)


def test_native_writer_rejects_input_hash_change_before_calculation(tmp_path):
    from app.research_web.capabilities.pack_native import run

    path = tmp_path / "input.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="input_hash_mismatch"):
        run(path, tmp_path / "result", {"input_sha256": "0" * 64})


@pytest.mark.skipif(sys.platform != "darwin", reason="Native Seatbelt is macOS only")
def test_frozen_resource_runs_in_real_native_sandbox_without_host_imports(tmp_path):
    from app.research_web.capabilities.catalog import CapabilityCatalog
    from app.research_web.sandbox import SandboxConfig, run_script

    root = tmp_path / "research"
    root.mkdir()
    session = root / "sessions" / str(uuid4())
    for name in ("inputs", "resources", "outputs", "tmp"):
        (session / name).mkdir(parents=True)
    catalog = CapabilityCatalog(root)
    selected = catalog.selection("research-pack-research-prep")
    catalog.snapshot(selected, session)
    source = {
        "schema": "research_pack_input_v1",
        "pack_id": "research-prep",
        "records_by_kind": {},
        "parameters": {"as_of": "2026-10-26T23:59:59+08:00"},
        "source_coverage": {},
    }
    input_path = session / "inputs" / "scenarios" / ("a" * 32) / "input.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(json.dumps(source))
    binding = {
        "execution_id": "e" * 32,
        "pack_id": "research-prep",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    }
    scripts = session / selected["resource_path"] / "scripts"
    output_root = "outputs/scenario-results/" + binding["execution_id"]
    target = session / output_root / "v1"
    target.parent.mkdir(parents=True)
    version = catalog.row(selected["id"])["versions"]["1"]
    paths = [
        selected["resource_path"] + "/" + name
        for name in ["SKILL.md", *[item["path"] for item in version["files"]]]
    ]
    paths.append(input_path.relative_to(session).as_posix())
    bindings = []
    for relative in paths:
        file = session / relative
        info = file.stat()
        bindings.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "bytes": info.st_size,
                "device": info.st_dev,
                "inode": info.st_ino,
            }
        )
    code = f"import sys,json\nfrom pathlib import Path\nsys.path.insert(0,{str(scripts)!r})\nfrom calculate import execute\nprint(json.dumps(execute(Path({str(input_path)!r}),Path({str(target)!r}),{binding!r})))\n"
    result = run_script(
        SandboxConfig(root, Path(sys.executable), timeout_seconds=15),
        session,
        code,
        read_paths=paths,
        input_policy="scenario-frozen-inputs-v1",
        file_bindings=bindings,
        output_root=output_root,
    )
    assert result.status == "completed", (result.status, result.stderr, result.error)
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "insufficient_data"
    assert (target / "full-result.json").is_file()
