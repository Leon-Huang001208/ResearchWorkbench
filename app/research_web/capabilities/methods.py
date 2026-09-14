"""Read-only research reasoning methods, routing policy, and observable trace checks."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from .models import CapabilityError, MethodPolicy

log = get_logger(__name__)


class ReasoningMethodSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    triggers: list[str] = Field(min_length=1, max_length=20)
    anti_triggers: list[str] = Field(min_length=1, max_length=20)
    input_contract: list[str] = Field(min_length=1, max_length=20)
    output_contract: list[str] = Field(min_length=1, max_length=20)
    procedure: list[str] = Field(min_length=2, max_length=20)
    compatible_methods: list[str] = Field(default_factory=list, max_length=20)
    incompatible_methods: list[str] = Field(default_factory=list, max_length=20)
    evaluation_rubric: list[str] = Field(min_length=1, max_length=20)


_METHOD_ROWS = (
    (
        "socratic-clarification",
        "苏格拉底澄清",
        "目标、概念或约束含混且答案会随定义变化",
        "需求明确或只需执行确定步骤",
        ["列出关键歧义", "逐项提出最小澄清问题", "确认可检验的任务边界"],
        ["歧义是否显式", "问题是否改变决策"],
    ),
    (
        "dual-layer-explanation",
        "双层解释",
        "需要同时服务快速决策与深入复核",
        "只要求单一粒度的简短答复",
        ["先给决策层结论", "再给证据与机制层解释", "对齐两层口径"],
        ["结论与证据是否一致", "层次是否可独立阅读"],
    ),
    (
        "reverse-engineering",
        "逆向拆解",
        "需要从优秀案例、结果或系统反推形成机制",
        "只有结果标签而没有可观察材料",
        ["界定目标结果", "拆出结构与关键选择", "验证因果而非模仿表象"],
        ["决定变量是否明确", "可迁移机制是否有证据"],
    ),
    (
        "horizontal-vertical-analysis",
        "横纵分析",
        "需要跨对象比较并追踪同一对象的时间变化",
        "只有单一对象单一时点",
        ["统一横向口径", "建立纵向时间线", "解释交叉差异与断点"],
        ["比较口径是否一致", "时序断点是否解释"],
    ),
    (
        "fact-checking",
        "事实核查",
        "关键事实、数字、时序或来源会影响结论",
        "纯创意任务且不含事实主张",
        ["拆分可核查主张", "区分一手与二手来源", "记录支持、反证和未决项"],
        ["来源区分", "反证覆盖", "时点与口径"],
    ),
    (
        "expert-perspectives",
        "专家视角",
        "复杂问题需要多个专业约束共同判断",
        "专业边界单一且结论直接",
        ["选择互补专家角色", "分别给出判断与盲点", "综合冲突而不投票平均"],
        ["视角是否互补", "冲突是否被处理"],
    ),
    (
        "first-principles",
        "第一性原理",
        "惯例或类比不可靠，需要从约束和基本事实重建",
        "成熟标准流程已足够",
        ["剥离惯例假设", "列出不可约束事实", "从约束重建候选解释"],
        ["基础假设是否显式", "推导链是否可检验"],
    ),
    (
        "cross-domain-transfer",
        "跨域迁移",
        "另一个领域存在可映射的成熟机制",
        "类比只提供修辞而无结构对应",
        ["抽取源领域机制", "建立结构映射", "标出迁移失效条件"],
        ["映射是否逐项", "失效条件是否明确"],
    ),
    (
        "steelman-comparison",
        "钢人比较",
        "需要公平比较竞争观点、方案或投资叙事",
        "只有一个候选且无需反方检验",
        ["为各方构造最强论证", "统一评价维度", "找出决定胜负的证据"],
        ["反方是否被钢人化", "决定变量是否可观察"],
    ),
    (
        "minimal-experiment",
        "最小实验",
        "高不确定判断可通过低成本试验降低风险",
        "无法定义观测或行动不可逆",
        ["定义最小可证伪假设", "限定样本、成本与停止条件", "预先规定读数与下一步"],
        ["实验条件", "停止条件", "决策阈值"],
    ),
)

METHOD_SPECS = tuple(
    ReasoningMethodSpec(
        method_id=method_id,
        version="1.0.0",
        title=title,
        description=trigger,
        triggers=[trigger],
        anti_triggers=[anti_trigger],
        input_contract=["研究问题", "已知事实与约束"],
        output_contract=["采用的方法步骤", "可观察结果与未决项"],
        procedure=procedure,
        compatible_methods=[],
        incompatible_methods=[],
        evaluation_rubric=rubric,
    )
    for method_id, title, trigger, anti_trigger, procedure, rubric in _METHOD_ROWS
)
METHOD_IDS = tuple(spec.method_id for spec in METHOD_SPECS)


def resolve_methods(catalog, policy=None, user_selected=(), model_supplemented=()):
    """Resolve required > user > recommended > model without silent truncation."""

    policy = (
        policy if isinstance(policy, MethodPolicy) else MethodPolicy.model_validate(policy or {})
    )
    groups = (
        ("required", policy.required),
        ("user-selected", list(user_selected)),
        ("recommended", policy.recommended),
        ("model-supplemented", list(model_supplemented)),
    )
    excluded, selected, seen = set(policy.excluded), [], set()
    for source, method_ids in groups:
        for method_id in method_ids:
            if method_id in excluded:
                if source in {"required", "user-selected"}:
                    raise CapabilityError("所选方法被当前能力策略排除", "method_excluded", 409)
                continue
            if method_id in seen:
                continue
            try:
                selection = catalog.selection(method_id)
            except CapabilityError as exc:
                raise CapabilityError("方法版本不可用", "method_unavailable", 409) from exc
            if selection["kind"] != "method":
                raise CapabilityError("引用的能力不是方法", "method_unavailable", 409)
            spec = catalog.row(method_id)["versions"][str(selection["version"])]["method_spec"]
            selected.append(
                {
                    "method_id": method_id,
                    "version": spec["version"],
                    "title": spec["title"],
                    "source": source,
                    "native_name": selection["native_name"],
                    "capability_version": selection["version"],
                }
            )
            seen.add(method_id)
    if len(selected) > 3:
        raise CapabilityError("自动或手动最多组合三个方法", "method_limit_exceeded", 409)
    selected_ids = {item["method_id"] for item in selected}
    for item in selected:
        spec = catalog.row(item["method_id"])["versions"][str(item["capability_version"])][
            "method_spec"
        ]
        if selected_ids & set(spec.get("incompatible_methods", [])):
            raise CapabilityError("方法组合存在冲突", "method_conflict", 409)
    log.info("research_methods_resolved", method_count=len(selected))
    return selected


def evaluate_method_trace(selected, evidence):
    observed = {
        (item.get("method_id"), item.get("version"), item.get("source")) for item in evidence
    }
    missing_required, missing_optional = [], []
    for item in selected:
        if (item["method_id"], item["version"], item["source"]) in observed:
            continue
        target = (
            missing_required
            if item["source"] in {"required", "user-selected"}
            else missing_optional
        )
        target.append(item["method_id"])
    return {
        "completion_blocked": bool(missing_required),
        "method_trace_incomplete": bool(missing_optional),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "evidence": list(evidence),
    }


def read_method_trace(session_root: Path):
    path = session_root / ".rwb" / "method-trace.jsonl"
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise CapabilityError("方法记录文件不可安全读取", "method_trace_unavailable", 503)
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if (
                set(value) != {"method_id", "version", "source"}
                or value["method_id"] not in METHOD_IDS
                or value["source"]
                not in {"required", "user-selected", "recommended", "model-supplemented"}
            ):
                raise ValueError("invalid method trace")
            rows.append(value)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        log.error("research_method_trace_unreadable", error_type=type(exc).__name__)
        raise CapabilityError("方法记录文件不可核对", "method_trace_unavailable", 503) from exc
    return rows


def evaluation_matrix():
    scenarios = ("来源冲突的公司业绩判断", "产业链瓶颈与受益方比较", "陌生领域低成本验证")
    return {
        method_id: [
            {
                "scenario": scenario,
                "variant": variant,
                "observable_only": True,
                "rubric": next(
                    spec.evaluation_rubric for spec in METHOD_SPECS if spec.method_id == method_id
                ),
            }
            for scenario in scenarios
            for variant in ("baseline", "single", "combined")
        ]
        for method_id in METHOD_IDS
    }


def promotion_decision(
    *,
    baseline_quality,
    method_quality,
    baseline_cost,
    method_cost,
    baseline_latency,
    method_latency,
):
    values = (
        baseline_quality,
        method_quality,
        baseline_cost,
        method_cost,
        baseline_latency,
        method_latency,
    )
    if any(not isinstance(value, (int, float)) or value < 0 for value in values):
        raise CapabilityError("方法评测指标无效", "method_eval_invalid")
    improved = method_quality > baseline_quality
    cost_ok = method_cost <= baseline_cost * 1.1
    latency_ok = method_latency <= baseline_latency * 1.1
    return {
        "promote": improved and cost_ok and latency_ok,
        "quality_improved": improved,
        "cost_ok": cost_ok,
        "latency_ok": latency_ok,
    }
