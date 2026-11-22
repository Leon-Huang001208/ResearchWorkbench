"""Required audit metadata must survive even when an attacker correctly rehashes."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.research_web.capabilities.pack_native import run
from app.research_web.capabilities.pack_resources import canonical
from app.research_web.scenario_pack_execution import read_artifacts
from app.research_web.scenarios.packs import execute_pack_bundle
from app.research_web.store import StoreError


@pytest.fixture
def result(tmp_path):
    vectors = json.loads(
        (
            Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
        ).read_bytes()
    )
    vector = copy.deepcopy(
        next(row for row in vectors if row["id"] == "deduplicate_source_versions.success")
    )
    value = {
        "schema": "research_pack_input_v1",
        "pack_id": "research-prep",
        "records_by_kind": vector["records_by_kind"],
        "parameters": {"as_of": vector["parameters"]["as_of"], "deduplicate_source_versions": {}},
        "source_coverage": {},
    }
    input = tmp_path / "input.json"
    input.write_bytes(canonical(value))
    binding = {
        "execution_id": "f" * 32,
        "pack_id": "research-prep",
        "input_sha256": hashlib.sha256(input.read_bytes()).hexdigest(),
    }
    from test_pack_source_versions import current_resources

    scope = current_resources(tmp_path, binding)
    output = "outputs/scenario-results/" + binding["execution_id"]
    target = tmp_path / output / "v1"
    target.parent.mkdir(parents=True)
    run(input, target, binding, calculator=execute_pack_bundle)
    return (
        tmp_path,
        target,
        {"output_root": output, "binding": binding, "scope": scope},
    )


def rewrite(target, receipt, full):
    receipt.pop("result_sha256", None)
    receipt["result_sha256"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    full["root"]["receipt_sha256"] = receipt["result_sha256"]
    manifest = json.loads((target / "manifest.json").read_bytes())
    for name, value in (("receipt", receipt), ("full-result", full)):
        raw = canonical(value)
        p = target / (name + ".json")
        p.chmod(0o600)
        p.write_bytes(raw)
        manifest["artifacts"][name].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    p = target / "manifest.json"
    p.chmod(0o600)
    p.write_bytes(canonical(manifest))


@pytest.mark.parametrize("where", ["root", "component"])
@pytest.mark.parametrize(
    "field",
    [
        "limitations",
        "source_refs",
        "missing",
        "rejected_rows",
        "host_qualification",
        "research_quality",
        "method_version",
        "parameter_delivery",
        "method_source_binding",
        "metrics",
    ],
)
def test_paired_metadata_deletion_is_rejected_after_correct_rehash(result, where, field):
    root, target, execution = result
    receipt = json.loads((target / "receipt.json").read_bytes())
    full = json.loads((target / "full-result.json").read_bytes())
    a, b = (
        (receipt, full["root"])
        if where == "root"
        else (receipt["rows"][0]["result"], full["components"][0])
    )
    a.pop(field)
    b.pop(field)
    rewrite(target, receipt, full)
    with pytest.raises(StoreError) as error:
        read_artifacts(root, execution)
    assert error.value.code == "pack_output_schema_invalid"


@pytest.mark.parametrize("mutation", ["extra", "type", "digest", "code_version"])
def test_metadata_type_extra_digest_and_code_conditions_are_independent(result, mutation):
    root, target, execution = result
    receipt = json.loads((target / "receipt.json").read_bytes())
    full = json.loads((target / "full-result.json").read_bytes())
    if mutation == "extra":
        receipt["approved"] = True
        full["root"]["approved"] = True
    elif mutation == "type":
        receipt["limitations"] = False
        full["root"]["limitations"] = False
    elif mutation == "digest":
        receipt["input_sha256"] = "not-a-digest"
        full["root"]["legacy_normalized_input_sha256"] = "not-a-digest"
    else:
        full["components"][0]["code_version"].pop("source_binding")
    rewrite(target, receipt, full)
    with pytest.raises(StoreError) as error:
        read_artifacts(root, execution)
    assert error.value.code == "pack_output_schema_invalid"


def test_independent_atom_contracts_accept_all_legitimate_frozen_vectors():
    from jsonschema import Draft202012Validator

    from app.research_web.capabilities.pack_result_contracts import payload
    from app.research_web.scenarios.packs import PackError, execute_atom_bundle

    rows = json.loads(
        (
            Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
        ).read_bytes()
    )
    accepted = 0
    for row in rows:
        try:
            bundle = execute_atom_bundle(row["atom"], row["records_by_kind"], row["parameters"])
        except PackError:
            assert (
                row["atom"] == "join_risk_windows"
            )  # legacy coverage strings deliberately invalid
            continue
        assert not list(
            Draft202012Validator(payload(row["atom"])).iter_errors(bundle.receipt)
        ), row["id"]
        assert not list(
            Draft202012Validator(payload(row["atom"], full=True)).iter_errors(
                json.loads(bundle.full_result.canonical_json)["root"]
            )
        ), row["id"]
        accepted += 1
    assert accepted == 20


@pytest.mark.parametrize("where", ["root", "component"])
@pytest.mark.parametrize(
    "field",
    [
        "counts",
        "code_version",
        "input_digest_kind",
        "canonical_input_sha256",
        "legacy_normalized_input_sha256",
        "receipt_sha256",
        "source_locator_contract",
    ],
)
def test_full_only_required_audit_fields_cannot_disappear(result, where, field):
    root, target, execution = result
    receipt = json.loads((target / "receipt.json").read_bytes())
    full = json.loads((target / "full-result.json").read_bytes())
    value = full["root"] if where == "root" else full["components"][0]
    value.pop(field)
    # rewrite intentionally restores root receipt_sha; remove it after the normal
    # rehash path for that one test while keeping actual file/manifest hashes true.
    rewrite(target, receipt, full)
    if where == "root" and field == "receipt_sha256":
        changed = json.loads((target / "full-result.json").read_bytes())
        changed["root"].pop(field)
        raw = canonical(changed)
        (target / "full-result.json").write_bytes(raw)
        manifest = json.loads((target / "manifest.json").read_bytes())
        manifest["artifacts"]["full-result"].update(
            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)
        )
        (target / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(StoreError) as error:
        read_artifacts(root, execution)
    assert error.value.code == "pack_output_schema_invalid"
