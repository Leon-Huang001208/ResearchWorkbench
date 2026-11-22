"""Unknown authorship is explicit, versioned, and never invented from capture."""

import copy
import json
from pathlib import Path

import pytest

from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.pack_result_contracts import contracts, validate
from app.research_web.scenarios.packs import execute_atom_bundle, execute_pack_bundle


def source_vector():
    values = json.loads(
        (
            Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
        ).read_bytes()
    )
    return copy.deepcopy(
        next(v for v in values if v["id"] == "deduplicate_source_versions.success")
    )


def test_unknown_role_is_retained_with_gap_and_no_reprint_inference():
    vector = source_vector()
    for row in vector["records_by_kind"]["source-version"]:
        row.update(
            source_role="unknown", language="unknown", region="unknown", parent_version_id=None
        )
        row["origin"]["published_at"] = None
    bundle = execute_atom_bundle(
        "deduplicate_source_versions", vector["records_by_kind"], vector["parameters"]
    )
    assert bundle.receipt["method_version"] == "1.1.0"
    assert bundle.receipt["metrics"]["reprint_lags"] == []
    assert sum(v["code"] == "source_role_unknown" for v in bundle.receipt["missing"]) == len(
        vector["records_by_kind"]["source-version"]
    )
    full = json.loads(bundle.full_result.canonical_json)
    assert all(
        v["source_role"] == "unknown" for row in full["root"]["rows"] for v in row["versions"]
    )


def test_two_pack_versions_and_original_roles_remain_explicit():
    vector = source_vector()
    for pack in ("research-prep", "global-opinion"):
        bundle = execute_pack_bundle(
            pack,
            vector["records_by_kind"],
            {"as_of": vector["parameters"]["as_of"], "deduplicate_source_versions": {}},
        )
        assert bundle.receipt["method_version"] == "1.1.0"
        validate(bundle.receipt, json.loads(bundle.full_result.canonical_json), pack)
    assert contracts()["version"] == 2
    with pytest.raises(CapabilityError):
        validate(
            bundle.receipt,
            json.loads(bundle.full_result.canonical_json),
            pack,
            definitions=contracts(version=1),
        )


def materialize_package(root, package, execution):
    from app.research_web.capabilities.packages import decode_file

    binding = execution["binding"]
    prefix = f"resources/capabilities/{binding['capability_id']}/{binding['version']}/"
    for file in package["files"]:
        path = root / (prefix + file["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(decode_file(file))


def old_artifacts(root):
    import shutil

    fixture = Path(__file__).parent / "fixtures/pack-633-v1"
    execution = json.loads((fixture / "execution.json").read_bytes())
    package = json.loads((fixture / "package.json").read_bytes())
    shutil.copytree(fixture / "outputs", root / "outputs")
    shutil.copyfile(fixture / "input.json", root / "input.json")
    materialize_package(root, package, execution)
    return execution, package


def test_actual_633_v1_frozen_artifacts_read_unchanged_with_v1_contract(tmp_path):
    import hashlib

    from app.research_web.capabilities.pack_resources import verify_pack_manifest
    from app.research_web.scenario_pack_execution import read_artifacts

    execution, package = old_artifacts(tmp_path)
    assert verify_pack_manifest(package["files"])["method_version"] == "1.0.0"
    old_input = tmp_path / "input.json"
    before = hashlib.sha256(old_input.read_bytes()).hexdigest()
    result = read_artifacts(tmp_path, execution)
    assert result["counts"]["components"] == {"deduplicate_source_versions": 2}
    assert result["computation_status"] == "partial"
    assert before == hashlib.sha256(old_input.read_bytes()).hexdigest()
    receipt = json.loads((tmp_path / execution["output_root"] / "v1/receipt.json").read_bytes())
    full = json.loads((tmp_path / execution["output_root"] / "v1/full-result.json").read_bytes())
    validate(receipt, full, "research-prep", definitions=contracts(version=1))
    with pytest.raises(CapabilityError):
        validate(receipt, full, "research-prep")


@pytest.mark.parametrize("mutation", ["contract", "manifest", "input_schema", "method_version"])
def test_old_v1_cannot_select_new_or_changed_frozen_schema(tmp_path, mutation):
    from app.research_web.capabilities.pack_resources import MANIFEST_PATH, canonical
    from app.research_web.scenario_pack_execution import read_artifacts
    from app.research_web.store import StoreError

    execution, _ = old_artifacts(tmp_path)
    prefix = tmp_path / "resources/capabilities/research-pack-research-prep/1"
    manifest_path = prefix / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_bytes())
    if mutation == "contract":
        (prefix / "references/output-contracts-v1.json").write_bytes(canonical(contracts()))
    elif mutation == "manifest":
        manifest["schema"] = "research_pack_code_manifest_v2"
        manifest_path.write_bytes(canonical(manifest))
    elif mutation == "method_version":
        manifest["method_version"] = "1.1.0"
        manifest_path.write_bytes(canonical(manifest))
    else:
        import hashlib

        # Correctly rehash all related *input* declarations; fixed legacy schema
        # still refuses an unknown role, independently of output hashes.
        input = json.loads((tmp_path / "input.json").read_bytes())
        input["records_by_kind"]["source-version"][0]["source_role"] = "unknown"
        raw = canonical(input)
        (tmp_path / "input.json").write_bytes(raw)
        execution["binding"]["input_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(StoreError) as error:
        read_artifacts(tmp_path, execution)
    assert error.value.code == "pack_output_schema_invalid"


def test_new_v2_unknown_source_pack_roundtrip_uses_frozen_v2(tmp_path):
    import hashlib

    from app.research_web.capabilities.pack_native import run
    from app.research_web.capabilities.pack_resources import MANIFEST_PATH, canonical, pack_packages
    from app.research_web.capabilities.packages import decode_file
    from app.research_web.scenario_pack_execution import read_artifacts

    package = dict(pack_packages())["research-pack-research-prep"]
    manifest = json.loads(
        decode_file(next(f for f in package["files"] if f["path"] == MANIFEST_PATH))
    )
    vector = source_vector()
    for row in vector["records_by_kind"]["source-version"]:
        row.update(
            source_role="unknown", language="unknown", region="unknown", parent_version_id=None
        )
        row["origin"]["published_at"] = None
    value = {
        "schema": "research_pack_input_v1",
        "pack_id": "research-prep",
        "records_by_kind": vector["records_by_kind"],
        "parameters": {"as_of": vector["parameters"]["as_of"], "deduplicate_source_versions": {}},
        "source_coverage": {},
    }
    raw = canonical(value)
    (tmp_path / "input.json").write_bytes(raw)
    binding = {
        "execution_id": "e" * 32,
        "pack_id": "research-prep",
        "capability_id": "research-pack-research-prep",
        "version": 1,
        "closure_sha256": manifest["closure_sha256"],
        "input_sha256": hashlib.sha256(raw).hexdigest(),
    }
    prefix = "resources/capabilities/research-pack-research-prep/1/"
    execution = {
        "binding": binding,
        "scope": {
            "input_path": "input.json",
            "file_bindings": [
                {"path": prefix + f["path"], "sha256": f["sha256"]} for f in package["files"]
            ],
        },
        "output_root": "outputs/scenario-results/" + binding["execution_id"],
    }
    materialize_package(tmp_path, package, execution)
    target = tmp_path / execution["output_root"] / "v1"
    target.parent.mkdir(parents=True)
    run(tmp_path / "input.json", target, binding, calculator=execute_pack_bundle)
    result = read_artifacts(tmp_path, execution)
    assert result["counts"]["components"] == {"deduplicate_source_versions": 2}
    assert any(gap["code"] == "source_role_unknown" for gap in result["missing"])


def current_resources(root, binding):
    """Real frozen contract scope for lower-level writer/validator tests."""
    from app.research_web.capabilities.pack_resources import MANIFEST_PATH, pack_packages
    from app.research_web.capabilities.packages import decode_file

    cid = "research-pack-" + binding["pack_id"]
    package = dict(pack_packages())[cid]
    manifest = json.loads(
        decode_file(next(f for f in package["files"] if f["path"] == MANIFEST_PATH))
    )
    binding.update(capability_id=cid, version=1, closure_sha256=manifest["closure_sha256"])
    execution = {"binding": binding}
    materialize_package(root, package, execution)
    prefix = f"resources/capabilities/{cid}/1/"
    return {
        "input_path": "input.json",
        "file_bindings": [
            {"path": prefix + f["path"], "sha256": f["sha256"]} for f in package["files"]
        ],
    }
