"""Report revision must work inside the original kernel sandbox and retain lineage."""

import hashlib
import json
import os
import shutil
import sys
from decimal import Decimal
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest
from test_research_quality import example, saved_report

from app.research_web.research_evidence import report_projection
from app.research_web.resources.research_report import archive_report_version, write_research_report
from app.research_web.store import Store


def test_failed_fomc_parent_references_are_deduplicated_without_certifying_text():
    from app.research_web.resources.research_report import evidence_section

    ref = "file:" + "a" * 24
    block = evidence_section(
        "r1_range", "Decision", "unverified interpretation", [ref, ref], ["r1"]
    )
    assert block["sections"][0]["citations"] == [ref]
    assert block["notes"][0]["citations"] == [ref]
    assert block["numeric_claims"] == []
    with pytest.raises(ValueError, match="observation"):
        evidence_section("s", "Decision", "text", ["business_" + "b" * 32], ["r1"])


def test_summary_writer_replays_actual_msft_values_with_real_empty_separator(tmp_path):
    from openpyxl import load_workbook

    from app.research_web.resources.research_report import numeric_summary, write_summary_workbook

    metrics = {
        "revenue_growth_pct": Decimal("15.66996201307127857867541231"),
        "fcf_2024_usd_mn": 74071,
        "fcf_capital_return_ratio_2024": Decimal("1.898039718129404228058936579"),
    }
    path = tmp_path / "summary.xlsx"
    write_summary_workbook(
        path,
        metrics,
        decimal_places={"revenue_growth_pct": 2, "fcf_capital_return_ratio_2024": 3},
        sheets={
            "Facts": [["metric", "source_ref"], ["fcf", ["file:" + "a" * 24]]],
            "Notes": [["description"], ["=not a formula"]],
        },
    )
    book = load_workbook(path, read_only=True, data_only=False)
    assert list(book["Summary"].values)[4] == (None, None)
    numeric_summary(
        book["Summary"].values,
        {
            "revenue_growth_pct": 15.67,
            "fcf_2024_usd_mn": 74071,
            "fcf_capital_return_ratio_2024": 1.898,
        },
    )
    assert json.loads(book["Facts"]["B2"].value) == ["file:" + "a" * 24]
    assert book["Notes"]["A2"].data_type != "f"
    book.close()
    before = path.read_bytes()
    with pytest.raises(ValueError):
        write_summary_workbook(path, {"x": float("nan")})
    assert path.read_bytes() == before
    for value in (Decimal("1.00000000000000001"), Decimal("0.12345678901234560000001")):
        with pytest.raises(ValueError):
            write_summary_workbook(path, {"x": value})
        assert path.read_bytes() == before


def test_exact_slash_joined_sources_still_reject_foreign_or_guessed_ids():
    from app.research_web.resources.research_report import source_references

    first, second = "file:" + "a" * 24, "file:" + "b" * 24
    sources = [{"id": first, "title": "july.md"}, {"id": second, "title": "september.md"}]
    assert source_references(first + " / " + second, sources) == [first, second]
    for bad in [
        first + "/file:filename",
        first + "/file:" + "c" * 24,
        first + "/comment/" + second,
    ]:
        with pytest.raises(ValueError):
            source_references(bad, sources)


def test_markdown_renderer_preserves_canonical_text_and_missing():
    from app.research_web.resources.research_report import render_markdown

    _, payload, _ = example()
    payload["missing"] = ["A real unsupported analysis remains missing"]
    rendered = render_markdown(payload)
    assert payload["missing"][0] in rendered
    assert all(section["text"] in rendered for section in payload["sections"])


def test_decimal_rate_arguments_retain_exact_financial_arithmetic():
    from app.research_web.resources.research_report import rate_difference

    assert rate_difference(Decimal("5.25"), Decimal("4.75"))["basis_points"] == "50.00"
    with pytest.raises(ValueError):
        rate_difference(Decimal("NaN"), Decimal("4.75"))


def test_decimal_claim_operands_remain_exact_json_data():
    from app.research_web.resources.research_report import build_numeric_claim

    row = {
        "observation_id": "file:" + "a" * 24,
        "quote": "2024 Revenue 2 count",
        "value": Decimal(2),
        "period": "2024",
        "unit": "count",
    }
    claim = build_numeric_claim(
        "claim", "section", row["quote"], "2024", "count", "identity", [row]
    )
    assert json.loads(json.dumps(claim))["operands"][0]["value"] == "2"


def test_source_reference_locator_requires_actual_host_identity_and_title():
    from app.research_web.resources.research_report import source_references

    sources = [{"id": "file:" + "a" * 24, "title": "owned-controls.md"}]
    identity = sources[0]["id"]
    assert source_references(identity + " · owned-controls.md · 第1段 Govern 1.1", sources) == [
        identity
    ]
    assert source_references(identity, sources) == [identity]
    for value in [
        "file:owned-controls.md",
        identity + " · different.md · 第1段",
        identity + " · owned-controls.md · file:" + "b" * 24,
        identity + " file:" + "b" * 24,
    ]:
        with pytest.raises(ValueError):
            source_references(value, sources)


def test_relative_archive_does_not_require_getcwd(tmp_path, monkeypatch):
    output = tmp_path / "outputs"
    output.mkdir()
    saved_report(output)
    monkeypatch.chdir(tmp_path)

    def denied():
        raise PermissionError("getcwd is denied by the original native sandbox")

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "getcwd", denied)
        version = archive_report_version(Path("outputs"))
    assert len(version["files"]) == 4
    for row in version["files"]:
        path = output / version["directory"] / row["stored_name"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert not list((output / "report-versions").glob(".pending-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="requires the original macOS kernel sandbox")
def test_second_write_archives_actual_report_in_original_native_sandbox(tmp_path):
    from app.research_web.sandbox import SandboxConfig, run_script

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "native revision")["id"]
    directory = store.directory(sid)
    resources = Path(__file__).parents[2] / "app/research_web/resources"
    shutil.copytree(resources, directory / "resources", dirs_exist_ok=True)
    _, payload, _ = example()
    code = (
        "import json\n"
        "from research_report import write_research_report, list_report_versions\n"
        f"payload = {payload!r}\n"
        "first = write_research_report('outputs', payload)\n"
        "original = first['json'].read_bytes()\n"
        "payload['title'] = '修订后的风险说明'\n"
        "second = write_research_report('outputs', payload)\n"
        "versions = list_report_versions('outputs')\n"
        "assert len(versions) == 1\n"
        "assert versions[0]['report']['title'] == '风险说明'\n"
        "assert json.loads(second['json'].read_text())['title'] == '修订后的风险说明'\n"
        "print('NATIVE_REPORT_REVISION_OK')\n"
    )
    result = run_script(SandboxConfig(store.root, Path(sys.executable)), directory, code)
    assert result.status == "completed", result.stderr
    assert "NATIVE_REPORT_REVISION_OK" in result.stdout
    assert not list((directory / "outputs/report-versions").glob(".pending-*"))


def projection_case(tmp_path):
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "canonical report")["id"]
    contract, payload, sources = example()
    output = store.directory(sid) / "outputs"
    paths = write_research_report(output, payload)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**row, "valid": True} for row in manifest["artifacts"]]}
    backup = output / "diagnostic-backup"
    backup.mkdir()
    shutil.copyfile(paths["json"], backup / "research-report.json")
    return store, sid, contract, sources, delivery, paths


def project(store, sid, contract, sources, delivery, files=None):
    return report_projection(
        store,
        sid,
        store.files(sid) if files is None else files,
        sources,
        contract["task_id"],
        delivery,
        contract=contract,
    )


def test_backup_report_name_cannot_make_current_canonical_report_ambiguous(tmp_path):
    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    result = project(store, sid, contract, sources, delivery)
    assert result["quality"] == "passed", result


def test_nested_report_without_current_canonical_report_remains_invalid(tmp_path):
    store, sid, contract, sources, delivery, paths = projection_case(tmp_path)
    paths["json"].unlink()
    result = project(store, sid, contract, sources, delivery)
    assert result["quality"] == "invalid"
    assert "report_identity_noncanonical" in result["issues"]


def test_duplicate_canonical_identity_still_fails_closed(tmp_path):
    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    files = store.files(sid)
    canonical = next(
        file
        for file in files
        if store.session(sid)["files"][file["id"]] == str(Path("outputs") / "research-report.json")
    )
    result = project(store, sid, contract, sources, delivery, [*files, canonical])
    assert result["quality"] == "invalid"
    assert "report_identity_ambiguous" in result["issues"]


@pytest.mark.parametrize(
    "relative,status",
    [
        ("outputs\\research-report.json", "passed"),
        ("outputs\\..\\outputs\\research-report.json", "invalid"),
    ],
)
def test_windows_path_selector_requires_exact_native_mapping(
    tmp_path, monkeypatch, relative, status
):
    import app.research_web.research_evidence as evidence

    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    files = store.files(sid)
    row = store.session(sid)
    mapped = {fid: path.replace("/", "\\") for fid, path in row["files"].items()}
    canonical = next(fid for fid, path in mapped.items() if path == "outputs\\research-report.json")
    mapped[canonical] = relative
    windows_store = SimpleNamespace(
        session=lambda requested: {**store.session(requested), "files": mapped},
        open_file=store.open_file,
    )
    monkeypatch.setattr(evidence, "Path", PureWindowsPath)
    result = project(windows_store, sid, contract, sources, delivery, files)
    assert result["quality"] == status


def test_business_source_identity_uses_host_id_not_uploaded_name():
    from app.research_web.resources.research_report import canonical_source

    sources = [{"id": "file:abc", "title": "f614-nist-controls.md", "sha256": "a" * 64}]
    assert canonical_source(sources, "f614-nist-controls.md") == {
        "id": "file:abc",
        "title": "f614-nist-controls.md",
    }
    with pytest.raises(ValueError):
        canonical_source(sources, "file:f614-nist-controls.md")
    with pytest.raises(ValueError):
        canonical_source(
            sources + [{"id": "file:other", "title": sources[0]["title"]}], sources[0]["title"]
        )


def test_business_evidence_section_retains_all_note_sources_and_requirements():
    from app.research_web.resources.research_report import evidence_section

    blocks = evidence_section(
        "future", "政策限制", "未来取决于实际数据。", ["file:july", "file:sep"], ["r4"]
    )
    assert blocks["notes"][0]["citations"] == ["file:july", "file:sep"]
    assert blocks["coverage"][0]["excerpt"] == blocks["sections"][0]["text"]
    assert set(blocks) == {"sections", "notes", "coverage", "numeric_claims"}
    assert blocks["numeric_claims"] == []


def test_business_numeric_claim_rejects_previous_bad_arities_and_count():
    from app.research_web.resources.research_report import build_numeric_claim

    row = {
        "observation_id": "file:abc",
        "value": "1",
        "period": "input",
        "unit": "count",
        "quote": "input 1 count",
    }
    for operation, operands, text in [
        ("identity", [row, row], "input Count 1 count"),
        ("ratio", [row] * 4, "input Count 1 ratio"),
        ("sum", [row], "input Count 8 count"),
        ("identity", [{**row, "period": "invented"}], "invented Count 1 count"),
    ]:
        with pytest.raises(ValueError):
            build_numeric_claim("count", "s1", text, "input", "count", operation, operands)


def test_business_numeric_claim_calculates_exact_value_and_preserves_gate():
    from test_research_quality import numeric_example

    from app.research_web.research_quality import assess_quality
    from app.research_web.resources.research_report import build_numeric_claim

    contract, payload, sources, observations = numeric_example()
    prior = payload["numeric_claims"][0]
    claim = build_numeric_claim(
        prior["id"],
        prior["section_id"],
        prior["text"],
        prior["period"],
        prior["unit"],
        prior["operation"],
        prior["operands"],
    )
    payload["numeric_claims"] = [claim]
    assert assess_quality(contract, payload, sources, observations)["status"] == "passed"
    observations[0]["content"] = "不同内容"
    observations[0]["sha256"] = hashlib.sha256("不同内容".encode()).hexdigest()
    assert assess_quality(contract, payload, sources, observations)["status"] != "passed"


def test_business_rate_and_cashflow_math_are_explicit():
    from app.research_web.resources.research_report import rate_difference, reconcile_amounts

    assert rate_difference("5.50", "5.00") == {"percentage_points": "0.50", "basis_points": "50.00"}
    result = reconcile_amounts("-37757", ["294", "-2907", "-17254", "-21771", "3881"])
    assert result["component_sum"] == "-37757"
    assert result["difference"] == "0"
    assert reconcile_amounts("10", ["3", "6"])["difference"] == "1"
    with pytest.raises(ValueError):
        rate_difference(True, "1")


def test_business_summary_accepts_explicit_rounding_and_padded_nulls_only():
    from app.research_web.resources.research_report import numeric_summary

    rows = [
        ("metric", "value", None, None),
        ("growth", 15.67, None, None),
        (None,) * 4,
        ("growth", "notes", "unit", "period"),
    ]
    assert numeric_summary(rows, {"growth": "15.66996201307127"}, decimal_places={"growth": 2}) == {
        "growth": 15.67
    }
    assert (
        numeric_summary(
            [("metric", "value"), ("growth", 15.66996201307127)],
            {"growth": "15.66996201307127"},
            decimal_places={"growth": 2},
        )["growth"]
        == 15.66996201307127
    )
    for bad_rows in [
        [("metric", "value"), ("growth", 15.68)],
        [("metric", "value"), ("growth", 15.67), ("growth", 15.67)],
        [("metric", "value"), ("growth", "=15.67")],
        [("metric", "value"), ("growth", "15.67")],
        [("metric", "value"), ("growth", True)],
        [("metric", "value"), ("growth", float("nan"))],
        [("metric", "value"), (None, None), ("growth", 15.67)],
        [("metric", "value"), ("growth", 15.67, "unexpected")],
    ]:
        with pytest.raises(ValueError):
            numeric_summary(bad_rows, {"growth": "15.66996201307127"}, decimal_places={"growth": 2})
    with pytest.raises(ValueError):
        numeric_summary(rows, {"growth": "15.66996201307127"})


def test_business_exact_math_does_not_hide_low_order_reconciliation_gap():
    from decimal import Context, Decimal, localcontext

    from app.research_web.resources.research_report import rate_difference, reconcile_amounts

    tiny = "1." + "0" * 110 + "1e-100"
    result = reconcile_amounts("1e100", ["1e100", tiny, "-1e-100"])
    assert Decimal(result["difference"]) == Decimal("-1e-211")
    with localcontext(Context(prec=512)):
        expected = Decimal("1e100") - Decimal(tiny)
    assert Decimal(rate_difference("1e100", tiny)["percentage_points"]) == expected


@pytest.mark.parametrize("heading,text", [("h" * 201, "text"), ("heading", "t" * 10001)])
def test_business_section_never_builds_an_invalid_coverage_excerpt(heading, text):
    from app.research_web.resources.research_report import evidence_section

    with pytest.raises(ValueError):
        evidence_section("s1", heading, text, ["file:abc"], ["r1"])
