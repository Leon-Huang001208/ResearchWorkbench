"""Independent actual operand gates preserve generic report arithmetic."""

import copy
import json

import pytest
import test_owned_method_execution as fixtures
from test_api import isolated_keyring  # noqa: F401
from test_report_calculations import observation, recipe

from app.research_web.resources.research_report_calculations import derive_business_observations
from app.research_web.resources.research_report_plan import (
    _summary_calculation,
    write_business_report_plan,
)
from app.research_web.scenario_method_sources import company_calculation_policy

POLICY = "owned-company-positive-base-v1"
api = fixtures.api


@pytest.mark.parametrize("base", ["0", "-10"])
def test_owned_nonpositive_base_is_rejected_after_primitive_resolution(base):
    rows = [
        observation("total_revenue", "2024", "20"),
        observation("total_revenue", "2023", base, source="b"),
    ]
    with pytest.raises(ValueError, match="owned_percent_change_nonpositive_base"):
        derive_business_observations(rows, [recipe(rows)], task_id="t", calculation_policy=POLICY)


def test_positive_owned_and_generic_negative_keep_original_math():
    positive = [
        observation("total_revenue", "2024", "245122"),
        observation("total_revenue", "2023", "211915", source="b"),
    ]
    assert (
        derive_business_observations(
            positive, [recipe(positive)], task_id="t", calculation_policy=POLICY
        )[0]["value"]
        == "15.67"
    )
    negative = [
        observation("total_revenue", "2024", "20"),
        observation("total_revenue", "2023", "-10", source="b"),
    ]
    assert (
        derive_business_observations(negative, [recipe(negative)], task_id="t")[0]["value"]
        == "-300.00"
    )


@pytest.mark.parametrize("base", ["0", "-10"])
def test_summary_direct_nonpositive_base_and_abs_step_are_rejected(base):
    rows = [
        observation("total_revenue", "2024", "20"),
        observation("total_revenue", "2023", base, source="b"),
    ]
    direct = [
        {"id": "growth", "operation": "percent_change", "operands": [row["id"] for row in rows]}
    ]
    with pytest.raises(ValueError, match="owned_percent_change_nonpositive_base"):
        _summary_calculation(
            {"observations": rows}, rows[0], direct, [0], {}, calculation_policy=POLICY
        )
    steps = [
        {"id": "washed", "operation": "abs", "operands": [rows[1]["id"]]},
        {"id": "growth", "operation": "percent_change", "operands": [rows[0]["id"], "$washed"]},
    ]
    with pytest.raises(ValueError, match="owned_percent_change_derived_base_unsupported"):
        _summary_calculation(
            {"observations": rows}, rows[0], steps, [0], {}, calculation_policy=POLICY
        )


def test_host_frozen_company_policy_rejects_sdk_policy_deletion_and_handwritten_canonical(
    api, monkeypatch
):
    # Synthetic negative captured body: never reported as the official fixture SHA.
    client, service, sid, _context, _descriptor, headers, _source = fixtures.prepared(
        api,
        monkeypatch,
        "owned-company-evidence",
        transform=lambda raw: raw.replace(b"| 211,915 |", b"| (211,915) |"),
    )
    receipt, _ = service._task_capabilities(sid)
    contract = receipt["research_contract"]
    policy = company_calculation_policy(service.store, sid, contract)
    assert policy == POLICY
    root = service.store.directory(sid)
    bundle = json.loads((root / "resources/research_evidence.json").read_bytes())
    revenues = {
        row["period"]: row for row in bundle["observations"] if row["metric"] == "total_revenue"
    }
    assert revenues["2023"]["value"] == "-211915"
    rows = [revenues["2024"], revenues["2023"]]
    report_context = {
        "task_id": contract["task_id"],
        "contract_sha256": contract["sha256"],
        "as_of": contract["as_of"],
        "requirement_ids": [row["id"] for row in contract["requirements"]],
        "formats": ["html"],
    }
    plan = {
        "title": "原件限定核验",
        "calculations": [recipe(rows)],
        "sections": [
            {
                "id": "income",
                "heading": "已取得材料",
                "evidence_ids": [row["id"] for row in rows] + ["$nominal_growth"],
                "requirement_ids": [contract["requirements"][0]["id"]],
                "analysis": "仅作已取得原件比较：{{formula:$nominal_growth}}。",
            }
        ],
        "missing": ["其余材料缺失。"],
    }
    monkeypatch.chdir(root)
    with pytest.raises(ValueError, match="owned_percent_change_nonpositive_base"):
        write_business_report_plan({**report_context, "calculation_policy": policy}, plan)
    # A caller omitting the SDK policy can produce generic arithmetic, but the
    # independently rebuilt Host policy must reject those original operands.
    write_business_report_plan(report_context, plan)
    result = client.post(
        "/api/research/internal/data/research-quality", json={"session_id": sid}, headers=headers
    )
    assert result.status_code == 200 and result.json()["status"] == "invalid", result.text
    assert "report_invalid" in result.json()["issues"]
    canonical = root / "outputs/research-report.json"
    payload = json.loads(canonical.read_bytes())
    payload.pop("system_plan")
    canonical.write_text(json.dumps(payload))
    result = client.post(
        "/api/research/internal/data/research-quality", json={"session_id": sid}, headers=headers
    )
    assert result.status_code == 200 and result.json()["status"] == "invalid", result.text
    changed = copy.deepcopy(contract)
    changed["execution_context"]["context_sha256"] = "0" * 64
    with pytest.raises(Exception, match="方法来源"):
        company_calculation_policy(service.store, sid, changed)
