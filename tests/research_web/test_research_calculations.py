"""Independent full-input checks do not trust model arithmetic or declared observations."""

import hashlib
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research_web.research_calculations import CalculationError, observe_calculations
from app.research_web.research_evidence import evidence_index
from app.research_web.research_quality import assess_quality, make_contract
from app.research_web.research_quality_service import source_context
from app.research_web.store import Store


def calculation_case(tmp_path, raw=None):
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "计算验收")["id"]
    raw = raw or b"minute,asset_a,asset_b\n0,100,100\n1,110,95\n2,90,105\n3,120,110\n4,115,125\n"
    (store.directory(sid) / "inputs" / "trusted-prices.csv").write_bytes(raw)
    files = store.files(sid)
    sources = evidence_index(files, [], [])
    recipe = {
        "id": "portfolio",
        "source_id": sources[0]["id"],
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "operation": "buy_and_hold",
        "weights": {"asset_a": "0.6", "asset_b": "0.4"},
        "terminal_shocks": {"asset_a": "-0.1", "asset_b": "0.05"},
    }
    return store, sid, files, sources, recipe


def test_independently_recomputes_series_drawdown_and_terminal_scenario(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    actual = observe_calculations(store, sid, files, sources, [recipe])
    values = {row["metric"]: row["value"] for row in actual}
    assert values == {
        "total_return": "0.1900000000",
        "max_drawdown": "-0.0769230769",
        "terminal_scenario_return": "0.1460000000",
        "row_count": "5",
    }
    assert all(
        row["source_id"] == sources[0]["id"] and row["input_sha256"] == recipe["source_sha256"]
        for row in actual
    )
    assert all(
        hashlib.sha256(row["content"].encode()).hexdigest() == row["sha256"] for row in actual
    )


def test_reads_the_complete_fifty_thousand_rows_not_the_preview(tmp_path):
    raw = b"minute,asset_a,asset_b\n" + b"0,100,100\n" * 49999 + b"49999,80,120\n"
    store, sid, files, sources, recipe = calculation_case(tmp_path, raw)
    actual = {
        r["metric"]: r["value"] for r in observe_calculations(store, sid, files, sources, [recipe])
    }
    assert actual["row_count"] == "50000"
    assert actual["total_return"] == "-0.0400000000"
    assert actual["max_drawdown"] == "-0.0400000000"
    assert actual["terminal_scenario_return"] == "-0.0640000000"


def test_mutation_after_cached_calculation_requires_the_new_full_digest(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    observe_calculations(store, sid, files, sources, [recipe])
    path = store.file_path(sid, files[0]["id"])
    path.write_bytes(path.read_bytes() + b"5,1,1\n")
    with pytest.raises(CalculationError, match="calculation_input_changed"):
        observe_calculations(store, sid, files, sources, [recipe])
    recipe["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    values = {
        r["metric"]: r["value"] for r in observe_calculations(store, sid, files, sources, [recipe])
    }
    assert values["row_count"] == "6"
    assert values["total_return"] == "-0.9900000000"


@pytest.mark.parametrize(
    "change",
    [
        "unknown_source",
        "other_session",
        "bad_weight",
        "nan",
        "zero",
        "duplicate_header",
        "unknown_column",
        "bad_shock",
        "unsupported",
        "too_many",
    ],
)
def test_rejects_unowned_or_unsupported_calculations(tmp_path, change):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    if change == "unknown_source":
        recipe["source_id"] = "file:" + "a" * 24
    elif change == "other_session":
        sid = store.create("fingpt", "other")["id"]
    elif change == "bad_weight":
        recipe["weights"]["asset_a"] = "0.5"
    elif change in {"nan", "zero", "duplicate_header"}:
        raw = {
            "nan": b"asset_a,asset_b\nNaN,100\n",
            "zero": b"asset_a,asset_b\n0,100\n",
            "duplicate_header": b"asset_a,asset_a,asset_b\n100,100,100\n",
        }[change]
        store.file_path(sid, files[0]["id"]).write_bytes(raw)
        recipe["source_sha256"] = hashlib.sha256(raw).hexdigest()
    elif change == "unknown_column":
        recipe["weights"] = {"arbitrary": "1"}
    elif change == "bad_shock":
        recipe["terminal_shocks"]["asset_a"] = "-2"
    elif change == "unsupported":
        recipe["operation"] = "eval"
    elif change == "too_many":
        recipe["weights"] = {str(i): "0.1" for i in range(9)}
    with pytest.raises((CalculationError, ValueError)):
        observe_calculations(store, sid, files, sources, [recipe])


def test_host_observations_use_existing_strict_claim_lineage_and_identity_gate(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    observed = observe_calculations(store, sid, files, sources, [recipe])
    item = next(row for row in observed if row["metric"] == "max_drawdown")
    quote = item["content"].splitlines()[0]
    contract = make_contract("a" * 24, "计算最大回撤", ["最大回撤"], "2026-10-18", "quick")
    source_id = sources[0]["id"]
    report = {
        "task_id": "a" * 24,
        "title": "计算结果",
        "as_of": "2026-10-18",
        "calculations": [recipe],
        "sections": [{"id": "result", "heading": "回撤", "text": quote, "citations": [source_id]}],
        "sources": [{"id": source_id, "title": sources[0]["title"]}],
        "notes": [{"stage_id": "result", "text": quote, "citations": [source_id]}],
        "coverage": [{"requirement_id": "r1", "section_ids": ["result"], "excerpt": quote}],
        "numeric_claims": [
            {
                "id": "n1",
                "section_id": "result",
                "text": quote,
                "value": item["value"],
                "period": item["period"],
                "unit": item["unit"],
                "operation": "identity",
                "operands": [
                    {
                        "observation_id": item["id"],
                        "value": item["value"],
                        "quote": quote,
                        "period": item["period"],
                        "unit": item["unit"],
                    }
                ],
            }
        ],
    }
    assert assess_quality(contract, report, sources, observed)["status"] == "passed"
    report["sources"][0]["title"] = "model invented friendly alias"
    assert assess_quality(contract, report, sources, observed)["status"] == "invalid"
    report["sources"][0]["title"] = sources[0]["title"]
    report["numeric_claims"][0]["value"] = "0.9"
    assert assess_quality(contract, report, sources, observed)["status"] == "incomplete"
    report["numeric_claims"][0]["value"] = item["value"]
    report["notes"] = []
    assert assess_quality(contract, report, sources, observed)["status"] == "incomplete"


def test_canonical_source_context_exposes_actual_owned_identity_and_digest(tmp_path):
    store, sid, files, sources, _ = calculation_case(tmp_path)
    context = source_context(SimpleNamespace(store=store), sid, files)
    assert context["sources"][0]["id"] == sources[0]["id"]
    assert context["sources"][0]["title"] == files[0]["name"]
    assert (
        context["sources"][0]["sha256"]
        == hashlib.sha256(store.file_path(sid, files[0]["id"]).read_bytes()).hexdigest()
    )
    assert "content" not in context["sources"][0]


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "1e999999", "0." + "1" * 80])
def test_non_finite_boolean_or_extreme_recipe_numbers_are_rejected(tmp_path, value):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    recipe["weights"]["asset_a"] = value
    with pytest.raises(CalculationError):
        observe_calculations(store, sid, files, sources, [recipe])


def test_recipe_unknown_fields_are_not_executable_extensions(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path)
    recipe["path"] = "/outside/the/session"
    with pytest.raises(CalculationError):
        observe_calculations(store, sid, files, sources, [recipe])


def test_full_digest_is_distinct_from_a_truncated_preview_digest(tmp_path):
    raw = b"minute,asset_a,asset_b\n" + b"0,100,100\n" * 50000
    store, sid, files, sources, recipe = calculation_case(tmp_path, raw)
    recipe["source_sha256"] = hashlib.sha256(raw[:12000]).hexdigest()
    with pytest.raises(CalculationError, match="calculation_input_changed"):
        observe_calculations(store, sid, files, sources, [recipe])


def test_observation_and_cache_identity_is_scoped_to_user_root_session_and_task(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path / "alice")
    first = observe_calculations(store, sid, files, sources, [recipe], task_id="a" * 24)
    next_task = observe_calculations(store, sid, files, sources, [recipe], task_id="b" * 24)
    other, other_sid, other_files, other_sources, other_recipe = calculation_case(tmp_path / "bob")
    other_user = observe_calculations(
        other, other_sid, other_files, other_sources, [other_recipe], task_id="a" * 24
    )
    assert first[0]["value"] == other_user[0]["value"]
    assert len({first[0]["id"], next_task[0]["id"], other_user[0]["id"]}) == 3


def test_row_and_byte_budgets_are_hard_limits(tmp_path, monkeypatch):
    from app.research_web import research_calculations

    store, sid, files, sources, recipe = calculation_case(tmp_path)
    monkeypatch.setattr(research_calculations, "MAX_ROWS", 4)
    with pytest.raises(CalculationError, match="calculation_row_limit"):
        observe_calculations(store, sid, files, sources, [recipe])
    monkeypatch.setattr(research_calculations, "MAX_INPUT_BYTES", 4)
    with pytest.raises(CalculationError, match="calculation_input_limit"):
        observe_calculations(store, sid, files, sources, [recipe])


def test_malformed_utf8_and_missing_csv_cells_are_rejected(tmp_path):
    for i, raw in enumerate((b"asset_a,asset_b\n100,\xff\n", b"asset_a,asset_b\n100\n")):
        store, sid, files, sources, recipe = calculation_case(tmp_path / str(i), raw)
        with pytest.raises(CalculationError):
            observe_calculations(store, sid, files, sources, [recipe])


def test_report_cannot_supply_its_own_calculation_observations(tmp_path):
    from app.research_web.research_evidence import report_projection

    store, sid, files, sources, recipe = calculation_case(tmp_path)
    contract = make_contract("a" * 24, "计算", ["收益"], "2026-10-18", "quick")
    payload = {
        "task_id": contract["task_id"],
        "title": "draft",
        "as_of": contract["as_of"],
        "sections": [
            {"id": "result", "heading": "结果", "text": "待核验", "citations": [sources[0]["id"]]}
        ],
        "sources": [{"id": sources[0]["id"], "title": sources[0]["title"]}],
        "calculations": [recipe],
        "calculation_observations": [{"value": "999999"}],
    }
    (store.directory(sid) / "outputs/research-report.json").write_text(json.dumps(payload))
    actual = report_projection(
        store, sid, store.files(sid), sources, contract["task_id"], contract=contract
    )
    assert actual["assessment"]["status"] == "incomplete"
    assert actual["calculation_observations"][0]["value"] == "0.1900000000"
    assert len(actual["calculation_observations"]) == 4
    store.file_path(sid, files[0]["id"]).write_text("asset_a,asset_b\n1,1\n")
    changed = report_projection(
        store, sid, store.files(sid), sources, contract["task_id"], contract=contract
    )
    assert changed["assessment"]["status"] == "invalid"
    assert changed["assessment"]["issues"] == ["calculation_input_changed"]


def test_unclosed_csv_quote_is_not_a_verified_partial_parse(tmp_path):
    store, sid, files, sources, recipe = calculation_case(tmp_path, b'asset_a,asset_b\n"100,100')
    with pytest.raises(CalculationError, match="calculation_data_invalid"):
        observe_calculations(store, sid, files, sources, [recipe])


def test_canonical_weight_order_has_identical_results_and_cache_identity(tmp_path):
    raw = b"a,b,c,d\n1000000000000000000,500000000000000000,1000000000000000000,1000000000000000000\n1000000000000000000,500000000100000000,0.00000000000000012,0.00000000000000012\n"
    store, sid, files, sources, recipe = calculation_case(tmp_path, raw)
    recipe.update(weights={name: "0.25" for name in ("a", "b", "c", "d")}, terminal_shocks={})
    first = observe_calculations(store, sid, files, sources, [recipe])
    recipe["weights"] = {name: "0.25" for name in ("c", "d", "a", "b")}
    second = observe_calculations(store, sid, files, sources, [recipe])
    assert first == second
    assert {r["metric"]: r["value"] for r in first}["total_return"] == "-0.5000000000"
    # A cold-cache computation also uses the same declared canonical column order.
    from app.research_web.research_calculations import _calculate

    assert _calculate(raw, recipe)["total_return"] == "-0.5000000000"


def assembled_case(tmp_path):
    from app.research_web.resources.research_report import calculation_evidence

    store, sid, files, sources, recipe = calculation_case(tmp_path)
    contract = make_contract(
        "a" * 24, "计算", ["收益", "回撤", "情景", "方法"], "2026-10-18", "quick"
    )
    observed = observe_calculations(
        store, sid, files, sources, [recipe], task_id=contract["task_id"]
    )
    blocks = calculation_evidence(
        observed,
        {"total_return": ["r1"], "max_drawdown": ["r2"], "terminal_scenario_return": ["r3"]},
        methods_requirement_ids=["r4"],
    )
    assert set(blocks) == {"sections", "notes", "numeric_claims", "coverage"}
    report = {
        "task_id": contract["task_id"],
        "title": "计算报告",
        "as_of": contract["as_of"],
        "sources": [{"id": sources[0]["id"], "title": sources[0]["title"]}],
        "calculations": [recipe],
        "missing": [],
        **blocks,
    }
    return contract, report, sources, observed


def test_assembler_keeps_each_claim_in_its_actual_section_and_verifies_all_metrics(tmp_path):
    contract, report, sources, observed = assembled_case(tmp_path)
    assert len(report["numeric_claims"]) == 4
    assert len(report["sections"]) == 5
    for claim, row in zip(report["numeric_claims"], observed, strict=True):
        section = next(s for s in report["sections"] if s["id"] == claim["section_id"])
        assert claim["text"] == section["text"] == row["content"].splitlines()[0]
        assert claim["operands"][0]["quote"] == claim["text"]
    assert assess_quality(contract, report, sources, observed)["status"] == "passed"


@pytest.mark.parametrize("corruption", ["value", "quote", "id", "missing", "coverage", "section"])
def test_assembler_never_certifies_untrusted_or_unfinished_evidence(tmp_path, corruption):
    contract, report, sources, observed = assembled_case(tmp_path)
    if corruption == "value":
        report["numeric_claims"][0]["value"] = "99"
    elif corruption == "quote":
        report["numeric_claims"][0]["operands"][0]["quote"] += " 改写"
    elif corruption == "id":
        report["numeric_claims"][0]["operands"][0]["observation_id"] = "calc_forged"
    elif corruption == "missing":
        report["missing"] = ["仍有未完成事项"]
    elif corruption == "coverage":
        report["coverage"] = [r for r in report["coverage"] if r["requirement_id"] != "r4"]
    else:
        report["sections"][0]["text"] = "模型未放入实际引用"
    assert assess_quality(contract, report, sources, observed)["status"] != "passed"


def test_assembler_cannot_make_foreign_observations_trusted(tmp_path):
    from app.research_web.resources.research_report import calculation_evidence

    contract, report, sources, observed = assembled_case(tmp_path)
    foreign = deepcopy(observed)
    for row in foreign:
        row["id"] = row["id"].replace("calc_", "calc_foreign_")
    report.update(
        calculation_evidence(foreign, {"total_return": ["r1"]}, methods_requirement_ids=["r4"])
    )
    assert assess_quality(contract, report, sources, observed)["status"] != "passed"


@pytest.mark.parametrize(
    "bad", ["duplicate", "missing_metric", "mixed_scope", "no_method", "bad_requirements"]
)
def test_assembler_rejects_ambiguous_or_incomplete_inputs(tmp_path, bad):
    from app.research_web.resources.research_report import calculation_evidence

    _, _, _, observed = assembled_case(tmp_path)
    mapping = {"total_return": ["r1"]}
    if bad == "duplicate":
        observed.append(deepcopy(observed[0]))
    elif bad == "missing_metric":
        observed.pop()
    elif bad == "mixed_scope":
        observed[0]["recipe_sha256"] = "0" * 64
    elif bad == "no_method":
        observed[0]["content"] = observed[0]["content"].splitlines()[0]
    else:
        mapping = {"unknown_metric": ["r1"]}
    with pytest.raises(ValueError, match="research_calculation_evidence_invalid"):
        calculation_evidence(observed, mapping, methods_requirement_ids=["r4"])


@pytest.mark.skipif(sys.platform != "darwin", reason="requires the original macOS kernel sandbox")
def test_assembler_writes_actual_native_artifacts_with_unchanged_quality_gate(tmp_path):
    from app.research_web.sandbox import SandboxConfig, run_script

    contract, report, sources, observed = assembled_case(tmp_path / "expected")
    store = Store(tmp_path / "native")
    sid = store.create("fingpt", "证据格式原生验收")["id"]
    directory = store.directory(sid)
    shutil.copytree(
        Path(__file__).parents[2] / "app/research_web/resources", directory / "resources"
    )
    code = (
        "from research_report import calculation_evidence, write_research_report\n"
        f"payload = {report!r}\n"
        f"actual = {observed!r}\n"
        "payload.update(calculation_evidence(actual, {'total_return':['r1'], 'max_drawdown':['r2'], 'terminal_scenario_return':['r3']}, methods_requirement_ids=['r4']))\n"
        "paths = write_research_report('outputs', payload)\n"
        "assert all(p.stat().st_size > 0 for p in paths.values())\n"
        "print('NATIVE_EVIDENCE_ASSEMBLY_OK')\n"
    )
    result = run_script(SandboxConfig(store.root, Path(sys.executable)), directory, code)
    assert result.status == "completed", result.stderr
    assert "NATIVE_EVIDENCE_ASSEMBLY_OK" in result.stdout
    actual = json.loads((directory / "outputs/research-report.json").read_text())
    # The sandbox serializer has no authority: the original Host verifies actual observations.
    assert assess_quality(contract, actual, sources, observed)["status"] == "passed"
    actual["missing"] = ["真实未完成事项"]
    assert assess_quality(contract, actual, sources, observed)["status"] == "incomplete"
