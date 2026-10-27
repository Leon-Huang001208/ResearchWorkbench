"""Additional pack contracts; the original eight frozen contracts stay intact."""

from ..capabilities.pack_resources import PACK_NAMES
from .catalog import _validate_inputs
from .packs import METHODS, PACKS, REQUIRED_COVERAGE
from .packs.contracts import PackError, encoded


def ui_methods(pack_id):
    """Read-only form projection; never adds source or execution authority."""
    labels = {
        "validate_positions": "持仓范围核对",
        "join_risk_windows": "风险窗口关联（完整覆盖仍由来源核验）",
        "deduplicate_source_versions": "原件版本去重",
        "compare_qualified_expectations": "同口径预期比较",
        "compare_valuation_samples": "同口径估值样本比较",
        "align_event_trading_day": "事件与交易日对齐",
        "sentiment_counts": "舆情分层计数",
        "disclosed_ownership": "已披露持有人比较",
        "earnings_calendar": "财报日历核对",
    }
    fields = {
        "expected_universe": ("研究证券范围", "securities"),
        "positions": ("风险关联证券范围", "securities"),
        "target_weight": ("目标总权重（比例，1代表100%）", "number"),
        "window_start": ("比较窗口起点", "instant"),
        "window_end": ("比较窗口终点", "instant"),
        "current_row_id": ("当前估值样本原件行ID", "text"),
        "minimum_samples": ("最少历史样本数", "integer"),
        "release_at": ("事件发布时间", "instant"),
        "pre_sessions": ("前置交易日数", "integer"),
        "post_sessions": ("后置交易日数", "integer"),
        "adjustment": ("价格复权口径", "adjustment"),
        "report_periods": ("比较报告期（逗号分隔，如2025FY,2026Q1）", "periods"),
        "report_period": ("目标报告期，如2026Q3", "text"),
    }
    result = []
    for method in PACKS[pack_id]:
        projected = []
        for key in sorted(METHODS[method][2] - {"category_coverage"}):
            label, kind = fields[key]
            if method == "join_risk_windows" and key.startswith("window_"):
                kind = "date"
            field = {"name": key, "label": label, "type": kind, "required": True}
            if kind in {"number", "integer"}:
                field["min"] = 1 if key == "minimum_samples" else 0
                if key in {"pre_sessions", "post_sessions"}:
                    field["max"] = 5000
            projected.append(field)
        result.append(
            {
                "id": method,
                "label": labels[method],
                "version": "1.0.0",
                "required_kinds": sorted(METHODS[method][1]),
                "fields": projected,
                "source_requirements": sorted(METHODS[method][2] & {"category_coverage"}),
            }
        )
    return result


def contracts():
    return [
        {
            "id": "pack-" + pack_id,
            "version": "1.0.0",
            "name": title,
            "description": "受控确定性后端；完整来源、参数界面和研究质量另行验收",
            "pack_id": pack_id,
            "ui_methods": ui_methods(pack_id),
            "ui_limits": "只读预览不执行模型或供应商；预览行最多128，完整结果以实际文件回执为准。",
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
