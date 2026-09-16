"""Deterministic contracts and safety gates for CPU quant Skills stage 4."""

from __future__ import annotations

import ast
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
from app.research_web.skills._shared import cpu_budget as cpu_budget_module
from app.research_web.skills._shared import input_contract as input_contract_module

PROJECT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT / "app/research_web/skills"
SLUGS = (
    "rate-ma-timing-research",
    "equity-risk-premium-timing",
    "style-rotation-research",
    "platform-breakout",
    "chanlun",
)
SERIES_IDENTITY_SLUGS = SLUGS[:3]
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
REQUIRED_PACKAGE_FILES_BY_SLUG = {
    "style-rotation-research": {
        "fixtures/moving-average-deviation-input.json",
        "fixtures/moving-average-deviation-golden-result.json",
    }
}
DATE_FIELDS = {
    "rate-ma-timing-research": "date",
    "equity-risk-premium-timing": "date",
    "style-rotation-research": "date",
    "platform-breakout": "date",
    "chanlun": "date",
}
NUMERIC_FIELDS = {
    "rate-ma-timing-research": "asset_close",
    "equity-risk-premium-timing": "pe_ttm",
    "style-rotation-research": "style_a_close",
    "platform-breakout": "close",
    "chanlun": "close",
}
REGISTRAR_KEY_HEX = "d4" * 32
OFFICIAL_JSON_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"

USER_INPUT_SERIES_IDENTITIES = {
    "rate-ma-timing-research": {
        "asset_series": {
            "role": "asset_index",
            "identity": "CSI.000300.SH.close",
            "version": "close_v1",
            "tenor": "spot",
        },
        "rate_series": {
            "role": "government_bond_yield",
            "identity": "CN.CGB.yield.10Y",
            "version": "yield_pct_v1",
            "tenor": "10Y",
        },
    },
    "equity-risk-premium-timing": {
        "index_series": {
            "role": "equity_index_valuation",
            "identity": "CSI.000300.SH.pe_ttm",
            "version": "pe_ttm_v1",
            "tenor": "spot",
        },
        "bond_yield_series": {
            "role": "government_bond_yield",
            "identity": "CN.CGB.yield.10Y",
            "version": "yield_pct_v1",
            "tenor": "10Y",
        },
    },
    "style-rotation-research": {
        "style_a_series": {
            "role": "style_a_index",
            "identity": "CSI.style.growth.close",
            "version": "close_v1",
            "tenor": "spot",
        },
        "style_b_series": {
            "role": "style_b_index",
            "identity": "CSI.style.value.close",
            "version": "close_v1",
            "tenor": "spot",
        },
    },
}


def load_json(slug: str, name: str) -> dict:
    return json.loads((SKILLS_ROOT / slug / "fixtures" / name).read_text(encoding="utf-8"))


def load_calculator(slug: str):
    path = SKILLS_ROOT / slug / "scripts/calculate.py"
    spec = importlib.util.spec_from_file_location(f"stage4_{slug.replace('-', '_')}", path)
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


def test_rate_ma_timing_research_matches_transparent_lagged_rule():
    module = load_calculator("rate-ma-timing-research")
    payload = load_json("rate-ma-timing-research", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(actual, load_json("rate-ma-timing-research", "golden-result.json"))
    assert actual["metrics"]["latest_research_signal"] == "rate_falling_above_deviation"
    assert actual["research_only"] is True


def test_equity_risk_premium_timing_uses_rolling_empirical_percentile():
    module = load_calculator("equity-risk-premium-timing")
    payload = load_json("equity-risk-premium-timing", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(actual, load_json("equity-risk-premium-timing", "golden-result.json"))
    assert actual["metrics"]["latest_research_signal"] == "elevated_risk_premium"


def test_style_rotation_research_uses_explicit_relative_strength_momentum():
    module = load_calculator("style-rotation-research")
    payload = load_json("style-rotation-research", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(actual, load_json("style-rotation-research", "golden-result.json"))
    assert actual["metrics"]["latest_research_signal"] == "style_a_preferred"


def test_style_rotation_moving_average_deviation_has_independent_golden_and_signal():
    module = load_calculator("style-rotation-research")
    payload = load_json("style-rotation-research", "moving-average-deviation-input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(
        actual,
        load_json("style-rotation-research", "moving-average-deviation-golden-result.json"),
    )
    assert actual["parameters"]["method"] == "moving_average_deviation"
    assert actual["metrics"]["latest_research_signal"] == "style_a_preferred"
    assert math.isclose(
        actual["rows"][-1]["deviation"],
        0.015173206016441121,
        rel_tol=1e-6,
        abs_tol=1e-8,
    )


def test_platform_breakout_uses_only_prior_window_and_bounded_watchlist():
    module = load_calculator("platform-breakout")
    payload = load_json("platform-breakout", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(actual, load_json("platform-breakout", "golden-result.json"))
    assert actual["rows"][0]["research_signal"] == "confirmed_breakout"


def test_chanlun_builds_deterministic_non_recursive_confirmed_strokes():
    module = load_calculator("chanlun")
    payload = load_json("chanlun", "input.json")

    actual = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))

    assert_close(actual, load_json("chanlun", "golden-result.json"))
    assert actual["metrics"]["latest_research_signal"] == "confirmed_up_swing"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_packages_have_strict_valid_schemas_goldens_and_provenance(slug):
    folder = SKILLS_ROOT / slug
    required_files = REQUIRED_PACKAGE_FILES | REQUIRED_PACKAGE_FILES_BY_SLUG.get(slug, set())
    assert required_files <= {
        path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()
    }
    input_schema = json.loads((folder / "references/input-schema.json").read_text(encoding="utf-8"))
    output_schema = json.loads(
        (folder / "references/output-schema.json").read_text(encoding="utf-8")
    )
    assert input_schema["$schema"] == OFFICIAL_JSON_SCHEMA_URI
    assert output_schema["$schema"] == OFFICIAL_JSON_SCHEMA_URI
    Draft202012Validator.check_schema(input_schema)
    Draft202012Validator.check_schema(output_schema)
    assert (
        list(
            Draft202012Validator(input_schema, format_checker=FormatChecker()).iter_errors(
                load_json(slug, "input.json")
            )
        )
        == []
    )
    assert (
        list(
            Draft202012Validator(output_schema, format_checker=FormatChecker()).iter_errors(
                load_json(slug, "golden-result.json")
            )
        )
        == []
    )
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
    assert provenance["source_text_included"] is False
    header = yaml.safe_load((folder / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    assert header["name"] == slug


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_schema_fields_and_runtime_contract_constants_are_equivalent(slug):
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
    if slug in SERIES_IDENTITY_SLUGS:
        identity_schema = schema["properties"]["series_identity"]
        assert set(identity_schema["required"]) == set(module.SERIES_IDENTITY_FIELDS)
        assert set(module.SYNTHETIC_SERIES_IDENTITIES) == set(module.SERIES_IDENTITY_FIELDS)
        for name, expected in module.SERIES_ROLE_CONTRACTS.items():
            descriptor = identity_schema["properties"][name]
            assert set(descriptor["required"]) == set(module.SERIES_DESCRIPTOR_FIELDS)
            assert descriptor["properties"]["role"] == {"const": expected["role"]}
            assert descriptor["properties"]["version"] == {"const": expected["version"]}
            assert descriptor["properties"]["tenor"] == {"const": expected["tenor"]}
            assert descriptor["properties"]["identity"] == {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": module.SERIES_IDENTITY_PATTERN,
            }
    actual = module.calculate(load_json(slug, "input.json"), input_bytes=1024)
    assert set(actual) == set(output_schema["properties"])
    assert actual["protocol"] == "cpu_bounded_v1"
    assert actual["research_only"] is True
    assert set(actual["research_summary"]) == {
        "sample_size",
        "conditions",
        "counterexamples",
        "failure_conditions",
        "data_cutoff",
    }


def test_stage4_source_provenance_records_only_verified_full_digests():
    verified = {
        "rate-ma-timing-research": "d01ac5155c1ccd07a7b1d192b555b0a9f0d13e951c3ebe0d4199c85d22d1d028",
        "equity-risk-premium-timing": "1abb2d15f810282ce3617246594de65c02636c57e8b510eff4184dc7044c7ed8",
        "style-rotation-research": "9450f30aebb1271b05bc04d086f22676d1e793e22822c43b1a5f7bc3e7e6969a",
    }
    unavailable = {
        "platform-breakout": ["66751cd4", "7b33cedd", "1dc9d6f", "a2978893"],
        "chanlun": ["df54c4ef", "6762dce"],
    }
    for slug, digest in verified.items():
        provenance = json.loads(
            (SKILLS_ROOT / slug / "references/provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["source_artifacts_available"] is True
        assert provenance["source_artifacts"]["reference_workbook_sha256"] == digest
        assert provenance["macros_or_formulas_executed"] is False
    for slug, prefixes in unavailable.items():
        provenance = json.loads(
            (SKILLS_ROOT / slug / "references/provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["source_artifacts_available"] is False
        assert "source_artifacts" not in provenance
        assert provenance["unmatched_candidate_sha256_prefixes"] == prefixes
        assert "source unavailable" in provenance["note"]


@pytest.mark.parametrize("slug", SLUGS)
@pytest.mark.parametrize("layer", ("root", "parameters", "record", "dataset_ref"))
def test_stage4_runtime_rejects_unknown_fields_at_every_input_layer(slug, layer):
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
def test_stage4_runtime_rejects_contract_provider_hash_and_future_mismatches(slug):
    module = load_calculator(slug)
    base = load_json(slug, "input.json")

    mismatch = copy.deepcopy(base)
    mismatch["data_contract"]["mapping_version"] = "2.0.0"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(mismatch, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"

    provider = copy.deepcopy(base)
    provider["dataset_refs"][0]["provider_id"] = "user_input"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(provider, input_bytes=1024)
    assert error.value.code == "data_not_equivalent"

    bad_hash = copy.deepcopy(base)
    bad_hash["source_hashes"] = {"synthetic": "not-sha256"}
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(bad_hash, input_bytes=1024)
    assert error.value.code == "invalid_source_hashes"

    future = copy.deepcopy(base)
    future["records"][0][DATE_FIELDS[slug]] = "2026-09-17"
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(future, input_bytes=1024)
    assert error.value.code == "future_data"


@pytest.mark.parametrize("slug", SERIES_IDENTITY_SLUGS)
def test_stage4_series_identity_is_required_and_round_trips_to_output(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")

    result = module.calculate(payload, input_bytes=1024)

    assert result["series_identity"] == payload["series_identity"]
    missing = copy.deepcopy(payload)
    missing.pop("series_identity")
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(missing, input_bytes=1024)
    assert error.value.code == "missing_required_field"


@pytest.mark.parametrize("slug", SERIES_IDENTITY_SLUGS)
def test_stage4_user_input_accepts_business_series_identity_and_round_trips(slug):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    payload["data_contract"]["provider"] = "user_input"
    payload["dataset_refs"][0]["provider_id"] = "user_input"
    payload["source_hashes"] = {"user_input": payload["dataset_refs"][0]["sha256"]}
    payload["series_identity"] = copy.deepcopy(USER_INPUT_SERIES_IDENTITIES[slug])

    schema = json.loads(
        (SKILLS_ROOT / slug / "references/input-schema.json").read_text(encoding="utf-8")
    )
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
    result = module.calculate(payload, input_bytes=1024)

    assert result["series_identity"] == USER_INPUT_SERIES_IDENTITIES[slug]


@pytest.mark.parametrize(
    ("slug", "mutate"),
    (
        (
            "rate-ma-timing-research",
            lambda identity: identity.update(
                {
                    "asset_series": identity["rate_series"],
                    "rate_series": identity["asset_series"],
                }
            ),
        ),
        (
            "equity-risk-premium-timing",
            lambda identity: identity["index_series"].update({"identity": ""}),
        ),
        (
            "style-rotation-research",
            lambda identity: identity["style_b_series"].update(
                {"identity": identity["style_a_series"]["identity"]}
            ),
        ),
        (
            "style-rotation-research",
            lambda identity: identity["style_b_series"].update({"role": "style_a_index"}),
        ),
        (
            "rate-ma-timing-research",
            lambda identity: identity["rate_series"].update({"tenor": "2Y"}),
        ),
    ),
)
def test_stage4_user_input_rejects_wrong_role_identity_or_tenor(slug, mutate):
    module = load_calculator(slug)
    payload = load_json(slug, "input.json")
    payload["data_contract"]["provider"] = "user_input"
    payload["dataset_refs"][0]["provider_id"] = "user_input"
    payload["series_identity"] = copy.deepcopy(USER_INPUT_SERIES_IDENTITIES[slug])
    mutate(payload["series_identity"])

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)

    assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", SERIES_IDENTITY_SLUGS)
def test_stage4_series_identity_mapping_is_provider_aware_and_production_closed(slug):
    module = load_calculator(slug)
    mapping = json.loads(
        (SKILLS_ROOT / slug / "references/field-mapping.json").read_text(encoding="utf-8")
    )["runtime_contract"]
    identity_contract = mapping["series_identity"]

    assert identity_contract["descriptor_fields"] == ["role", "identity", "version", "tenor"]
    assert identity_contract["identity_pattern"] == module.SERIES_IDENTITY_PATTERN
    assert identity_contract["provider_rules"]["user_input"]["series"] == (
        module.SERIES_ROLE_CONTRACTS
    )
    assert (
        identity_contract["provider_rules"]["synthetic"]["series"]
        == load_json(slug, "input.json")["series_identity"]
    )
    for provider in ("datahub", "wind"):
        assert identity_contract["provider_rules"][provider]["mode"] == "exact_allowlist"
        assert identity_contract["provider_rules"][provider]["series"] == []

        payload = load_json(slug, "input.json")
        payload["data_contract"]["provider"] = provider
        payload["dataset_refs"][0]["provider_id"] = provider
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(payload, input_bytes=1024)
        assert error.value.code == "data_not_equivalent"


def test_rate_and_erp_reject_series_identity_version_and_tenor_mismatch():
    cases = (
        ("rate-ma-timing-research", "rate_series", "tenor", "2Y"),
        ("rate-ma-timing-research", "asset_series", "identity", "wrong_asset"),
        ("equity-risk-premium-timing", "bond_yield_series", "tenor", "2Y"),
        ("equity-risk-premium-timing", "index_series", "identity", "wrong_index"),
        ("equity-risk-premium-timing", "index_series", "version", "wrong_version"),
    )
    for slug, series, field, value in cases:
        module = load_calculator(slug)
        payload = load_json(slug, "input.json")
        payload["series_identity"][series][field] = value
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(payload, input_bytes=1024)
        assert error.value.code == "data_not_equivalent"


def test_style_rejects_swapped_duplicate_or_version_mismatched_series_identity():
    module = load_calculator("style-rotation-research")
    base = load_json("style-rotation-research", "input.json")

    swapped = copy.deepcopy(base)
    swapped["series_identity"]["style_a_series"], swapped["series_identity"]["style_b_series"] = (
        swapped["series_identity"]["style_b_series"],
        swapped["series_identity"]["style_a_series"],
    )
    duplicate = copy.deepcopy(base)
    duplicate["series_identity"]["style_b_series"] = copy.deepcopy(
        duplicate["series_identity"]["style_a_series"]
    )
    version_mismatch = copy.deepcopy(base)
    version_mismatch["series_identity"]["style_a_series"]["version"] = "wrong_version"

    for payload in (swapped, duplicate, version_mismatch):
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(payload, input_bytes=1024)
        assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_runtime_enforces_finite_numbers_and_explicit_partial_provenance(slug):
    module = load_calculator(slug)
    for value in (float("inf"), 10**400):
        invalid = copy.deepcopy(load_json(slug, "input.json"))
        invalid["records"][0][NUMERIC_FIELDS[slug]] = value
        with pytest.raises(module.CalculatorError) as error:
            module.calculate(invalid, input_bytes=1024)
        assert error.value.code == "invalid_number"
    missing = load_json(slug, "input.json")
    missing.pop("source_hashes")
    result = module.calculate(missing, input_bytes=1024)
    assert result["status"] == "partial"
    assert result["provenance"]["source_hashes"] == {}
    assert "source_hashes_missing" in result["limitations"]


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_insufficient_history_fails_closed(slug):
    module = load_calculator(slug)
    payload = copy.deepcopy(load_json(slug, "input.json"))
    payload["records"] = payload["records"][:2]
    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)
    assert error.value.code == "insufficient_history"


def test_stage4_explicit_ambiguous_rules_fail_closed():
    style = load_calculator("style-rotation-research")
    style_payload = load_json("style-rotation-research", "input.json")
    style_payload["parameters"]["method"] = "auto"
    with pytest.raises(style.CalculatorError) as error:
        style.calculate(style_payload, input_bytes=1024)
    assert error.value.code == "ambiguous_rule"

    chanlun = load_calculator("chanlun")
    plateau = load_json("chanlun", "input.json")
    plateau["records"][0]["high"] = plateau["records"][1]["high"]
    plateau["records"][0]["close"] = plateau["records"][0]["high"]
    with pytest.raises(chanlun.CalculatorError) as error:
        chanlun.calculate(plateau, input_bytes=1024)
    assert error.value.code == "ambiguous_structure"


def test_chanlun_dual_pivot_fails_closed_as_ambiguous_structure():
    module = load_calculator("chanlun")
    payload = load_json("chanlun", "input.json")
    payload["records"][3].update({"high": 12, "low": 7, "close": 9})

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)

    assert error.value.code == "ambiguous_structure"


def test_chanlun_too_close_reversal_fails_closed_as_ambiguous_structure():
    module = load_calculator("chanlun")
    payload = load_json("chanlun", "input.json")
    payload["parameters"]["minimum_separation_bars"] = 3

    with pytest.raises(module.CalculatorError) as error:
        module.calculate(payload, input_bytes=1024)

    assert error.value.code == "ambiguous_structure"


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_cli_is_strict_json_relative_safe_bounded_and_without_success_newline(
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


def test_stage4_packages_do_not_contain_absolute_paths_or_forbidden_execution_stacks():
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
        "openpyxl",
    }
    forbidden_tokens = ("cuda", "mps", "metal", "vba", "openpyxl")
    for slug in SLUGS:
        folder = SKILLS_ROOT / slug
        source = (folder / "scripts/calculate.py").read_text(encoding="utf-8")
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
        package_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in folder.rglob("*")
            if path.is_file() and path.suffix in {".md", ".json", ".py"}
        )
        lowered = package_text.lower()
        assert all(re.search(rf"\b{token}\b", lowered) is None for token in forbidden_tokens), slug
        assert all(
            re.search(rf"\b{token}\b", lowered) is None
            for token in ("socket", "requests", "urllib", "httpx", "cjpy")
        ), slug
        assert "http://" not in lowered
        assert lowered.count("https://") == 2
        assert lowered.count(OFFICIAL_JSON_SCHEMA_URI) == 2
        assert re.search(r"/(?:users|home)/[^/]+/", lowered) is None, slug
        assert re.search(r"[a-z]:\\\\(?:users|documents and settings)\\\\", lowered) is None, slug
        assert "load_relative_json" in source
        assert "allow_nan=False" in source


def test_all_five_regular_calculations_complete_under_two_seconds():
    started = time.monotonic()
    for slug in SLUGS:
        module = load_calculator(slug)
        payload = load_json(slug, "input.json")
        result = module.calculate(payload, input_bytes=len(json.dumps(payload).encode("utf-8")))
        assert result["skill_slug"] == slug
    assert time.monotonic() - started < 2


def test_stage4_synthetic_source_artifacts_are_real_and_bound_to_fixtures():
    for slug in SLUGS:
        artifact = SKILLS_ROOT / slug / "fixtures/source-artifact.json"
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
        if slug in SERIES_IDENTITY_SLUGS:
            source_artifact = json.loads(artifact.read_text(encoding="utf-8"))
            assert source_artifact["series_identity"] == payload["series_identity"]


def test_five_stage4_packages_are_discoverable_disabled_and_receipt_gated(tmp_path):
    seeded = dict(seed_packages())
    assert set(SLUGS) <= set(seeded)
    assert set(SLUGS) <= RECEIPT_GATED_SKILLS

    catalog = CapabilityCatalog(tmp_path)
    rows = {row["id"]: row for row in catalog.list(kind="skill")["items"]}
    assert len(rows) == 30
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


def test_stage4_additive_seed_migration_reinstalls_missing_builtins_disabled(tmp_path):
    root = tmp_path / "capabilities"
    root.mkdir()
    (root / "catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": {},
                "pending": None,
                "comparison_receipts": {
                    "rate-ma-timing-research:999": {
                        "schema_version": 2,
                        "skill_slug": "rate-ma-timing-research",
                        "version": 999,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    migrated = CapabilityCatalog(tmp_path)

    for slug in SLUGS:
        row = migrated.row(slug)
        assert row["source"] == "builtin"
        assert row["status"] == "disabled"
        assert migrated.comparison_receipt(slug) is None


def _version_script_digest(catalog: CapabilityCatalog, slug: str, version: int) -> str:
    files = catalog.row(slug)["versions"][str(version)]["files"]
    return next(item["sha256"] for item in files if item["path"] == "scripts/calculate.py")


def _write_comparison_evidence(tmp_path: Path, catalog: CapabilityCatalog, slug: str) -> Path:
    version = catalog.row(slug)["version"]
    evidence_dir = tmp_path / "comparison-evidence" / slug
    evidence_dir.mkdir(parents=True, exist_ok=True)
    expected = evidence_dir / "golden-result.json"
    actual = evidence_dir / "actual-result.json"
    synthetic_input = evidence_dir / "synthetic-input.json"
    actual_input = evidence_dir / "wind-excel-actual-input.json"
    shutil.copy2(SKILLS_ROOT / slug / "fixtures/golden-result.json", expected)
    shutil.copy2(expected, actual)
    shutil.copy2(SKILLS_ROOT / slug / "fixtures/source-artifact.json", synthetic_input)
    shutil.copy2(synthetic_input, actual_input)
    output = json.loads(actual.read_text(encoding="utf-8"))
    evidence = {
        "schema_version": 2,
        "skill_slug": slug,
        "version": version,
        "script_sha256": _version_script_digest(catalog, slug, version),
        "compared_at": "2026-09-16T00:00:00Z",
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
    return artifact


def _sign_comparison_evidence(artifact: Path) -> None:
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in evidence.items() if key != "registrar_signature"}
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    evidence["registrar_signature"] = hmac.new(
        bytes.fromhex(REGISTRAR_KEY_HEX), canonical, hashlib.sha256
    ).hexdigest()
    artifact.write_text(json.dumps(evidence), encoding="utf-8")


def test_stage4_plain_json_cannot_self_attest_a_comparison_receipt(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    for slug in SLUGS:
        artifact = _write_comparison_evidence(tmp_path, catalog, slug)
        with pytest.raises(CapabilityError) as error:
            catalog.record_comparison_receipt(artifact)
        assert error.value.code == "comparison_registrar_required"
        assert catalog.comparison_receipt(slug) is None


def test_stage4_forged_registrar_signature_cannot_enable(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_COMPARISON_REGISTRAR_KEY", REGISTRAR_KEY_HEX)
    catalog = CapabilityCatalog(tmp_path)
    artifact = _write_comparison_evidence(tmp_path, catalog, "rate-ma-timing-research")
    with pytest.raises(CapabilityError) as error:
        catalog.record_comparison_receipt(artifact)
    assert error.value.code == "invalid_comparison_evidence"
    assert catalog.comparison_receipt("rate-ma-timing-research") is None


def test_stage4_valid_receipt_is_bound_to_immutable_version(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_COMPARISON_REGISTRAR_KEY", REGISTRAR_KEY_HEX)
    slug = "rate-ma-timing-research"
    catalog = CapabilityCatalog(tmp_path)
    old_version = catalog.row(slug)["version"]
    artifact = _write_comparison_evidence(tmp_path, catalog, slug)
    _sign_comparison_evidence(artifact)
    old_receipt = catalog.record_comparison_receipt(artifact)
    catalog._require_comparison_receipt(slug, old_version)

    row = catalog.row(slug)
    row["draft"] = copy.deepcopy(dict(seed_packages())[slug])
    row["has_draft"] = True
    catalog.publish(slug, _allow_builtin_migration=True, _status="disabled")
    new_version = catalog.row(slug)["version"]

    assert new_version == old_version + 1
    assert catalog.comparison_receipt(slug, old_version) == old_receipt
    assert catalog.comparison_receipt(slug, new_version) is None
    with pytest.raises(CapabilityError) as error:
        catalog.transition(slug, "enable")
    assert error.value.code == "comparison_receipt_required"


def _stress_payload(slug: str) -> dict:
    payload = load_json(slug, "input.json")
    as_of = date.fromisoformat(payload["as_of"])
    count = 1_000 if slug == "platform-breakout" else 5_000
    days = [(as_of - timedelta(days=count - index - 1)).isoformat() for index in range(count)]
    if slug == "rate-ma-timing-research":
        payload["records"] = [
            {
                "date": day,
                "asset_close": 3_000 + index / 10,
                "rate_pct": 2.0 + index / 100_000,
            }
            for index, day in enumerate(days)
        ]
    elif slug == "equity-risk-premium-timing":
        payload["records"] = [
            {
                "date": day,
                "index_close": 3_000 + index / 10,
                "pe_ttm": 10 + (index % 100) / 100,
                "bond_yield_pct": 2.0 + (index % 50) / 1_000,
            }
            for index, day in enumerate(days)
        ]
    elif slug == "style-rotation-research":
        payload["records"] = [
            {
                "date": day,
                "style_a_close": 1_000 + index / 10,
                "style_b_close": 1_000 + index / 20,
            }
            for index, day in enumerate(days)
        ]
    elif slug == "chanlun":
        payload["records"] = [
            {
                "asset_id": "TEST.SH",
                "date": day,
                "high": 10 + index / 100,
                "low": 9 + index / 100,
                "close": 9.5 + index / 100,
            }
            for index, day in enumerate(days)
        ]
    else:
        payload["records"] = [
            {
                "asset_id": f"TEST-{symbol:02d}.SH",
                "date": day,
                "high": 10.0,
                "low": 9.0,
                "close": 9.5,
            }
            for symbol in range(50)
            for day in days
        ]
    return payload


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_over_limit_workloads_fail_with_stable_error(slug):
    module = load_calculator(slug)
    payload = _stress_payload(slug)
    payload["records"].append(copy.deepcopy(payload["records"][-1]))
    with pytest.raises(Exception) as error:
        module.calculate(payload, input_bytes=64 * 1024)
    assert getattr(error.value, "code", None) == "workload_too_large"
    assert error.value.metadata["reduce_scope"] is True


def _run_stage4_sandbox(payload: dict, slug: str, tmp_path: Path) -> tuple[dict, float, int]:
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
    assert supervisor["stderr"] == "", supervisor
    output_size = len(supervisor["stdout"].encode("utf-8")) + len(
        supervisor["stderr"].encode("utf-8")
    )
    assert output_size <= 64 * 1024
    result = json.loads(supervisor["stdout"])
    assert result["skill_slug"] == slug
    assert result["row_delivery"]["processed_input_rows"] == len(payload["records"])
    return result, elapsed, peak_rss_bytes


@pytest.mark.parametrize("slug", SLUGS)
def test_stage4_near_limit_process_stays_within_sandbox_time_rss_and_output(slug, tmp_path):
    result, elapsed, peak_rss_bytes = _run_stage4_sandbox(_stress_payload(slug), slug, tmp_path)
    assert result["status"] in {"complete", "partial"}
    assert elapsed < 10
    assert peak_rss_bytes < 1024 * 1024 * 1024
