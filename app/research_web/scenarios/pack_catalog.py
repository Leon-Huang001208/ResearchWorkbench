"""Additional pack contracts; the original eight frozen contracts stay intact."""

from ..capabilities.pack_resources import PACK_NAMES
from .catalog import _validate_inputs
from .packs import PACKS, REQUIRED_COVERAGE
from .packs.contracts import PackError, encoded


def contracts():
    return [
        {
            "id": "pack-" + pack_id,
            "version": "1.0.0",
            "name": title,
            "description": "受控确定性后端；完整来源、参数界面和研究质量另行验收",
            "pack_id": pack_id,
            "capability_ids": ["research-pack-" + pack_id],
            "subject_kinds": (
                ["stock", "industry", "topic"]
                if pack_id in {"research-prep", "global-opinion"}
                else ["stock"]
            ),
            "required_inputs": ["subject", "question", "as_of", "material_ids"],
            "optional_inputs": ["research_scope"],
            "materials_required": True,
            "examples": [
                {
                    "subject": {"kind": "stock", "identity": "600600.SH"},
                    "as_of": "2026-10-27",
                    "question": title + "：核验已选材料并保留来源缺口",
                    "material_ids": [],
                }
            ],
            "required_data": list(REQUIRED_COVERAGE[pack_id]),
            "steps": [
                "核对本人原件、来源权限、时区、单位与完整覆盖。",
                "通过受控原生脚本执行冻结版本：" + "、".join(PACKS[pack_id]),
                "重新读取真实结果文件，分别登记保存、计算缺口和研究质量。",
            ],
            "coverage": ["限定确定性计算；来源完整性独立核验", "旧18算法回执门保持"],
            "expected_artifacts": [
                "full-result.json",
                "receipt.json",
                "manifest.json",
                "来源与缺口台账",
            ],
            "missing_data_behavior": "缺数、未知时点或权限不足保持partial/blocked；不补造、付费重取或自动发送。",
        }
        for pack_id, title in PACK_NAMES.items()
    ]


def select(service, scenario_id, values):
    from ..scenario_handoffs import capability_facts, fail

    contract = next((row for row in contracts() if row["id"] == scenario_id), None)
    if contract is None:
        fail("scenario_unknown", "研究组合包不存在", 404)

    def bounded(value, depth=0):
        if depth > 16:
            fail("pack_scope_invalid", "研究参数嵌套过深", 422)
        if isinstance(value, dict):
            for item in value.values():
                bounded(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                bounded(item, depth + 1)

    bounded(values)
    try:
        encoded(values)
    except PackError:
        fail("pack_scope_invalid", "研究参数无效或超过输入预算", 422)
    checked = _validate_inputs(contract, values)
    capabilities = capability_facts(service, contract)
    missing = [
        {"code": "source_qualification_required", "id": key} for key in contract["required_data"]
    ]
    return {
        "scenario_id": scenario_id,
        "version": contract["version"],
        "contract": contract,
        "inputs": checked,
        "capabilities": capabilities,
        "missing": missing,
        "eligible_for_draft": False,
        "status": "incomplete",
        "auto_send": False,
        "frozen": False,
        "send_authorized": False,
        "runtime_verified": False,
        "quality_passed": False,
    }
