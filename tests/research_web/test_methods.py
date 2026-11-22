import copy
import io
import json
import zipfile

import pytest
from pydantic import ValidationError

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.methods import (
    METHOD_IDS,
    MethodPolicy,
    evaluate_method_trace,
    resolve_methods,
)
from app.research_web.capabilities.models import CapabilityError, DraftInput


def test_builtin_methods_are_versioned_read_only_native_skills(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    rows = catalog.list("method")["items"]

    assert {row["id"] for row in rows} == set(METHOD_IDS)
    assert all(row["kind"] == "method" and row["builtin"] and row["version"] == 1 for row in rows)
    for row in rows:
        detail = catalog.detail(row["id"])
        spec = detail["draft"]["method_spec"]
        assert spec["method_id"] == row["id"]
        assert spec["version"] == "1.0.0"
        assert detail["draft"]["files"] == []
        assert detail["metadata"]["required_tools"] == []
        native = catalog.native_root / row["id"] / "SKILL.md"
        text = native.read_text(encoding="utf-8")
        assert "kind=method" in text
        assert "rwb_record_method_use" in text
        with zipfile.ZipFile(io.BytesIO(catalog.export(row["id"], 1))) as archive:
            assert "kind=method" in archive.read("SKILL.md").decode()
            assert json.loads(archive.read("method.json"))["method_id"] == row["id"]
        with pytest.raises(CapabilityError, match="只能复制"):
            catalog.edit(row["id"], detail["draft"])


def test_method_copy_is_an_ordinary_skill_without_rewriting_history(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    cid = "fact-checking"
    original = copy.deepcopy(catalog.row(cid))
    native = (catalog.native_root / cid / "SKILL.md").read_bytes()
    copied = catalog.copy(cid, "事实核验副本", "fact-checking-copy")
    assert copied["kind"] == "skill"
    assert copied["version"] is None
    assert copied["origin"] == {"capability_id": cid, "version": 1}
    assert not copied["draft"].get("method_spec")
    instructions = copied["draft"]["instructions"]
    spec = original["versions"]["1"]["method_spec"]
    for field in (
        "triggers",
        "anti_triggers",
        "input_contract",
        "output_contract",
        "procedure",
        "evaluation_rubric",
    ):
        assert all(item in instructions for item in spec[field])
    assert "rwb_record_method_use" not in instructions
    assert "kind=method" not in instructions
    assert copied["metadata"]["required_tools"] == []
    assert catalog.check(copied["id"])["valid"]
    catalog.publish(copied["id"])
    assert catalog.detail(copied["id"])["version"] == 1
    assert catalog.row(cid) == original
    assert (catalog.native_root / cid / "SKILL.md").read_bytes() == native


@pytest.mark.parametrize(
    "field,value",
    [
        ("instructions", "unreviewed instruction"),
        ("files", [{"path": "x.py"}]),
        ("required_tools", ["shell"]),
    ],
)
def test_method_copy_rejects_invalid_source_without_partial_creation(tmp_path, field, value):
    catalog = CapabilityCatalog(tmp_path)
    source = catalog.row("fact-checking")["versions"]["1"]
    target = source["metadata"] if field == "required_tools" else source
    target[field] = value
    before = set(catalog.data["items"])
    with pytest.raises(CapabilityError):
        catalog.copy("fact-checking", "副本", "fact-checking-copy")
    assert set(catalog.data["items"]) == before


def test_users_cannot_create_or_import_method_contracts():
    with pytest.raises(ValidationError):
        DraftInput.model_validate({"kind": "method"})


def test_method_resolution_priority_conflicts_limits_and_versions(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    policy = MethodPolicy(
        required=["fact-checking"],
        recommended=["first-principles"],
        excluded=["reverse-engineering"],
    )
    selected = resolve_methods(
        catalog,
        policy,
        user_selected=["dual-layer-explanation"],
        model_supplemented=[],
    )
    assert [(item["method_id"], item["source"]) for item in selected] == [
        ("fact-checking", "required"),
        ("dual-layer-explanation", "user-selected"),
        ("first-principles", "recommended"),
    ]

    with pytest.raises(CapabilityError, match="排除"):
        resolve_methods(catalog, policy, user_selected=["reverse-engineering"])
    with pytest.raises(CapabilityError, match="最多组合三个"):
        resolve_methods(
            catalog,
            MethodPolicy(required=["fact-checking", "first-principles"]),
            user_selected=["dual-layer-explanation", "minimal-experiment"],
        )
    catalog.data["items"]["fact-checking"]["versions"]["1"]["method_spec"][
        "incompatible_methods"
    ] = ["first-principles"]
    with pytest.raises(CapabilityError, match="冲突"):
        resolve_methods(
            catalog,
            MethodPolicy(required=["fact-checking"]),
            user_selected=["first-principles"],
        )
    catalog.transition("fact-checking", "disable")
    with pytest.raises(CapabilityError, match="不可用"):
        resolve_methods(catalog, MethodPolicy(required=["fact-checking"]))


def test_method_trace_blocks_required_and_degrades_recommended():
    methods = [
        {"method_id": "fact-checking", "version": "1.0.0", "source": "required"},
        {"method_id": "first-principles", "version": "1.0.0", "source": "recommended"},
    ]
    blocked = evaluate_method_trace(methods, [])
    assert blocked["completion_blocked"] is True
    assert blocked["missing_required"] == ["fact-checking"]

    degraded = evaluate_method_trace(
        methods,
        [{"method_id": "fact-checking", "version": "1.0.0", "source": "required"}],
    )
    assert degraded["completion_blocked"] is False
    assert degraded["method_trace_incomplete"] is True
    assert degraded["missing_optional"] == ["first-principles"]


def test_method_eval_matrix_has_three_samples_and_three_variants_per_method():
    from app.research_web.capabilities.methods import (
        evaluation_matrix,
        promotion_decision,
    )

    matrix = evaluation_matrix()
    assert set(matrix) == set(METHOD_IDS)
    assert all(len(cases) >= 9 for cases in matrix.values())
    assert all(
        {case["variant"] for case in cases} >= {"baseline", "single", "combined"}
        for cases in matrix.values()
    )
    assert (
        promotion_decision(
            baseline_quality=3,
            method_quality=4,
            baseline_cost=10,
            method_cost=10.5,
            baseline_latency=20,
            method_latency=21,
        )["promote"]
        is True
    )
    assert (
        promotion_decision(
            baseline_quality=3,
            method_quality=4,
            baseline_cost=10,
            method_cost=12,
            baseline_latency=20,
            method_latency=21,
        )["promote"]
        is False
    )
