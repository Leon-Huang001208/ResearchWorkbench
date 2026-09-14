"""Offline contracts and deterministic goldens for CPU quant Skills stage 2."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import time
from contextlib import chdir, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest
import yaml

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.seeds import seed_packages
from app.research_web.skills._shared import cpu_budget as cpu_budget_module
from app.research_web.skills._shared.cpu_budget import MAX_INPUT_BYTES, WorkloadTooLarge

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
    sys.path.insert(0, str(path.parent))
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
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


def test_six_unique_builtin_packages_are_admitted_and_selectable(tmp_path):
    seeded = dict(seed_packages())
    assert len(seeded) == len(seed_packages())
    assert set(SLUGS) <= set(seeded)

    catalog = CapabilityCatalog(tmp_path)
    rows = {row["id"]: row for row in catalog.list(kind="skill")["items"]}
    assert len(rows) == 18
    for slug in SLUGS:
        row = rows[slug]
        assert row["source"] == "builtin"
        assert row["status"] == "enabled"
        assert row["metadata"]["required_tools"] == REQUIRED_TOOLS[slug]
        assert catalog.selection(slug)["id"] == slug
        detail = catalog.detail(slug)
        header = yaml.safe_load(detail["draft"]["instructions"].split("---", 2)[1])
        assert header["name"] == slug
        assert detail["checks"]["valid"] is True
        assert detail["checks"]["issues"] == []


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
        assert set(input_schema["properties"]["dataset_refs"]["items"]["required"]) == {
            "dataset_id",
            "provider_id",
            "as_of",
            "sha256",
        }
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
    assert_close(actual, expected)
    assert actual["skill_slug"] == slug
    assert actual["compute_profile"] == "cpu_bounded_v1"
    assert actual["protocol"] == "cpu_bounded_v1"
    assert actual["research_only"] is True
    assert actual["status"] in {"complete", "partial", "insufficient_data"}
    assert isinstance(actual["limitations"], list)
    assert isinstance(actual["dataset_refs"], list) and actual["dataset_refs"]


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
            if path.is_file():
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
