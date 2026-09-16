"""Offline contracts and deterministic goldens for CPU quant Skills stage 2."""

from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import time
from contextlib import chdir, redirect_stderr, redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import psutil
import pytest
import yaml
from jsonschema import Draft202012Validator

from app.research_web.capabilities.catalog import (
    COMPARISON_EXECUTOR_IDENTITY,
    CapabilityCatalog,
)
from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.seeds import seed_packages
from app.research_web.skills._shared import cpu_budget as cpu_budget_module
from app.research_web.skills._shared import input_contract as input_contract_module
from app.research_web.skills._shared.cpu_budget import (
    MAX_INPUT_BYTES,
    WorkloadBudget,
    WorkloadTooLarge,
)

PROJECT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT / "app/research_web/skills"
SLUGS = (
    "daily-market-brief",
    "policy-sentinel",
    "event-review",
    "etf-flow-monitor",
    "earnings-report-monitor",
    "earnings-preview-monitor",
)
REGISTRAR_KEY_HEX = "d4" * 32


def _registrar_signature(evidence: dict) -> str:
    unsigned = {key: value for key, value in evidence.items() if key != "registrar_signature"}
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hmac.new(bytes.fromhex(REGISTRAR_KEY_HEX), canonical, hashlib.sha256).hexdigest()


OLD_STAGE2_SCRIPT_DIGESTS = {
    "daily-market-brief": "d63e3750cfb28c2be5e3c492e2ba5bed73fe6914e8fa41033e19613fe330b05e",
    "policy-sentinel": "a78ae122087231c72b95d98749c1e6a0e764b89336d8c413538025b6faac75d9",
    "event-review": "6519b155074b9cc57af7bd6410e7379793d338b51bef67cc23682416415b9a8d",
    "etf-flow-monitor": "3b9d77321f185a570c8d481ec86021c65ac813ad393f6ee293645b2cdeb776c9",
    "earnings-report-monitor": "fa5c5f36119380028cb4bcb170cb80b84c7c0aaf8f9296939e25410a287d2c59",
    "earnings-preview-monitor": "189e96f9fcde39a388cf765196eea6e38d9fb25a224fe8a8fcb98668b5a304f1",
}
REQUIRED_TOOLS = {
    "daily-market-brief": [
        "research_run_script",
        "datahub_get_index_data",
        "datahub_get_market_snapshot",
        "datahub_get_market_activity",
        "datahub_search_news",
    ],
    "policy-sentinel": [
        "research_run_script",
        "datahub_search_news",
        "datahub_search_announcements",
    ],
    "event-review": ["research_run_script", "datahub_get_market_bars"],
    "etf-flow-monitor": [
        "research_run_script",
        "datahub_get_fund_data",
        "datahub_query_table",
    ],
    "earnings-report-monitor": [
        "research_run_script",
        "datahub_get_financials",
        "datahub_query_table",
    ],
    "earnings-preview-monitor": [
        "research_run_script",
        "datahub_get_financials",
        "datahub_get_market_snapshot",
        "datahub_get_market_activity",
        "datahub_search_research",
        "datahub_query_table",
    ],
}

CONTRACTS = {
    "daily-market-brief": {
        "provider": "synthetic",
        "mapping_id": "daily-market-brief",
        "mapping_version": "1.0.0",
        "units": {
            "price": "native_quote",
            "change_pct": "percent",
            "turnover": "CNY",
        },
        "date_semantics": "trade_date",
        "adjustment": "not_applicable",
    },
    "policy-sentinel": {
        "provider": "synthetic",
        "mapping_id": "policy-sentinel",
        "mapping_version": "1.0.0",
        "units": {"record": "document"},
        "date_semantics": "publication_date",
        "adjustment": "not_applicable",
    },
    "event-review": {
        "provider": "synthetic",
        "mapping_id": "event-review",
        "mapping_version": "1.0.0",
        "units": {
            "target_close": "CNY_per_share",
            "benchmark_close": "points",
            "volume": "share",
            "return": "decimal",
        },
        "date_semantics": "trade_date",
        "adjustment": "forward",
    },
    "etf-flow-monitor": {
        "provider": "synthetic",
        "mapping_id": "etf-flow-monitor",
        "mapping_version": "1.0.0",
        "units": {
            "shares": "share",
            "nav": "CNY_per_share",
            "price": "CNY_per_share",
            "estimated_flow": "CNY",
        },
        "date_semantics": "trade_date",
        "adjustment": "not_applicable",
    },
    "earnings-report-monitor": {
        "provider": "synthetic",
        "mapping_id": "earnings-report-monitor",
        "mapping_version": "1.0.0",
        "units": {"revenue": "CNY", "net_profit": "CNY", "growth": "percent"},
        "date_semantics": "disclosure_date",
        "adjustment": "not_applicable",
    },
    "earnings-preview-monitor": {
        "provider": "synthetic",
        "mapping_id": "earnings-preview-monitor",
        "mapping_version": "1.0.0",
        "units": {
            "profit": "CNY",
            "growth": "percent",
            "market_cap": "CNY",
            "valuation": "multiple",
            "exposure": "ratio",
            "research_coverage": "count",
        },
        "date_semantics": "disclosure_date",
        "adjustment": "not_applicable",
    },
}


def load_json(slug: str, name: str) -> dict:
    return json.loads((SKILLS_ROOT / slug / "fixtures" / name).read_text(encoding="utf-8"))


def load_calculator(slug: str):
    path = SKILLS_ROOT / slug / "scripts/calculate.py"
    spec = importlib.util.spec_from_file_location(f"stage2_{slug.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    previous_budget = sys.modules.get("cpu_budget")
    sys.modules["cpu_budget"] = cpu_budget_module
    sys.path.insert(0, str(SKILLS_ROOT / "_shared"))
    sys.path.insert(0, str(path.parent))
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
        sys.path.pop(0)
        sys.path.pop(0)
        if previous_budget is None:
            sys.modules.pop("cpu_budget", None)
        else:
            sys.modules["cpu_budget"] = previous_budget
    return module


def assert_close(actual, expected, path="result"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), path
        for key, value in expected.items():
            assert_close(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for index, value in enumerate(expected):
            assert_close(actual[index], value, f"{path}[{index}]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8), path
    else:
        assert actual == expected, path


def test_six_unique_builtin_packages_are_admitted_discoverable_and_disabled(tmp_path):
    seeded = dict(seed_packages())
    assert len(seeded) == len(seed_packages())
    assert set(SLUGS) <= set(seeded)

    catalog = CapabilityCatalog(tmp_path)
    rows = {row["id"]: row for row in catalog.list(kind="skill")["items"]}
    assert len(rows) == 30
    for slug in SLUGS:
        row = rows[slug]
        assert row["source"] == "builtin"
        assert row["status"] == "disabled"
        assert row["metadata"]["required_tools"] == REQUIRED_TOOLS[slug]
        with pytest.raises(CapabilityError) as error:
            catalog.selection(slug)
        assert error.value.code == "capability_disabled"
        detail = catalog.detail(slug)
        header = yaml.safe_load(detail["draft"]["instructions"].split("---", 2)[1])
        assert header["name"] == slug
        assert detail["checks"]["valid"] is True
        assert detail["checks"]["issues"] == []


def _version_script_digest(catalog: CapabilityCatalog, slug: str, version: int) -> str:
    files = catalog.row(slug)["versions"][str(version)]["files"]
    return next(item["sha256"] for item in files if item["path"] == "scripts/calculate.py")


def _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch, **overrides):
    monkeypatch.setenv("RESEARCH_COMPARISON_REGISTRAR_KEY", REGISTRAR_KEY_HEX)
    version = catalog.row(slug)["version"]
    evidence_dir = tmp_path / "comparison-evidence" / slug
    evidence_dir.mkdir(parents=True)
    golden = SKILLS_ROOT / slug / "fixtures/golden-result.json"
    actual = evidence_dir / "actual-result.json"
    expected = evidence_dir / "golden-result.json"
    shutil.copy2(golden, expected)
    synthetic_input = evidence_dir / "synthetic-input.json"
    actual_input = evidence_dir / "wind-excel-actual-input.json"
    fixture_input = SKILLS_ROOT / slug / "fixtures/input.json"
    shutil.copy2(fixture_input, synthetic_input)
    actual_payload = json.loads(fixture_input.read_text(encoding="utf-8"))
    actual_payload["data_contract"]["provider"] = "datahub"
    for dataset_ref in actual_payload["dataset_refs"]:
        dataset_ref["provider_id"] = "datahub"
    actual_input.write_text(
        json.dumps(actual_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    synthetic_payload = json.loads(synthetic_input.read_bytes())
    normalized_actual = copy.deepcopy(actual_payload)
    normalized_actual["data_contract"]["provider"] = synthetic_payload["data_contract"]["provider"]
    for actual_ref, synthetic_ref in zip(
        normalized_actual["dataset_refs"], synthetic_payload["dataset_refs"], strict=True
    ):
        actual_ref["provider_id"] = synthetic_ref["provider_id"]
    assert normalized_actual == synthetic_payload
    assert actual_input.read_bytes() != synthetic_input.read_bytes()
    actual.write_text(
        json.dumps(json.loads(expected.read_text(encoding="utf-8")), indent=2),
        encoding="utf-8",
    )
    golden_digest = hashlib.sha256(expected.read_bytes()).hexdigest()
    actual_digest = hashlib.sha256(actual.read_bytes()).hexdigest()
    source_hashes = json.loads(actual.read_text(encoding="utf-8"))["provenance"]["source_hashes"]
    evidence = {
        "schema_version": 2,
        "skill_slug": slug,
        "version": version,
        "script_sha256": _version_script_digest(catalog, slug, version),
        "compared_at": "2026-09-15T00:00:00Z",
        "platform": "macos",
        "comparison": "wind_excel",
        "result": "passed",
        "input_source_hashes": source_hashes,
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
        "golden_result": {"path": expected.name, "sha256": golden_digest},
        "actual_result": {"path": actual.name, "sha256": actual_digest},
    }
    evidence.update(overrides)
    evidence["registrar_signature"] = _registrar_signature(evidence)
    artifact = evidence_dir / "comparison.json"
    artifact.write_text(json.dumps(evidence), encoding="utf-8")
    return artifact, actual


def test_comparison_receipt_accepts_trusted_independent_business_equivalent_result(
    tmp_path, monkeypatch
):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    artifact, actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    expected = artifact.parent / "golden-result.json"

    assert actual.read_bytes() != expected.read_bytes()
    assert json.loads(actual.read_bytes()) == json.loads(expected.read_bytes())
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    synthetic_input = artifact.parent / evidence["synthetic_input"]["path"]
    actual_input = artifact.parent / evidence["actual_input"]["path"]
    assert json.loads(actual_input.read_bytes()) != json.loads(synthetic_input.read_bytes())
    receipt = catalog.record_comparison_receipt(artifact)
    assert receipt["actual_result_sha256"] != receipt["golden_result_sha256"]


def test_comparison_receipt_rejects_signed_duplicate_input_content(tmp_path, monkeypatch):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    artifact, _actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    synthetic_input = artifact.parent / evidence["synthetic_input"]["path"]
    actual_input = artifact.parent / evidence["actual_input"]["path"]
    actual_input.write_bytes(synthetic_input.read_bytes())
    evidence["actual_input"]["sha256"] = hashlib.sha256(actual_input.read_bytes()).hexdigest()
    evidence["registrar_signature"] = _registrar_signature(evidence)
    artifact.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(CapabilityError) as error:
        catalog.record_comparison_receipt(artifact)

    assert error.value.code == "invalid_comparison_evidence"
    assert catalog.comparison_receipt(slug) is None


def test_comparison_receipt_rejects_digest_valid_business_difference(tmp_path, monkeypatch):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    artifact, actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    result = json.loads(actual.read_bytes())
    result["metrics"]["average_change_pct"] += 0.01
    actual.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    evidence["actual_result"]["sha256"] = hashlib.sha256(actual.read_bytes()).hexdigest()
    evidence["registrar_signature"] = _registrar_signature(evidence)
    artifact.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(CapabilityError) as error:
        catalog.record_comparison_receipt(artifact)
    assert error.value.code == "invalid_comparison_evidence"


def test_comparison_business_values_use_numeric_tolerance_and_exact_labels():
    compare = CapabilityCatalog._comparison_results_equal
    expected = {
        "metric": 100.0,
        "date": "2026-09-12",
        "category": "industry",
        "signal": "up",
    }
    within_tolerance = {**expected, "metric": 100.00009}
    outside_tolerance = {**expected, "metric": 100.0002}
    wrong_label = {**expected, "signal": "down"}

    assert compare(expected, within_tolerance) is True
    assert compare(expected, outside_tolerance) is False
    assert compare(expected, wrong_label) is False


@pytest.mark.parametrize("slug", SLUGS)
def test_receipt_gated_skills_require_persistent_bound_macos_comparison(
    slug, tmp_path, monkeypatch
):
    catalog = CapabilityCatalog(tmp_path)
    version = catalog.row(slug)["version"]
    script_sha256 = _version_script_digest(catalog, slug, version)

    for action in ("enable", "rollback"):
        with pytest.raises(CapabilityError) as error:
            catalog.transition(slug, action, version if action == "rollback" else None)
        assert error.value.code == "comparison_receipt_required"

    with pytest.raises(CapabilityError) as self_declared:
        catalog.record_comparison_receipt(
            {"skill_slug": slug, "result": "passed", "script_sha256": script_sha256}
        )
    assert self_declared.value.code == "comparison_registrar_required"

    artifact, actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    recorded = catalog.record_comparison_receipt(artifact)
    assert recorded["artifact_sha256"]

    restarted = CapabilityCatalog(tmp_path)
    assert restarted.comparison_receipt(slug) == recorded
    assert restarted.transition(slug, "enable")["status"] == "enabled"
    assert restarted.transition(slug, "disable")["status"] == "disabled"
    assert restarted.transition(slug, "rollback", version)["status"] == "enabled"
    restarted.transition(slug, "disable")
    actual.write_text("{}", encoding="utf-8")
    with pytest.raises(CapabilityError) as changed:
        restarted.transition(slug, "enable")
    assert changed.value.code == "comparison_evidence_changed"


def test_selection_and_restart_reject_legacy_receipt_for_current_enabled_projection(
    tmp_path, monkeypatch
):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    artifact, _actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    catalog.record_comparison_receipt(artifact)
    catalog.transition(slug, "enable")
    row = catalog.row(slug)
    native = catalog.native_root / row["versions"][str(row["version"])]["native_name"]
    catalog.data["comparison_receipts"][f"{slug}:{row['version']}"] = {
        "schema_version": 1,
        "skill_slug": slug,
        "version": row["version"],
    }
    catalog.save()

    with pytest.raises(CapabilityError) as selection_error:
        catalog.selection(slug)
    assert selection_error.value.code == "invalid_comparison_receipt"

    restarted = CapabilityCatalog(tmp_path)
    assert restarted.row(slug)["status"] == "disabled"
    assert not native.exists()
    persisted = json.loads(restarted.index.read_text(encoding="utf-8"))
    assert persisted["items"][slug]["status"] == "disabled"


def test_restart_keeps_valid_v2_receipt_only_while_registrar_can_reverify(tmp_path, monkeypatch):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    artifact, _actual = _write_comparison_evidence(tmp_path, catalog, slug, monkeypatch)
    catalog.record_comparison_receipt(artifact)
    catalog.transition(slug, "enable")

    verified = CapabilityCatalog(tmp_path)
    assert verified.row(slug)["status"] == "enabled"
    assert verified.selection(slug)["id"] == slug

    monkeypatch.delenv("RESEARCH_COMPARISON_REGISTRAR_KEY")
    failed_closed = CapabilityCatalog(tmp_path)
    assert failed_closed.row(slug)["status"] == "disabled"
    native_name = failed_closed.row(slug)["versions"][str(failed_closed.row(slug)["version"])][
        "native_name"
    ]
    assert not (failed_closed.native_root / native_name).exists()


@pytest.mark.parametrize("slug", SLUGS)
def test_comparison_receipt_rejects_wrong_version_digest_time_or_result(
    slug, tmp_path, monkeypatch
):
    catalog = CapabilityCatalog(tmp_path)
    version = catalog.row(slug)["version"]
    invalid_values = {
        "version": version + 1,
        "script_sha256": "0" * 64,
        "compared_at": "not-a-time",
        "result": "failed",
        "platform": "windows",
        "input_source_hashes": {"unbound-source": "0" * 64},
        "unexpected": True,
    }
    for field, value in invalid_values.items():
        artifact, _actual = _write_comparison_evidence(
            tmp_path / field, catalog, slug, monkeypatch, **{field: value}
        )
        with pytest.raises(CapabilityError) as error:
            catalog.record_comparison_receipt(artifact)
        assert error.value.code == "invalid_comparison_evidence"


@pytest.mark.parametrize("slug", SLUGS)
def test_known_initial_stage2_builtin_is_migrated_to_current_disabled_version(slug, tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    row = catalog.row(slug)
    old_version = row["version"]
    calculate = next(
        item
        for item in row["versions"][str(old_version)]["files"]
        if item["path"] == "scripts/calculate.py"
    )
    calculate["sha256"] = OLD_STAGE2_SCRIPT_DIGESTS[slug]
    row["status"] = "enabled"
    catalog.save()

    upgraded = CapabilityCatalog(tmp_path)
    migrated = upgraded.row(slug)
    assert migrated["version"] == old_version + 1
    assert migrated["status"] == "disabled"
    assert (
        _version_script_digest(upgraded, slug, migrated["version"])
        != OLD_STAGE2_SCRIPT_DIGESTS[slug]
    )
    native_name = migrated["versions"][str(migrated["version"])]["native_name"]
    assert not (upgraded.native_root / native_name).exists()


@pytest.mark.parametrize("failure_point", ("publish", "save"))
def test_known_stage2_migration_failure_never_restores_enabled_native(
    failure_point, tmp_path, monkeypatch
):
    slug = "daily-market-brief"
    catalog = CapabilityCatalog(tmp_path)
    row = catalog.row(slug)
    calculate = next(
        item
        for item in row["versions"][str(row["version"])]["files"]
        if item["path"] == "scripts/calculate.py"
    )
    calculate["sha256"] = OLD_STAGE2_SCRIPT_DIGESTS[slug]
    row["status"] = "enabled"
    native = catalog.native_root / row["versions"][str(row["version"])]["native_name"]
    native.mkdir()
    (native / "SKILL.md").write_text("unsafe old projection", encoding="utf-8")
    catalog.save()

    if failure_point == "publish":
        original_publish = CapabilityCatalog.publish

        def fail_publish(self, cid, *args, **kwargs):
            if cid == slug and kwargs.get("_allow_builtin_migration"):
                raise CapabilityError("injected", "injected_publish_failure", 503)
            return original_publish(self, cid, *args, **kwargs)

        monkeypatch.setattr(CapabilityCatalog, "publish", fail_publish)
    else:
        monkeypatch.setattr(
            CapabilityCatalog,
            "save",
            lambda _self: (_ for _ in ()).throw(OSError("injected save failure")),
        )

    with pytest.raises(CapabilityError):
        CapabilityCatalog(tmp_path)
    assert not native.exists()
    if failure_point == "publish":
        persisted = json.loads(catalog.index.read_text(encoding="utf-8"))
        assert persisted["items"][slug]["status"] == "disabled"


def test_each_package_has_required_resources_and_reviewed_hashes():
    seeded = dict(seed_packages())
    expected_local = {
        "scripts/calculate.py",
        "references/input-schema.json",
        "references/output-schema.json",
        "references/field-mapping.json",
        "references/provenance.json",
        "fixtures/input.json",
        "fixtures/golden-result.json",
    }
    expected_shared = {
        "references/cpu-bounded-policy.md",
        "references/cpu-bounded-result-v1.md",
        "references/provenance-v1.md",
        "scripts/cpu_budget.py",
    }
    for slug in SLUGS:
        package = seeded[slug]
        files = {item["path"]: item for item in package["files"]}
        assert expected_local | expected_shared <= set(files)
        script_hashes = {item["sha256"] for item in files.values() if item["path"].endswith(".py")}
        assert script_hashes == set(package["reviewed_scripts"])
        for name in (
            "input-schema.json",
            "output-schema.json",
            "field-mapping.json",
            "provenance.json",
        ):
            value = json.loads(
                (SKILLS_ROOT / slug / "references" / name).read_text(encoding="utf-8")
            )
            assert isinstance(value, dict) and value
        input_schema = json.loads(
            (SKILLS_ROOT / slug / "references/input-schema.json").read_text(encoding="utf-8")
        )
        assert "data_contract" in input_schema["required"]
        contract_schema = input_schema["properties"]["data_contract"]
        if "$ref" in contract_schema:
            contract_schema = input_schema["$defs"][contract_schema["$ref"].rsplit("/", 1)[-1]]
        assert contract_schema["additionalProperties"] is False
        refs_schema = input_schema["properties"]["dataset_refs"]
        if "$ref" in refs_schema:
            refs_schema = input_schema["$defs"][refs_schema["$ref"].rsplit("/", 1)[-1]]
        assert set(refs_schema["items"]["required"]) == {
            "dataset_id",
            "provider_id",
            "as_of",
            "sha256",
        }
        assert refs_schema["maxItems"] == 32
        assert refs_schema["items"]["additionalProperties"] is False
        assert input_schema["properties"]["source_hashes"]["maxProperties"] == 32
        assert input_schema["properties"]["parameters"]["additionalProperties"] is False
        output_schema = json.loads(
            (SKILLS_ROOT / slug / "references/output-schema.json").read_text(encoding="utf-8")
        )
        assert output_schema["properties"]["metrics"]["required"]
        rows_schema = output_schema["properties"]["rows"]
        assert rows_schema.get("required") or rows_schema["items"]["required"]


@pytest.mark.parametrize("slug", SLUGS)
def test_synthetic_golden_is_deterministic_and_fast(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    expected = load_json(slug, "golden-result.json")
    started = time.monotonic()
    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))
    assert time.monotonic() - started < 2.0
    output_schema = json.loads(
        (SKILLS_ROOT / slug / "references/output-schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(output_schema).validate(actual)
    assert_close(actual, expected)
    assert actual["skill_slug"] == slug
    assert actual["compute_profile"] == "cpu_bounded_v1"
    assert actual["protocol"] == "cpu_bounded_v1"
    assert actual["research_only"] is True
    assert actual["status"] in {"complete", "partial", "insufficient_data"}
    assert isinstance(actual["limitations"], list)
    assert isinstance(actual["dataset_refs"], list) and actual["dataset_refs"]


@pytest.mark.parametrize("slug", SLUGS)
def test_runtime_data_equivalence_contract_is_required_and_exact(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    assert payload["data_contract"] == CONTRACTS[slug]

    cases = []
    missing = copy.deepcopy(payload)
    missing["data_contract"].pop("adjustment")
    cases.append(missing)
    wrong_unit = copy.deepcopy(payload)
    unit = next(iter(wrong_unit["data_contract"]["units"]))
    wrong_unit["data_contract"]["units"][unit] = "wrong_unit"
    cases.append(wrong_unit)
    wrong_adjustment = copy.deepcopy(payload)
    wrong_adjustment["data_contract"]["adjustment"] = "none"
    cases.append(wrong_adjustment)
    wrong_provider = copy.deepcopy(payload)
    wrong_provider["data_contract"]["provider"] = "unsupported-provider"
    cases.append(wrong_provider)
    wrong_ref_provider = copy.deepcopy(payload)
    wrong_ref_provider["dataset_refs"][0]["provider_id"] = "unsupported-provider"
    cases.append(wrong_ref_provider)

    for invalid in cases:
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", SLUGS)
def test_runtime_rejects_future_dataset_and_record_dates(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")

    future_ref = copy.deepcopy(payload)
    future_ref["dataset_refs"][0]["as_of"] = "2026-09-13"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(future_ref, input_bytes=1024)
    assert error.value.code == "future_data"

    future_record = copy.deepcopy(payload)
    if slug == "daily-market-brief":
        future_record["market_snapshot"][0]["date"] = "2026-09-13"
    elif slug == "policy-sentinel":
        future_record["records"][0]["published_at"] = "2026-09-13"
    elif slug == "event-review":
        future_record["target_series"][-1]["date"] = "2026-09-13"
    elif slug == "etf-flow-monitor":
        future_record["rows"][0]["date"] = "2026-09-13"
    else:
        future_record["records"][0]["disclosure_date"] = "2026-09-13"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(future_record, input_bytes=1024)
    assert error.value.code == "future_data"


@pytest.mark.parametrize("slug", SLUGS)
def test_runtime_requires_extended_iso_dates_at_all_boundaries(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")

    compact_root = copy.deepcopy(payload)
    compact_root["as_of"] = "20260912"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(compact_root, input_bytes=1024)
    assert error.value.code == "invalid_date"

    compact_ref = copy.deepcopy(payload)
    compact_ref["dataset_refs"][0]["as_of"] = "20260912"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(compact_ref, input_bytes=1024)
    assert error.value.code == "invalid_date"

    compact_record = copy.deepcopy(payload)
    if slug == "daily-market-brief":
        compact_record["market_snapshot"][0]["date"] = "20260912"
    elif slug == "policy-sentinel":
        compact_record["records"][0]["published_at"] = "20260912"
    elif slug == "event-review":
        compact_record["target_series"][0]["date"] = "20260912"
    elif slug == "etf-flow-monitor":
        compact_record["rows"][0]["date"] = "20260912"
    else:
        compact_record["records"][0]["disclosure_date"] = "20260912"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(compact_record, input_bytes=1024)
    assert error.value.code == "invalid_date"


@pytest.mark.parametrize("slug", SLUGS)
def test_source_hashes_are_validated_or_explicitly_degraded(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")

    missing = copy.deepcopy(payload)
    missing.pop("source_hashes")
    result = module.calculate(missing, input_bytes=1024)
    assert result["provenance"]["source_hashes"] == {}
    assert "source_hashes_missing" in result["limitations"]
    assert result["status"] == "partial"

    malformed = copy.deepcopy(payload)
    malformed["source_hashes"] = {"synthetic": "not-a-sha256"}
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(malformed, input_bytes=1024)
    assert error.value.code == "invalid_source_hashes"

    digest = "a" * 64
    for invalid_hashes in (
        None,
        {" ": digest},
        {" source ": digest, "source": "b" * 64},
        {"source\nname": digest},
        {"source\rname": digest},
        {"source\u2028name": digest},
        {"source\u2029name": digest},
    ):
        invalid = copy.deepcopy(payload)
        invalid["source_hashes"] = invalid_hashes
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code == "invalid_source_hashes"


def test_all_source_hash_schemas_require_canonical_nonblank_keys():
    expected = {
        "type": "string",
        "minLength": 1,
        "pattern": r"^(?!.*[\r\n\u2028\u2029])\S(?:.*\S)?$",
    }
    for slug in SLUGS:
        schema = json.loads(
            (SKILLS_ROOT / slug / "references/input-schema.json").read_text(encoding="utf-8")
        )
        property_names = schema["properties"]["source_hashes"]["propertyNames"]
        assert property_names == expected
        validator = Draft202012Validator({"type": "object", "propertyNames": property_names})
        assert not list(validator.iter_errors({"source name": "value"}))
        for invalid_key in (
            "source\nname",
            "source\rname",
            "source\u2028name",
            "source\u2029name",
        ):
            assert list(validator.iter_errors({invalid_key: "value"}))


@pytest.mark.parametrize("slug", ["daily-market-brief", "etf-flow-monitor"])
def test_cny_calculators_reject_conflicting_currency(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    payload["parameters"]["currency"] = "USD"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"


def test_daily_runtime_requires_all_schema_collections_and_integer_breadth():
    module = load_calculator("daily-market-brief")
    payload = load_json("daily-market-brief", "input.json")

    for field in ("breadth", "sectors", "themes", "news"):
        missing = copy.deepcopy(payload)
        missing.pop(field)
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(missing, input_bytes=1024)
        assert error.value.code == "missing_required_field"

    for field in ("advances", "declines", "flat"):
        fractional = copy.deepcopy(payload)
        fractional["breadth"][field] = 1.5
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(fractional, input_bytes=1024)
        assert error.value.code == "invalid_field_type"


def test_daily_and_etf_currency_schemas_are_fixed_to_cny():
    for slug in ("daily-market-brief", "etf-flow-monitor"):
        schema = json.loads(
            (SKILLS_ROOT / slug / "references/input-schema.json").read_text(encoding="utf-8")
        )
        assert schema["properties"]["parameters"]["properties"]["currency"] == {"const": "CNY"}

    daily_schema = json.loads(
        (SKILLS_ROOT / "daily-market-brief" / "references/input-schema.json").read_text(
            encoding="utf-8"
        )
    )
    daily_module = load_calculator("daily-market-brief")
    assert set(daily_module.REQUIRED_ROOT_FIELDS) == set(daily_schema["required"])


@pytest.mark.parametrize("slug", SLUGS)
def test_runtime_rejects_unknown_fields_at_every_nested_boundary(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    cases = []

    unknown_param = copy.deepcopy(payload)
    unknown_param["parameters"]["unreviewed"] = True
    cases.append(unknown_param)
    unknown_ref = copy.deepcopy(payload)
    unknown_ref["dataset_refs"][0]["unreviewed"] = True
    cases.append(unknown_ref)
    unknown_contract = copy.deepcopy(payload)
    unknown_contract["data_contract"]["unreviewed"] = True
    cases.append(unknown_contract)
    unknown_units = copy.deepcopy(payload)
    unknown_units["data_contract"]["units"]["unreviewed"] = "unit"
    cases.append(unknown_units)
    unknown_record = copy.deepcopy(payload)
    if slug == "daily-market-brief":
        unknown_record["market_snapshot"][0]["unreviewed"] = True
    elif slug == "event-review":
        unknown_record["target_series"][0]["unreviewed"] = True
    elif slug == "etf-flow-monitor":
        unknown_record["rows"][0]["unreviewed"] = True
    else:
        unknown_record["records"][0]["unreviewed"] = True
    cases.append(unknown_record)
    if slug == "etf-flow-monitor":
        unknown_classification = copy.deepcopy(payload)
        unknown_classification["rows"][0]["classification"]["unreviewed"] = "category"
        cases.append(unknown_classification)

    for invalid in cases:
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code in {"unknown_field", "data_not_equivalent"}


@pytest.mark.parametrize("slug", SLUGS)
def test_calculators_reject_missing_wrong_empty_and_oversized_inputs(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    required = module.REQUIRED_ROOT_FIELDS[0]

    missing = dict(payload)
    missing.pop(required)
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(missing, input_bytes=1)
    assert error.value.code == "missing_required_field"

    wrong = dict(payload)
    wrong[required] = 1
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(wrong, input_bytes=1)
    assert error.value.code == "invalid_field_type"

    empty = dict(payload)
    empty[module.PRIMARY_ROWS_FIELD] = []
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(empty, input_bytes=1)
    assert error.value.code == "empty_input"

    with pytest.raises(WorkloadTooLarge) as error:
        module.calculate(payload, input_bytes=MAX_INPUT_BYTES + 1)
    assert error.value.code == "workload_too_large"


@pytest.mark.parametrize("slug", SLUGS)
def test_calculators_reject_unknown_root_fields_and_incomplete_dataset_refs(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")

    unknown = dict(payload)
    unknown["unreviewed_input"] = "ignored"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(unknown, input_bytes=1024)
    assert error.value.code == "unknown_field"

    incomplete_ref = dict(payload)
    incomplete_ref["dataset_refs"] = [{"dataset_id": "opaque-only"}]
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(incomplete_ref, input_bytes=1024)
    assert error.value.code == "invalid_dataset_ref"


NUMERIC_SKILLS = (
    "daily-market-brief",
    "event-review",
    "etf-flow-monitor",
    "earnings-report-monitor",
    "earnings-preview-monitor",
)


def _set_primary_number(payload: dict, slug: str, value: float) -> None:
    if slug == "daily-market-brief":
        payload["market_snapshot"][0]["price"] = value
    elif slug == "event-review":
        payload["target_series"][0]["close"] = value
    elif slug == "etf-flow-monitor":
        payload["rows"][0]["shares"] = value
    elif slug == "earnings-report-monitor":
        payload["records"][0]["revenue"] = value
    else:
        payload["records"][0]["profit_low"] = value


@pytest.mark.parametrize("slug", NUMERIC_SKILLS)
def test_cli_maps_integer_float_overflow_to_stable_json(slug, tmp_path):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    _set_primary_number(payload, slug, 10**400)
    path = tmp_path / "overflow.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    stdout = StringIO()
    stderr = StringIO()
    with chdir(tmp_path), redirect_stdout(stdout), redirect_stderr(stderr):
        assert module.main([path.name]) == 1
    assert "Traceback" not in stderr.getvalue()
    assert json.loads(stderr.getvalue().splitlines()[-1]) == {
        "error": {"code": "invalid_number", "message": "invalid_number"}
    }


@pytest.mark.parametrize("slug", SLUGS)
def test_cli_rejects_nonfinite_result_serialization(slug, tmp_path, monkeypatch):
    module = load_calculator(slug)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(load_json(slug, "input.json")), encoding="utf-8")
    monkeypatch.setattr(module, "calculate", lambda *_args, **_kwargs: {"metric": math.nan})
    stdout = StringIO()
    stderr = StringIO()
    with chdir(tmp_path), redirect_stdout(stdout), redirect_stderr(stderr):
        assert module.main([path.name]) == 1
    assert json.loads(stderr.getvalue().splitlines()[-1])["error"]["code"] == "invalid_number"


@pytest.mark.parametrize(
    "slug",
    ("daily-market-brief", "event-review", "etf-flow-monitor", "earnings-preview-monitor"),
)
def test_derived_numeric_overflow_is_rejected(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    if slug == "daily-market-brief":
        for row in payload["market_snapshot"]:
            row["turnover"] = 1e308
    elif slug == "event-review":
        for row in payload["target_series"]:
            row["close"] = 1e-308
        payload["target_series"][-1]["close"] = 1e308
    elif slug == "etf-flow-monitor":
        payload["rows"][0].update(shares=1e308, prior_shares=1.0, nav=1e308)
    else:
        payload["records"][0].update(profit_low=1e308, profit_high=1e308)
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "invalid_number"


def test_earnings_preview_rejects_mixed_or_wrong_report_period():
    module = load_calculator("earnings-preview-monitor")
    payload = load_json("earnings-preview-monitor", "input.json")
    for index in (0, 1):
        invalid = copy.deepcopy(payload)
        invalid["records"][index]["report_period"] = "2026-03-31"
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code == "data_not_equivalent"


def test_daily_provenance_reuses_normalized_dataset_refs():
    module = load_calculator("daily-market-brief")
    payload = load_json("daily-market-brief", "input.json")
    payload["dataset_refs"][0]["dataset_id"] = " fixture-daily "
    payload["dataset_refs"][0]["sha256"] = "ABCDEF" * 10 + "ABCD"
    result = module.calculate(payload, input_bytes=1024)
    assert result["provenance"]["dataset_refs"] == result["dataset_refs"]
    assert result["dataset_refs"][0]["dataset_id"] == "fixture-daily"
    assert result["dataset_refs"][0]["sha256"] == ("abcdef" * 10 + "abcd")


@pytest.mark.parametrize("slug", SLUGS)
def test_calculator_cli_accepts_only_relative_json_input(slug):
    module = load_calculator(slug)
    package = SKILLS_ROOT / slug
    stdout = StringIO()
    stderr = StringIO()
    with chdir(package), redirect_stdout(stdout), redirect_stderr(stderr):
        assert module.main(["fixtures/input.json"]) == 0
    output = json.loads(stdout.getvalue())
    assert output["skill_slug"] == slug

    stdout = StringIO()
    stderr = StringIO()
    with chdir(package), redirect_stdout(stdout), redirect_stderr(stderr):
        assert module.main([str((package / "fixtures/input.json").resolve())]) == 1
    error = json.loads(stderr.getvalue().splitlines()[-1])
    assert error == {"error": {"code": "unsafe_input_path", "message": "unsafe_input_path"}}


@pytest.mark.parametrize("slug", SLUGS)
@pytest.mark.parametrize("link_kind", ("file", "directory"))
def test_calculator_cli_rejects_symlinked_input_or_parent(slug, link_kind, tmp_path):
    module = load_calculator(slug)
    real = tmp_path / "real"
    real.mkdir()
    target = real / "input.json"
    target.write_text(json.dumps(load_json(slug, "input.json")), encoding="utf-8")
    if link_kind == "file":
        link = tmp_path / "input.json"
        link_target = target
        argument = link.name
    else:
        link = tmp_path / "linked"
        link_target = real
        argument = "linked/input.json"
    try:
        link.symlink_to(link_target, target_is_directory=link_kind == "directory")
    except OSError:
        pytest.skip("symlinks unavailable on this host")
    stderr = StringIO()
    with chdir(tmp_path), redirect_stdout(StringIO()), redirect_stderr(stderr):
        assert module.main([argument]) == 1
    assert json.loads(stderr.getvalue().splitlines()[-1])["error"]["code"] == "unsafe_input_path"


def test_all_calculator_clis_use_shared_safe_json_loader():
    shared = (SKILLS_ROOT / "_shared/input_contract.py").read_text(encoding="utf-8")
    assert "def load_relative_json" in shared
    for slug in SLUGS:
        source = (SKILLS_ROOT / slug / "scripts/calculate.py").read_text(encoding="utf-8")
        assert "load_relative_json" in source
        assert "def _path(" not in source
        assert "def _input_path(" not in source


@pytest.mark.parametrize("slug", SLUGS)
def test_calculator_cli_preserves_safe_workload_metadata(slug, tmp_path):
    module = load_calculator(slug)
    oversized = tmp_path / "oversized.json"
    with oversized.open("wb") as handle:
        handle.truncate(MAX_INPUT_BYTES + 1)
    stderr = StringIO()
    with chdir(tmp_path), redirect_stderr(stderr):
        assert module.main([oversized.name]) == 1
    error = json.loads(stderr.getvalue().splitlines()[-1])["error"]
    assert error["code"] == error["message"] == "workload_too_large"
    assert error["metadata"] == {
        "actual": MAX_INPUT_BYTES + 1,
        "limit": MAX_INPUT_BYTES,
        "reduce_scope": True,
        "resource": "input_bytes",
    }


def _stress_payload(slug: str) -> dict:
    payload = load_json(slug, "input.json")
    if slug == "daily-market-brief":
        payload["market_snapshot"] = [
            {
                "date": payload["as_of"],
                "asset": f"{index:06d}.SH",
                "name": f"asset-{index}",
                "price": 100 + index / 100,
                "change_pct": index % 20 - 10,
                "turnover": 1_000_000 + index,
            }
            for index in range(4_800)
        ]
        payload["sectors"] = []
        payload["themes"] = []
        payload["news"] = []
    elif slug == "policy-sentinel":
        payload["records"] = [
            {
                "evidence_id": f"evidence-{index}",
                "title": f"监管记录 {index}",
                "summary": "合成摘要",
                "published_at": payload["as_of"],
                "source": "synthetic",
                "source_ref": f"source-{index}",
                "potential_impact_objects": ["object"],
            }
            for index in range(4_800)
        ]
    elif slug == "event-review":
        last_day = date.fromisoformat(payload["as_of"])
        first_day = last_day - timedelta(days=4_799)
        days = [(first_day + timedelta(days=index)).isoformat() for index in range(4_800)]
        payload["target_series"] = [
            {"date": day, "close": 100 + index / 1000, "volume": 1_000 + index}
            for index, day in enumerate(days)
        ]
        payload["benchmark_series"] = [
            {"date": day, "close": 1_000 + index / 500, "volume": 10_000 + index}
            for index, day in enumerate(days)
        ]
        payload["event_date"] = days[-3]
    elif slug == "etf-flow-monitor":
        template = payload["rows"][0]
        payload["rows"] = [
            {**copy.deepcopy(template), "code": f"{510000 + index:06d}"} for index in range(48)
        ]
    else:
        template = payload["records"][0]
        payload["records"] = [
            {**copy.deepcopy(template), "security": f"{index:06d}.SZ"} for index in range(48)
        ]
        if slug == "earnings-report-monitor":
            payload["parameters"]["expected_count"] = 50
    return payload


@pytest.mark.parametrize("slug", SLUGS)
def test_calculator_near_limit_process_stays_within_time_and_peak_rss(slug, tmp_path):
    payload = _stress_payload(slug)
    research_root = tmp_path / "research"
    session = research_root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    scripts = session / "resources" / "calculator" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SKILLS_ROOT / slug / "scripts/calculate.py", scripts / "calculate.py")
    shutil.copy2(SKILLS_ROOT / "_shared/cpu_budget.py", scripts / "cpu_budget.py")
    shutil.copy2(SKILLS_ROOT / "_shared/input_contract.py", scripts / "input_contract.py")
    input_path = session / "inputs" / "input.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert input_path.stat().st_size < 8 * 1024 * 1024
    code = """
import json
import sys
from pathlib import Path
scripts = Path(__SCRIPTS__)
sys.path.insert(0, str(scripts))
namespace = {'__name__': 'reviewed_skill_resource'}
source = (scripts / 'calculate.py').read_text(encoding='utf-8')
exec(compile(source, 'scripts/calculate.py', 'exec'), namespace)
input_path = Path(__INPUT__)
raw = input_path.read_bytes()
result = namespace['calculate'](json.loads(raw), input_bytes=len(raw))
print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
""".replace("__SCRIPTS__", repr(str(scripts))).replace("__INPUT__", repr(str(input_path)))
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
    supervisor_result = json.loads(stdout)
    assert supervisor_result["status"] == "completed", supervisor_result
    assert len(supervisor_result["stdout"].encode("utf-8")) < 64 * 1024
    output = json.loads(supervisor_result["stdout"])
    assert output["skill_slug"] == slug
    expected_rows = (
        9_600
        if slug == "event-review"
        else (
            4_800
            if slug
            in {
                "daily-market-brief",
                "policy-sentinel",
            }
            else 48
        )
    )
    assert output["row_delivery"]["processed_input_rows"] == expected_rows
    if output["row_delivery"]["mode"] == "summary_with_dataset_refs":
        assert output["row_delivery"]["dataset_refs_reused"] is True
        assert "dataset_refs" not in output["row_delivery"]
    assert len(json.dumps(output, ensure_ascii=False, allow_nan=False).encode("utf-8")) <= 64 * 1024
    assert elapsed < 10
    assert 0 < peak_rss_bytes < 1024**3
    print(
        json.dumps(
            {"slug": slug, "elapsed_seconds": elapsed, "peak_rss_bytes": peak_rss_bytes},
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("slug", SLUGS)
def test_calculator_cli_exact_65536_byte_stdout_completes_in_real_sandbox(slug, tmp_path):
    research_root = tmp_path / "research"
    session = research_root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    scripts = session / "resources" / "calculator" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SKILLS_ROOT / slug / "scripts/calculate.py", scripts / "calculate.py")
    shutil.copy2(SKILLS_ROOT / "_shared/cpu_budget.py", scripts / "cpu_budget.py")
    shutil.copy2(SKILLS_ROOT / "_shared/input_contract.py", scripts / "input_contract.py")
    code = """
import sys
from pathlib import Path
scripts = Path(__SCRIPTS__)
sys.path.insert(0, str(scripts))
namespace = {'__name__': 'reviewed_skill_resource'}
source = (scripts / 'calculate.py').read_text(encoding='utf-8')
exec(compile(source, 'scripts/calculate.py', 'exec'), namespace)
namespace['load_relative_json'] = lambda *_args, **_kwargs: ({}, 0)
namespace['calculate'] = lambda *_args, **_kwargs: {}
namespace['strict_json_dumps'] = lambda *_args, **_kwargs: 'x' * 65536
if namespace['main'](['input.json']) != 0:
    raise RuntimeError('calculator main failed')
""".replace("__SCRIPTS__", repr(str(scripts)))
    result = subprocess.run(
        [
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
            "65536",
        ],
        input=json.dumps({"code": code}),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    supervisor = json.loads(result.stdout)
    assert supervisor["status"] == "completed", supervisor
    assert supervisor["stderr"] == ""
    assert len(supervisor["stdout"].encode("utf-8")) == 65536


def test_large_provenance_and_text_fail_with_compact_json_inside_real_sandbox(tmp_path):
    slug = "daily-market-brief"
    payload = load_json(slug, "input.json")
    payload["news"][0]["title"] = "长" * 20_000
    payload["dataset_refs"] = [
        {
            "dataset_id": f"dataset-{index:03d}-" + "x" * 80,
            "provider_id": "synthetic",
            "as_of": payload["as_of"],
            "sha256": f"{index:064x}",
        }
        for index in range(300)
    ]
    payload["source_hashes"] = {
        f"source-{index:03d}-" + "x" * 80: f"{index + 1:064x}" for index in range(300)
    }
    research_root = tmp_path / "research"
    session = research_root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    scripts = session / "resources" / "calculator" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("calculate.py",):
        shutil.copy2(SKILLS_ROOT / slug / "scripts" / name, scripts / name)
    for name in ("cpu_budget.py", "input_contract.py"):
        shutil.copy2(SKILLS_ROOT / "_shared" / name, scripts / name)
    (session / "inputs/input.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
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
    result = subprocess.run(
        [
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
        ],
        input=json.dumps({"code": code}),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    supervisor = json.loads(result.stdout)
    assert supervisor["status"] == "completed", supervisor
    assert len(supervisor["stdout"].encode()) + len(supervisor["stderr"].encode()) < 64 * 1024
    error = json.loads(supervisor["stderr"].splitlines()[-1])
    assert error["error"]["code"] == "workload_too_large"
    assert error["error"]["metadata"]["reduce_scope"] is True


def test_strict_json_envelope_counts_utf8_bytes_and_fails_compactly():
    with pytest.raises(input_contract_module.ContractTooLarge) as error:
        input_contract_module.strict_json_dumps({"text": "长" * 22_000}, error=ValueError)
    assert error.value.metadata == {
        "resource": "result_bytes",
        "limit": 64 * 1024,
        "actual": len(json.dumps({"text": "长" * 22_000}, ensure_ascii=False).encode()),
        "reduce_scope": True,
    }


@pytest.mark.parametrize("slug", SLUGS)
@pytest.mark.parametrize("field", ("dataset_refs", "source_hashes"))
def test_provenance_collection_counts_are_bounded_before_result_build(slug, field):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    if field == "dataset_refs":
        template = payload[field][0]
        payload[field] = [{**template, "dataset_id": f"dataset-{index}"} for index in range(300)]
    else:
        payload[field] = {f"source-{index}": f"{index:064x}" for index in range(300)}
    with pytest.raises(ValueError) as error:
        module.calculate(payload, input_bytes=1024)
    assert getattr(error.value, "code", None) == "workload_too_large"
    assert error.value.metadata["reduce_scope"] is True


def test_safe_json_loader_rejects_ancestor_directory_switch_race(tmp_path, monkeypatch):
    victim = tmp_path / "victim"
    attacker = tmp_path / "attacker"
    victim.mkdir()
    attacker.mkdir()
    (victim / "input.json").write_text('{"source":"victim"}', encoding="utf-8")
    (attacker / "input.json").write_text('{"source":"attacker"}', encoding="utf-8")
    original = tmp_path / "original"
    real_lstat = input_contract_module.os.lstat
    real_open = input_contract_module.os.open
    switched = False

    def switch_ancestor():
        nonlocal switched
        if switched:
            return
        victim.rename(original)
        victim.symlink_to(attacker, target_is_directory=True)
        switched = True

    def racing_lstat(path, *args, **kwargs):
        if Path(path) == victim / "input.json":
            switch_ancestor()
        return real_lstat(path, *args, **kwargs)

    def racing_open(path, flags, *args, **kwargs):
        if path == "victim" and kwargs.get("dir_fd") is not None:
            switch_ancestor()
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(input_contract_module.os, "lstat", racing_lstat)
    monkeypatch.setattr(input_contract_module.os, "open", racing_open)
    with chdir(tmp_path), pytest.raises(ValueError) as error:
        input_contract_module.load_relative_json(
            "victim/input.json", error=ValueError, budget=WorkloadBudget()
        )
    assert str(error.value) == "unsafe_input_path"


def test_event_beta_is_unavailable_when_pre_event_sample_is_insufficient():
    module = load_calculator("event-review")
    result = module.calculate(load_json("event-review", "input.json"), input_bytes=1024)
    assert result["metrics"]["beta_alpha"] == {
        "status": "unavailable",
        "observations": 2,
        "beta": None,
        "daily_alpha": None,
    }
    assert "beta_alpha_insufficient_pre_event_sample" in result["limitations"]


def test_policy_requires_auditable_evidence():
    module = load_calculator("policy-sentinel")
    payload = load_json("policy-sentinel", "input.json")
    payload["records"][0].pop("source_ref")
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "evidence_required"


def test_etf_requires_user_supplied_classification():
    module = load_calculator("etf-flow-monitor")
    payload = load_json("etf-flow-monitor", "input.json")
    payload["rows"][0].pop("classification")
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "classification_required"


@pytest.mark.parametrize("slug", ["earnings-report-monitor", "earnings-preview-monitor"])
def test_earnings_monitors_fail_closed_on_missing_record_field(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    payload["records"][0].pop(module.REQUIRED_RECORD_FIELDS[0])
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "missing_required_field"


def test_daily_brief_rejects_absent_market_data():
    module = load_calculator("daily-market-brief")
    payload = load_json("daily-market-brief", "input.json")
    payload["market_snapshot"] = []
    payload["sectors"] = []
    payload["themes"] = []
    payload["news"] = []
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "empty_input"


def test_stage2_packages_have_no_forbidden_runtime_or_host_assumptions():
    forbidden_words = (
        "torch|tensorflow|jax|cuda|mps|metal|cjpy|subprocess|concurrent|" "threadpoolexecutor|vba"
    )
    for slug in SLUGS:
        for path in (SKILLS_ROOT / slug).rglob("*"):
            if path.is_file() and path.suffix in {".json", ".md", ".py"}:
                text = path.read_text(encoding="utf-8").lower()
                assert re.search(rf"\b(?:{forbidden_words})\b", text) is None, (slug, path.name)
                assert not any(token in text for token in ("cdn.", "/users/", "c:\\\\")), (
                    slug,
                    path.name,
                )
                if path.suffix == ".py":
                    assert not any(
                        token in text
                        for token in ("http://", "https://", "socket", "urllib", "requests")
                    ), (slug, path.name)

    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    absolute_bin_literal = f"{chr(34)}{chr(47)}bin{chr(47)}"
    assert absolute_bin_literal not in test_source
