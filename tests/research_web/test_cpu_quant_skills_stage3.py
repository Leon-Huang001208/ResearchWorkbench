"""Deterministic contracts and safety gates for CPU quant Skills stage 3."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import psutil
import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from app.research_web.capabilities.catalog import (
    COMPARISON_EXECUTOR_IDENTITY,
    CapabilityCatalog,
)
from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.seeds import RECEIPT_GATED_SKILLS, seed_packages
from app.research_web.sandbox import child_environment
from app.research_web.skills._shared import cpu_budget as cpu_budget_module
from app.research_web.skills._shared import input_contract as input_contract_module

PROJECT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT / "app/research_web/skills"
SLUGS = (
    "fund-matcher",
    "fund-penetration",
    "portfolio-overlap",
    "portfolio-benchmark-deviation",
    "industry-prosperity",
    "industry-quadrant-monitor",
    "industry-crowding-monitor",
)
OLD_STAGE3_SCRIPT_DIGESTS = {
    "fund-matcher": "e0d0b61aeae71ffd409f0cdddd42d459c874b06dfcb489524b1e49e2692b978f",
    "fund-penetration": "ae4349dfbc3755b599eec265d70bce4e5470791c312c211f6f747900df11dc54",
    "portfolio-overlap": "454419b2b58a720c364d3bf3883be3840adb35fdd38152f1204b0fe3e2c1df5f",
    "portfolio-benchmark-deviation": "c216c3ea377ae6fa5ace72260ce60b909fdefa7fe813200f7988112801f2b80a",
    "industry-prosperity": "31df916c150ea791f7581a817e1efc19f33f6581b4ca8967feff0a5ed1225da2",
    "industry-quadrant-monitor": "c3efd22876b06bacc39ba56cba411de1075fe5b0b884c15855be59a5d9175513",
    "industry-crowding-monitor": "418a7eb9003c3242202d772d5493ce6a7b36813db5c882f7c522953bdfaf33db",
}
REQUIRED_PACKAGE_FILES = {
    "SKILL.md",
    "scripts/calculate.py",
    "references/input-schema.json",
    "references/output-schema.json",
    "references/field-mapping.json",
    "references/provenance.json",
    "fixtures/input.json",
    "fixtures/golden-result.json",
    "fixtures/source-artifact.json",
}
DATE_FIELDS = {
    "fund-matcher": ("records", "as_of"),
    "fund-penetration": ("records", "as_of"),
    "portfolio-overlap": ("records", "as_of"),
    "portfolio-benchmark-deviation": ("records", "as_of"),
    "industry-prosperity": ("records", "period_end"),
    "industry-quadrant-monitor": ("records", "observation_date"),
    "industry-crowding-monitor": ("records", "date"),
}
NUMERIC_FIELDS = {
    "fund-matcher": "annual_return_pct",
    "fund-penetration": "weight",
    "portfolio-overlap": "weight",
    "portfolio-benchmark-deviation": "market_cap",
    "industry-prosperity": "current_value",
    "industry-quadrant-monitor": "current_score",
    "industry-crowding-monitor": "industry_turnover",
}


def load_json(slug: str, name: str) -> dict:
    return json.loads((SKILLS_ROOT / slug / "fixtures" / name).read_text(encoding="utf-8"))


def load_calculator(slug: str):
    path = SKILLS_ROOT / slug / "scripts/calculate.py"
    spec = importlib.util.spec_from_file_location(f"stage3_{slug.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous_budget = sys.modules.get("cpu_budget")
    previous_contract = sys.modules.get("input_contract")
    sys.modules["cpu_budget"] = cpu_budget_module
    sys.modules["input_contract"] = input_contract_module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_budget is None:
            sys.modules.pop("cpu_budget", None)
        else:
            sys.modules["cpu_budget"] = previous_budget
        if previous_contract is None:
            sys.modules.pop("input_contract", None)
        else:
            sys.modules["input_contract"] = previous_contract
    return module


def test_fund_matcher_orders_candidates_by_deterministic_weighted_distance():
    module = load_calculator("fund-matcher")
    payload = load_json("fund-matcher", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("fund-matcher", "golden-result.json")
    assert [row["fund_code"] for row in actual["rows"]] == ["FUND-A", "FUND-B"]
    assert actual["research_only"] is True


def test_fund_penetration_normalizes_units_and_aggregates_repeated_lookthrough():
    module = load_calculator("fund-penetration")
    payload = load_json("fund-penetration", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("fund-penetration", "golden-result.json")
    assert actual["metrics"]["duplicate_leaf_paths_aggregated"] == 1
    assert actual["rows"][0]["asset_id"] == "STOCK-X"


def test_fund_penetration_rejects_cycles():
    module = load_calculator("fund-penetration")
    payload = load_json("fund-penetration", "input.json")
    payload["records"][-1]["weight"] = 50
    payload["records"].append(
        {
            "owner_id": "FUND-B",
            "holding_id": "FUND-A",
            "holding_type": "fund",
            "weight": 10,
            "weight_unit": "percent",
            "as_of": payload["as_of"],
        }
    )

    try:
        module.calculate(payload, input_bytes=1)
    except module.CalculatorError as exc:
        assert exc.code == "cycle_detected"
    else:
        raise AssertionError("cycle must fail closed")


def test_fund_penetration_rejects_disconnected_cycles():
    module = load_calculator("fund-penetration")
    payload = load_json("fund-penetration", "input.json")
    payload["records"].extend(
        [
            {
                "owner_id": "FUND-X",
                "holding_id": "FUND-Y",
                "holding_type": "fund",
                "weight": 0.5,
                "weight_unit": "decimal",
                "as_of": "2026-09-15",
            },
            {
                "owner_id": "FUND-Y",
                "holding_id": "FUND-X",
                "holding_type": "fund",
                "weight": 0.5,
                "weight_unit": "decimal",
                "as_of": "2026-09-15",
            },
        ]
    )

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "cycle_detected"


def test_fund_penetration_rejects_mixed_snapshot_dates():
    module = load_calculator("fund-penetration")
    payload = load_json("fund-penetration", "input.json")
    payload["records"][0]["weight"] = 25
    payload["records"][0]["as_of"] = "2026-09-14"
    payload["records"].insert(
        1,
        {
            "owner_id": "FUND-A",
            "holding_id": "FUND-B",
            "holding_type": "fund",
            "weight": 25,
            "weight_unit": "percent",
            "as_of": "2026-09-15",
        },
    )
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"


def test_portfolio_overlap_aggregates_duplicates_and_normalizes_each_book():
    module = load_calculator("portfolio-overlap")
    payload = load_json("portfolio-overlap", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("portfolio-overlap", "golden-result.json")
    assert actual["metrics"]["overlap_ratio"] == 0.5
    assert actual["metrics"]["duplicate_rows_aggregated"] == 1


def test_portfolio_benchmark_deviation_matches_weight_and_zscore_definition():
    module = load_calculator("portfolio-benchmark-deviation")
    payload = load_json("portfolio-benchmark-deviation", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("portfolio-benchmark-deviation", "golden-result.json")
    assert actual["rows"][0]["industry"] == "Tech"
    assert actual["metrics"]["overall"]["market_cap_zscore"] > 0


def test_industry_prosperity_uses_only_preaggregated_directional_indicators():
    module = load_calculator("industry-prosperity")
    payload = load_json("industry-prosperity", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("industry-prosperity", "golden-result.json")
    assert actual["rows"][0]["industry"] == "Tech"
    assert actual["rows"][0]["research_signal"] == "improving"


def test_industry_quadrant_classifies_level_and_momentum_without_inference():
    module = load_calculator("industry-quadrant-monitor")
    payload = load_json("industry-quadrant-monitor", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("industry-quadrant-monitor", "golden-result.json")
    assert actual["metrics"]["quadrant_counts"] == {
        "high_and_improving": 1,
        "high_but_weakening": 1,
        "low_but_improving": 1,
        "low_and_weakening": 1,
    }


def test_industry_crowding_uses_rolling_preaggregated_turnover_share_and_percentile():
    module = load_calculator("industry-crowding-monitor")
    payload = load_json("industry-crowding-monitor", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert actual == load_json("industry-crowding-monitor", "golden-result.json")
    assert actual["rows"][0]["industry"] == "Tech"
    assert actual["rows"][0]["research_signal"] == "high_crowding"


def test_seven_stage3_packages_are_discoverable_disabled_and_receipt_gated(tmp_path):
    seeded = dict(seed_packages())
    assert set(SLUGS) <= set(seeded)
    assert set(SLUGS) <= RECEIPT_GATED_SKILLS

    catalog = CapabilityCatalog(tmp_path)
    rows = {row["id"]: row for row in catalog.list(kind="skill")["items"]}
    assert len(rows) == 25
    for slug in SLUGS:
        assert rows[slug]["source"] == "builtin"
        assert rows[slug]["status"] == "disabled"
        assert rows[slug]["enabled"] is False
        assert "research_run_script" in rows[slug]["metadata"]["required_tools"]
        detail = catalog.row(slug)
        native_name = detail["versions"][str(detail["version"])]["native_name"]
        assert not (catalog.native_root / native_name).exists()
        with pytest.raises(CapabilityError) as error:
            catalog.selection(slug)
        assert error.value.code == "capability_disabled"
        with pytest.raises(CapabilityError) as error:
            catalog.transition(slug, "enable")
        assert error.value.code == "comparison_receipt_required"


def _version_script_digest(catalog: CapabilityCatalog, slug: str, version: int) -> str:
    files = catalog.row(slug)["versions"][str(version)]["files"]
    return next(item["sha256"] for item in files if item["path"] == "scripts/calculate.py")


def _write_comparison_evidence(tmp_path: Path, catalog: CapabilityCatalog, slug: str):
    version = catalog.row(slug)["version"]
    evidence_dir = tmp_path / "comparison-evidence" / slug
    evidence_dir.mkdir(parents=True)
    actual = evidence_dir / "actual-result.json"
    expected = evidence_dir / "golden-result.json"
    shutil.copy2(SKILLS_ROOT / slug / "fixtures/golden-result.json", expected)
    source_artifact = SKILLS_ROOT / slug / "fixtures/source-artifact.json"
    if not source_artifact.exists():
        source_artifact = SKILLS_ROOT / slug / "fixtures/input.json"
    synthetic_input = evidence_dir / "synthetic-input.json"
    actual_input = evidence_dir / "wind-excel-actual-input.json"
    shutil.copy2(source_artifact, synthetic_input)
    actual_input.write_text(
        json.dumps(json.loads(source_artifact.read_text(encoding="utf-8")), indent=2),
        encoding="utf-8",
    )
    actual.write_text(
        json.dumps(json.loads(expected.read_text(encoding="utf-8")), indent=2),
        encoding="utf-8",
    )
    output = json.loads(actual.read_text(encoding="utf-8"))
    evidence = {
        "schema_version": 2,
        "skill_slug": slug,
        "version": version,
        "script_sha256": _version_script_digest(catalog, slug, version),
        "compared_at": "2026-09-15T00:00:00Z",
        "platform": "macos",
        "comparison": "wind_excel",
        "result": "passed",
        "input_source_hashes": output["provenance"]["source_hashes"],
        "synthetic_input": {
            "path": synthetic_input.name,
            "sha256": hashlib.sha256(synthetic_input.read_bytes()).hexdigest(),
        },
        "actual_input": {
            "path": actual_input.name,
            "sha256": hashlib.sha256(actual_input.read_bytes()).hexdigest(),
        },
        "executor": {
            "identity": COMPARISON_EXECUTOR_IDENTITY,
            "executable_sha256": "c3" * 32,
        },
        "golden_result": {
            "path": expected.name,
            "sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
        },
        "actual_result": {
            "path": actual.name,
            "sha256": hashlib.sha256(actual.read_bytes()).hexdigest(),
        },
        "registrar_signature": "0" * 64,
    }
    artifact = evidence_dir / "comparison.json"
    artifact.write_text(json.dumps(evidence), encoding="utf-8")
    return artifact, actual


def test_stage3_plain_json_cannot_self_attest_a_comparison_receipt(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    for slug in SLUGS:
        artifact, _actual = _write_comparison_evidence(tmp_path, catalog, slug)
        with pytest.raises(CapabilityError) as error:
            catalog.record_comparison_receipt(artifact)
        assert error.value.code == "comparison_registrar_required"
        assert catalog.comparison_receipt(slug) is None


def test_stage3_forged_registrar_signature_cannot_enable(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_COMPARISON_REGISTRAR_KEY", "d4" * 32)
    catalog = CapabilityCatalog(tmp_path)
    artifact, _actual = _write_comparison_evidence(tmp_path, catalog, "fund-matcher")

    with pytest.raises(CapabilityError) as error:
        catalog.record_comparison_receipt(artifact)

    assert error.value.code == "invalid_comparison_evidence"
    assert catalog.comparison_receipt("fund-matcher") is None


def test_comparison_registrar_key_is_never_in_sandbox_child_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_COMPARISON_REGISTRAR_KEY", "d4" * 32)

    environment = child_environment(tmp_path)

    assert "RESEARCH_COMPARISON_REGISTRAR_KEY" not in environment


@pytest.mark.parametrize("slug", SLUGS)
def test_known_initial_stage3_builtin_is_migrated_without_reusing_receipt_or_projection(
    slug, tmp_path
):
    catalog = CapabilityCatalog(tmp_path)
    row = catalog.row(slug)
    old_version = row["version"]
    calculate = next(
        item
        for item in row["versions"][str(old_version)]["files"]
        if item["path"] == "scripts/calculate.py"
    )
    calculate["sha256"] = OLD_STAGE3_SCRIPT_DIGESTS[slug]
    row["status"] = "enabled"
    native_name = row["versions"][str(old_version)]["native_name"]
    native = catalog.native_root / native_name
    native.mkdir()
    (native / "SKILL.md").write_text("unsafe initial projection", encoding="utf-8")
    catalog.data["comparison_receipts"][f"{slug}:{old_version}"] = {
        "schema_version": 2,
        "skill_slug": slug,
        "version": old_version,
    }
    catalog.save()

    upgraded = CapabilityCatalog(tmp_path)
    migrated = upgraded.row(slug)

    assert migrated["version"] == old_version + 1
    assert migrated["status"] == "disabled"
    assert upgraded.comparison_receipt(slug) is None
    assert not native.exists()
    migrated_native_name = migrated["versions"][str(migrated["version"])]["native_name"]
    assert not (upgraded.native_root / migrated_native_name).exists()


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_packages_have_strict_valid_schemas_goldens_and_internal_provenance(slug):
    folder = SKILLS_ROOT / slug
    assert REQUIRED_PACKAGE_FILES <= {
        path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()
    }
    input_schema = json.loads((folder / "references/input-schema.json").read_text(encoding="utf-8"))
    output_schema = json.loads(
        (folder / "references/output-schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(input_schema)
    Draft202012Validator.check_schema(output_schema)
    input_validator = Draft202012Validator(input_schema, format_checker=FormatChecker())
    output_validator = Draft202012Validator(output_schema, format_checker=FormatChecker())
    assert list(input_validator.iter_errors(load_json(slug, "input.json"))) == []
    assert list(output_validator.iter_errors(load_json(slug, "golden-result.json"))) == []
    assert input_schema["additionalProperties"] is False
    assert input_schema["properties"]["parameters"]["additionalProperties"] is False
    assert input_schema["properties"]["records"]["items"]["additionalProperties"] is False
    dataset_refs = input_schema["properties"]["dataset_refs"]
    if "$ref" in dataset_refs:
        dataset_refs = input_schema["$defs"][dataset_refs["$ref"].rsplit("/", 1)[-1]]
    dataset_item = dataset_refs["items"]
    if "$ref" in dataset_item:
        dataset_item = input_schema["$defs"][dataset_item["$ref"].rsplit("/", 1)[-1]]
    assert dataset_item["additionalProperties"] is False
    provenance = json.loads((folder / "references/provenance.json").read_text(encoding="utf-8"))
    assert provenance["rights"] == "internal-only"
    assert provenance["method_version"] == "1.0.0"
    assert provenance.get("source_workbook_included") is not True
    instructions = (folder / "SKILL.md").read_text(encoding="utf-8")
    header = yaml.safe_load(instructions.split("---", 2)[1])
    assert header["name"] == slug
    for phrase in ("样本", "截止", "条件", "反例", "失效条件", "research signal", "交易建议"):
        assert phrase in instructions


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_schema_fields_and_runtime_contract_constants_are_equivalent(slug):
    module = load_calculator(slug)
    schema = json.loads(
        (SKILLS_ROOT / slug / "references/input-schema.json").read_text(encoding="utf-8")
    )
    output_schema = json.loads(
        (SKILLS_ROOT / slug / "references/output-schema.json").read_text(encoding="utf-8")
    )
    assert set(schema["required"]) == set(module.ROOT_FIELDS)
    assert set(schema["properties"]) == set(module.ALLOWED_ROOT_FIELDS)
    assert set(schema["properties"]["parameters"]["required"]) == set(module.PARAMETER_FIELDS)
    assert set(schema["properties"]["parameters"]["properties"]) == set(module.PARAMETER_FIELDS)
    record_schema = schema["properties"]["records"]["items"]
    assert set(record_schema["required"]) == set(module.RECORD_FIELDS)
    assert set(record_schema["properties"]) == set(module.RECORD_FIELDS)
    contract_schema = schema["properties"]["data_contract"]
    if "$ref" in contract_schema:
        contract_schema = schema["$defs"][contract_schema["$ref"].rsplit("/", 1)[-1]]
    assert set(contract_schema["properties"]["provider"]["enum"]) == set(module.SUPPORTED_PROVIDERS)
    assert contract_schema["properties"]["mapping_id"] == {"const": module.SKILL_SLUG}
    assert contract_schema["properties"]["mapping_version"] == {"const": module.METHOD_VERSION}
    assert contract_schema["properties"]["units"]["properties"] == {
        key: {"const": value} for key, value in module.CONTRACT_UNITS.items()
    }
    actual = module.calculate(load_json(slug, "input.json"), input_bytes=1024)
    assert set(actual) == set(output_schema["properties"])


def test_only_verified_workbook_sources_record_full_sha256():
    expected = {
        "portfolio-benchmark-deviation": "415d61e46b2c390de928c0f33011792d94f70efb508e59176d7aa77168c6c504",
        "industry-crowding-monitor": "24010fb2dd76604442d89b7ea4c3c691e3cdc198c87bd191ed1aaf020a0bb831",
    }
    for slug, digest in expected.items():
        provenance = json.loads(
            (SKILLS_ROOT / slug / "references/provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["source_artifacts"]["reference_workbook_sha256"] == digest
        assert provenance["macros_or_formulas_executed"] is False
    for slug in set(SLUGS) - set(expected):
        provenance = json.loads(
            (SKILLS_ROOT / slug / "references/provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["source_artifacts_available"] is False
        assert "source_artifacts" not in provenance


@pytest.mark.parametrize("slug", SLUGS)
@pytest.mark.parametrize("layer", ("root", "parameters", "record", "dataset_ref"))
def test_stage3_runtime_rejects_unknown_fields_at_every_input_layer(slug, layer):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    target = {
        "root": payload,
        "parameters": payload["parameters"],
        "record": payload["records"][0],
        "dataset_ref": payload["dataset_refs"][0],
    }[layer]
    target["unexpected"] = "value"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "unknown_field"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_runtime_rejects_non_iso_dates_contract_mismatch_and_bad_source_hash(slug):
    module = load_calculator(slug)
    base = load_json(slug, "input.json")
    invalid_date = copy.deepcopy(base)
    invalid_date["as_of"] = "2026-9-15"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(invalid_date, input_bytes=1024)
    assert error.value.code == "invalid_date"

    mismatch = copy.deepcopy(base)
    mismatch["data_contract"]["mapping_version"] = "2.0.0"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(mismatch, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"

    bad_hash = copy.deepcopy(base)
    bad_hash["source_hashes"] = {"synthetic": "not-sha256"}
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(bad_hash, input_bytes=1024)
    assert error.value.code == "invalid_source_hashes"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_dataset_ref_provider_must_match_data_contract_provider(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    payload["dataset_refs"][0]["provider_id"] = "user_input"

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_unverified_datahub_mapping_fails_closed(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    payload["data_contract"]["provider"] = "datahub"
    for dataset_ref in payload["dataset_refs"]:
        dataset_ref["provider_id"] = "datahub"

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"
    mapping = json.loads(
        (SKILLS_ROOT / slug / "references/field-mapping.json").read_text(encoding="utf-8")
    )
    assert all(tool["callable"] is False for tool in mapping["business_tools"])


@pytest.mark.parametrize("slug", ("portfolio-overlap", "portfolio-benchmark-deviation"))
def test_portfolio_calculators_reject_mixed_snapshot_dates(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    payload["records"][0]["as_of"] = "2026-09-14"

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", ("portfolio-overlap", "portfolio-benchmark-deviation"))
def test_portfolio_calculators_reject_implicit_leverage(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    payload["records"][0]["weight"] = 1.01
    payload["records"][0]["weight_unit"] = "decimal"

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "invalid_weight"


@pytest.mark.parametrize("slug", ("portfolio-overlap", "portfolio-benchmark-deviation"))
def test_portfolio_calculators_reject_leveraged_book_totals(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    target_book = "PORT-A" if slug == "portfolio-overlap" else "portfolio"
    leveraged_weight = 0.4 if slug == "portfolio-overlap" else 0.6
    for record in payload["records"]:
        identity = record.get("portfolio_id", record.get("book"))
        if identity == target_book:
            record["weight"] = leveraged_weight
            record["weight_unit"] = "decimal"

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "invalid_weight_sum"


def test_benchmark_deviation_requires_explicit_factor_and_mapping_cutoffs():
    module = load_calculator("portfolio-benchmark-deviation")
    payload = copy.deepcopy(load_json("portfolio-benchmark-deviation", "input.json"))
    payload["parameters"].update(
        report_period="2026-06-30",
        factor_date="2026-09-15",
        industry_mapping_version="citics-2026-v1",
    )

    result = module.calculate(payload, input_bytes=1024)

    assert result["parameters"] == {
        "portfolio_id": payload["parameters"]["portfolio_id"],
        "benchmark_id": payload["parameters"]["benchmark_id"],
        "report_period": "2026-06-30",
        "factor_date": "2026-09-15",
        "industry_mapping_version": "citics-2026-v1",
    }


def test_industry_crowding_rejects_noncanonical_calendar_and_market_overallocation():
    module = load_calculator("industry-crowding-monitor")
    payload = copy.deepcopy(load_json("industry-crowding-monitor", "input.json"))
    missing_day = copy.deepcopy(payload)
    missing_day["records"].pop()
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(missing_day, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"

    overallocated = copy.deepcopy(payload)
    for record in overallocated["records"]:
        if record["date"] == overallocated["as_of"]:
            record["industry_turnover"] = record["total_market_turnover"] * 0.6
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(overallocated, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_runtime_enforces_date_and_finite_number_boundaries(slug):
    module = load_calculator(slug)
    base = load_json(slug, "input.json")

    compact_ref = copy.deepcopy(base)
    compact_ref["dataset_refs"][0]["as_of"] = "20260915"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(compact_ref, input_bytes=1024)
    assert error.value.code == "invalid_date"

    record_collection, record_field = DATE_FIELDS[slug]
    compact_record = copy.deepcopy(base)
    compact_record[record_collection][0][record_field] = "20260915"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(compact_record, input_bytes=1024)
    assert error.value.code == "invalid_date"

    future_record = copy.deepcopy(base)
    future_record[record_collection][0][record_field] = "2026-09-16"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(future_record, input_bytes=1024)
    assert error.value.code == "future_data"

    for value in (float("inf"), 10**400):
        invalid_number = copy.deepcopy(base)
        invalid_number["records"][0][NUMERIC_FIELDS[slug]] = value
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid_number, input_bytes=1024)
        assert error.value.code == "invalid_number"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_source_hashes_are_canonical_or_explicitly_partial(slug):
    module = load_calculator(slug)
    missing = load_json(slug, "input.json")
    missing.pop("source_hashes")
    result = module.calculate(missing, input_bytes=1024)
    assert result["status"] == "partial"
    assert result["provenance"]["source_hashes"] == {}
    assert "source_hashes_missing" in result["limitations"]

    digest = "a" * 64
    for invalid_hashes in (
        None,
        {" ": digest},
        {" source ": digest},
        {"source\nname": digest},
        {"source\rname": digest},
        {"source\u2028name": digest},
        {"source\u2029name": digest},
    ):
        invalid = load_json(slug, "input.json")
        invalid["source_hashes"] = invalid_hashes
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code == "invalid_source_hashes"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_cli_is_strict_json_relative_safe_bounded_and_without_success_newline(
    slug, tmp_path
):
    package = tmp_path / slug
    scripts = package / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SKILLS_ROOT / slug / "scripts/calculate.py", scripts / "calculate.py")
    shutil.copy2(SKILLS_ROOT / "_shared/cpu_budget.py", scripts / "cpu_budget.py")
    shutil.copy2(SKILLS_ROOT / "_shared/input_contract.py", scripts / "input_contract.py")
    (package / "input.json").write_text(
        json.dumps(load_json(slug, "input.json"), ensure_ascii=False), encoding="utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "scripts/calculate.py", "input.json"],
        cwd=package,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    assert completed.stderr == b""
    assert not completed.stdout.endswith(b"\n")
    assert len(completed.stdout) <= 64 * 1024
    assert json.loads(completed.stdout)["skill_slug"] == slug

    rejected = subprocess.run(
        [sys.executable, "scripts/calculate.py", str((package / "input.json").resolve())],
        cwd=package,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stderr.decode("utf-8").splitlines()[-1])["error"]["code"] == (
        "unsafe_input_path"
    )


def test_stage3_calculators_do_not_import_forbidden_execution_or_network_stacks():
    forbidden_roots = {
        "asyncio",
        "concurrent",
        "multiprocessing",
        "subprocess",
        "threading",
        "socket",
        "requests",
        "urllib",
        "httpx",
        "torch",
        "tensorflow",
        "jax",
        "cjpy",
    }
    forbidden_tokens = ("cuda", "mps", "metal", "vba", "openpyxl")
    for slug in SLUGS:
        path = SKILLS_ROOT / slug / "scripts/calculate.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports |= {
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert imports.isdisjoint(forbidden_roots), (slug, imports & forbidden_roots)
        lowered = source.lower()
        assert all(re.search(rf"\b{token}\b", lowered) is None for token in forbidden_tokens), slug
        assert "http://" not in lowered and "https://" not in lowered
        assert "load_relative_json" in source
        assert "allow_nan=False" in source


def test_all_seven_regular_calculations_complete_under_two_seconds():
    started = time.monotonic()
    for slug in SLUGS:
        module = load_calculator(slug)
        payload = load_json(slug, "input.json")
        result = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))
        assert result["skill_slug"] == slug
    assert time.monotonic() - started < 2


def _stress_payload(slug: str) -> dict:
    payload = load_json(slug, "input.json")
    as_of = payload["as_of"]
    if slug == "fund-matcher":
        payload["parameters"]["top_n"] = 50
        payload["records"] = [
            {
                "fund_code": f"FUND-{index:03d}",
                "name": f"synthetic-{index:03d}",
                "category": "equity",
                "as_of": as_of,
                "annual_return_pct": 5 + index / 10,
                "max_drawdown_pct": -20 + index / 10,
                "volatility_pct": 10 + index / 20,
                "expense_ratio_pct": 0.5 + index / 100,
                "manager_tenure_years": 1 + index / 10,
            }
            for index in range(50)
        ]
    elif slug == "fund-penetration":
        root_rows = [
            {
                "owner_id": "FUND-A",
                "holding_id": f"FUND-{branch}",
                "holding_type": "fund",
                "weight": 0.25,
                "weight_unit": "decimal",
                "as_of": as_of,
            }
            for branch in range(4)
        ]
        leaf_rows = [
            {
                "owner_id": f"FUND-{branch}",
                "holding_id": f"SEC-{branch}-{index:04d}",
                "holding_type": "security",
                "weight": 0.001,
                "weight_unit": "decimal",
                "as_of": as_of,
            }
            for branch in range(4)
            for index in range(1000)
        ]
        payload["records"] = root_rows + leaf_rows
    elif slug == "portfolio-overlap":
        payload["records"] = [
            {
                "portfolio_id": portfolio_id,
                "asset_id": f"SEC-{index:04d}",
                "weight": 0.001,
                "weight_unit": "decimal",
                "as_of": as_of,
            }
            for portfolio_id in ("PORT-A", "PORT-B")
            for index in range(1000)
        ]
    elif slug == "portfolio-benchmark-deviation":
        payload["records"] = [
            {
                "book": book,
                "book_id": book_id,
                "asset_id": f"SEC-{index:03d}",
                "industry": f"IND-{index % 10:02d}",
                "weight": 2,
                "weight_unit": "percent",
                "as_of": as_of,
                "market_cap": 100 + index + offset,
                "pe_ttm": 10 + index / 10 + offset,
                "profit_growth_yoy_pct": 5 + index / 5 + offset,
            }
            for book, book_id, offset in (
                ("portfolio", "PORT-A", 1),
                ("benchmark", "000906.SH", 0),
            )
            for index in range(50)
        ]
    elif slug == "industry-prosperity":
        payload["parameters"]["minimum_indicators"] = 100
        payload["records"] = [
            {
                "industry": f"IND-{industry:02d}",
                "indicator": f"metric-{index:04d}",
                "period_end": payload["parameters"]["period_end"],
                "current_value": 101 + (industry + index) % 3,
                "prior_value": 100,
                "direction": 1,
                "weight": 1,
            }
            for industry in range(50)
            for index in range(100)
        ]
    elif slug == "industry-quadrant-monitor":
        payload["records"] = [
            {
                "industry": f"IND-{index:02d}",
                "observation_date": as_of,
                "current_score": index - 25,
                "prior_score": index - 26,
            }
            for index in range(50)
        ]
    else:
        last_day = date.fromisoformat(as_of)
        days = [(last_day - timedelta(days=999 - index)).isoformat() for index in range(1000)]
        payload["parameters"].update(rolling_days=250, percentile_days=1000)
        payload["records"] = [
            {
                "industry": f"IND-{industry:02d}",
                "date": day,
                "industry_turnover": 1_000 + (industry + index) % 100,
                "total_market_turnover": 100_000,
            }
            for industry in range(50)
            for index, day in enumerate(days)
        ]
    return payload


def test_fund_penetration_owner_limit_counts_raw_rows_before_duplicate_aggregation():
    module = load_calculator("fund-penetration")
    payload = copy.deepcopy(load_json("fund-penetration", "input.json"))
    payload["records"] = [
        {
            "owner_id": "FUND-A",
            "holding_id": "STOCK-X",
            "holding_type": "security",
            "weight": 0.0005,
            "weight_unit": "decimal",
            "as_of": payload["as_of"],
        }
        for _ in range(1001)
    ]

    with pytest.raises(Exception) as error:
        module.calculate(payload, input_bytes=64 * 1024)
    assert getattr(error.value, "code", None) == "workload_too_large"
    assert error.value.metadata["resource"] == "rows_per_symbol"


def test_industry_prosperity_projects_nested_contributions_globally_to_128():
    module = load_calculator("industry-prosperity")
    payload = _stress_payload("industry-prosperity")

    result = module.calculate(
        payload, input_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    )

    assert sum(len(row["indicator_contributions"]) for row in result["rows"]) == 128
    assert result["row_delivery"]["nested_inline_output_rows"] == 128
    assert result["row_delivery"]["nested_omitted_output_rows"] == 4_872
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    assert len(encoded) <= 64 * 1024


def test_stage3_synthetic_source_artifacts_are_real_and_bound_to_fixtures():
    for slug in SLUGS:
        artifact = SKILLS_ROOT / slug / "fixtures/source-artifact.json"
        assert artifact.is_file()
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        payload = load_json(slug, "input.json")
        golden = load_json(slug, "golden-result.json")
        assert payload["source_hashes"] == {"synthetic": digest}
        assert payload["dataset_refs"][0]["sha256"] == digest
        assert golden["provenance"]["source_hashes"] == {"synthetic": digest}
        assert golden["dataset_refs"][0]["sha256"] == digest
        provenance = json.loads(
            (SKILLS_ROOT / slug / "references/provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["synthetic_source_artifact_sha256"] == digest


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_over_limit_workloads_fail_with_stable_error(slug):
    module = load_calculator(slug)
    payload = _stress_payload(slug)
    if slug == "fund-matcher":
        extra = copy.deepcopy(payload["records"][0])
        extra["fund_code"] = "FUND-OVER-LIMIT"
        payload["records"].append(extra)
    elif slug == "industry-quadrant-monitor":
        extra = copy.deepcopy(payload["records"][0])
        extra["industry"] = "IND-OVER-LIMIT"
        payload["records"].append(extra)
    elif slug == "industry-crowding-monitor":
        payload["records"].append(copy.deepcopy(payload["records"][0]))
    else:
        needed = 5_001 - len(payload["records"])
        repeated = payload["records"] * (needed // len(payload["records"]) + 1)
        payload["records"].extend(copy.deepcopy(repeated[:needed]))

    with pytest.raises(Exception) as error:
        module.calculate(payload, input_bytes=64 * 1024)
    assert getattr(error.value, "code", None) == "workload_too_large"
    assert error.value.metadata["reduce_scope"] is True


@pytest.mark.parametrize("slug", SLUGS)
def test_stage3_near_limit_process_stays_within_sandbox_time_rss_and_output(slug, tmp_path):
    payload = _stress_payload(slug)
    research_root = tmp_path / "research"
    session = research_root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    scripts = session / "resources" / "calculator" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SKILLS_ROOT / slug / "scripts/calculate.py", scripts / "calculate.py")
    for name in ("cpu_budget.py", "input_contract.py"):
        shutil.copy2(SKILLS_ROOT / "_shared" / name, scripts / name)
    input_path = session / "inputs" / "input.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert input_path.stat().st_size < 64 * 1024 * 1024
    code = """
import sys
from pathlib import Path
scripts = Path(__SCRIPTS__)
sys.path.insert(0, str(scripts))
namespace = {'__name__': 'reviewed_skill_resource'}
source = (scripts / 'calculate.py').read_text(encoding='utf-8')
exec(compile(source, 'scripts/calculate.py', 'exec'), namespace)
namespace['main'](['inputs/input.json'])
""".replace("__SCRIPTS__", repr(str(scripts)))
    command = [
        sys.executable,
        str(PROJECT / "app/research_web/sandbox.py"),
        "--research-root",
        str(research_root),
        "--python",
        sys.executable,
        "--session",
        str(session),
        "--timeout",
        "9",
        "--max-output",
        str(64 * 1024),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps({"code": code}))
    process.stdin.close()
    process.stdin = None
    tracked_process = psutil.Process(process.pid)
    peak_rss_bytes = 0
    while process.poll() is None:
        try:
            processes = [tracked_process, *tracked_process.children(recursive=True)]
            peak_rss_bytes = max(
                peak_rss_bytes,
                sum(child.memory_info().rss for child in processes if child.is_running()),
            )
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass
        if time.monotonic() - started >= 10:
            process.kill()
            pytest.fail(f"{slug} exceeded 10 seconds")
        time.sleep(0.01)
    stdout, stderr = process.communicate(timeout=1)
    elapsed = time.monotonic() - started
    assert process.returncode == 0, stderr
    supervisor = json.loads(stdout)
    assert supervisor["status"] == "completed", supervisor
    output_size = len(supervisor["stdout"].encode("utf-8")) + len(
        supervisor["stderr"].encode("utf-8")
    )
    assert output_size <= 64 * 1024
    assert supervisor["stderr"] == "", supervisor
    result = json.loads(supervisor["stdout"])
    assert result["skill_slug"] == slug
    assert result["row_delivery"]["processed_input_rows"] == len(payload["records"])
    assert elapsed < 10
    assert 0 < peak_rss_bytes < 1024**3
