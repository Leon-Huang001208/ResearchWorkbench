"""Three fixed owned-method scenarios alongside the original frozen eight."""

from __future__ import annotations

from core.observability import get_logger

from ..capabilities.scenario_method_packages import METHODS
from .catalog import _validate_inputs
from .models import ScenarioError

log = get_logger(__name__)


def contracts():
    return [
        {
            "id": cid,
            "version": "1.0.0",
            "name": title,
            "description": description,
            "source_selection_kind": "owned-method",
            "capability_ids": [cid],
            "subject_kinds": (
                ["stock"] if cid != "owned-news-evidence" else ["stock", "industry", "topic"]
            ),
            "required_inputs": ["subject", "as_of", "question", "material_ids"],
            "optional_inputs": [],
            "required_data": [],
            "materials_required": True,
            "steps": [
                "重开已选原件并核验来源身份、版本与截止",
                "实际执行固定原件检查并交付缺口台账",
                "唯一DSH依据已核材料叙事并运行原报告质量检查",
            ],
            "coverage": ["原件引用与覆盖", "口径和来源缺口", "事实与条件解释"],
            "expected_artifacts": ["method-source-ledger", "research-report.json"],
            "missing_data_behavior": "缺资料保持incomplete，完整性或权限错误保持invalid；不自动补抓或重跑。",
            "examples": [
                {
                    "subject": {"kind": "stock", "identity": "MSFT.US"},
                    "as_of": "2026-10-27",
                    "question": "核验已取得原件并说明缺口",
                    "material_ids": [],
                }
            ],
        }
        for cid, (title, _action, description) in METHODS.items()
    ]


def select(service, scenario_id, values):
    from ..scenario_handoffs import capability_facts

    contract = next((row for row in contracts() if row["id"] == scenario_id), None)
    if contract is None:
        log.warning("research_method_scenario_unknown")
        raise ScenarioError("scenario_unknown")
    values = _validate_inputs(contract, values)
    capabilities = capability_facts(service, contract)
    missing = [
        {"code": "capability_unavailable", "id": row["id"]}
        for row in capabilities
        if not row.get("available")
    ]
    if not values["material_ids"]:
        missing.append({"code": "materials_missing", "id": "material_ids"})
    return {
        "scenario_id": scenario_id,
        "version": contract["version"],
        "contract": contract,
        "inputs": values,
        "capabilities": capabilities,
        "missing": missing,
        "eligible_for_draft": not missing,
        "status": "ready_for_draft" if not missing else "incomplete",
        "auto_send": False,
        "frozen": False,
        "send_authorized": False,
        "runtime_verified": False,
        "quality_passed": False,
    }
