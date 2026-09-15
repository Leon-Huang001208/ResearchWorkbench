"""Offline contracts and deterministic goldens for CPU quant Skills stage 2."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from contextlib import chdir, redirect_stderr, redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pytest
import yaml

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError
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
    assert len(rows) == 18
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
        assert refs_schema["items"]["additionalProperties"] is False
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
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert input_path.stat().st_size < 8 * 1024 * 1024
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SKILLS_ROOT / "_shared")
    output_path = tmp_path / "output.json"
    error_path = tmp_path / "error.log"
    started = time.monotonic()
    with (
        output_path.open("w", encoding="utf-8") as output,
        error_path.open("w", encoding="utf-8") as errors,
    ):
        process = subprocess.Popen(
            [sys.executable, str(SKILLS_ROOT / slug / "scripts/calculate.py"), input_path.name],
            cwd=tmp_path,
            env=environment,
            stdout=output,
            stderr=errors,
            text=True,
        )
        peak_rss_kib = 0
        while process.poll() is None:
            rss = subprocess.run(
                ["/bin/ps", "-o", "rss=", "-p", str(process.pid)],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,
            ).stdout.strip()
            if rss:
                peak_rss_kib = max(peak_rss_kib, int(rss))
            if time.monotonic() - started >= 10:
                process.kill()
                pytest.fail(f"{slug} exceeded 10 seconds")
            time.sleep(0.01)
        process.wait(timeout=1)
    elapsed = time.monotonic() - started
    assert process.returncode == 0, error_path.read_text(encoding="utf-8")
    assert json.loads(output_path.read_text(encoding="utf-8"))["skill_slug"] == slug
    assert elapsed < 10
    assert 0 < peak_rss_kib < 1024 * 1024


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
