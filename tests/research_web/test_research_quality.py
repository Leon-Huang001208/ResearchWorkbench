"""Frozen Host requirements, observed evidence and immutable report versions."""

import copy
import hashlib
import json

import pytest

from app.research_web.research_quality import assess_quality, make_contract
from app.research_web.resources.research_report import (
    archive_report_version,
    list_report_versions,
    validate_payload,
)


def example():
    contract = make_contract("a" * 24, "核查风险", ["风险"], "2026-10-16", "deep")
    report = {
        "task_id": "a" * 24,
        "title": "风险说明",
        "as_of": "2026-10-16",
        "sections": [
            {
                "id": "risk",
                "heading": "风险",
                "text": "存在经营不确定性。",
                "citations": ["file:abc"],
            }
        ],
        "sources": [{"id": "file:abc", "title": "经营资料"}],
        "notes": [
            {"stage_id": "risk", "text": "经营资料说明不确定性。", "citations": ["file:abc"]}
        ],
        "coverage": [
            {"requirement_id": "r1", "section_ids": ["risk"], "excerpt": "存在经营不确定性。"}
        ],
    }
    sources = [{"id": "file:abc", "title": "经营资料", "content": "存在经营不确定性。"}]
    return contract, report, sources


def test_contract_copies_requirements_and_detects_later_tampering():
    requirements = [{"id": "risk", "text": "风险"}]
    contract = make_contract("a" * 24, "问题", requirements, "2026-10-16", "agent")
    requirements[0]["text"] = "缩减要求"
    assert contract["requirements"][0]["text"] == "风险"
    _, report, sources = example()
    contract["requirements"].clear()
    assert assess_quality(contract, report, sources)["status"] == "invalid"


def test_model_required_sections_cannot_drop_host_requirement():
    contract, report, sources = example()
    contract = make_contract("a" * 24, "核查风险及估值", ["风险", "估值"], "2026-10-16", "deep")
    report["required_sections"] = ["风险"]
    assessment = assess_quality(contract, report, sources)
    assert assessment["status"] == "incomplete"
    assert assessment["coverage"][1]["status"] == "missing"
    assert "requirement_uncovered:r2" in assessment["issues"]


def test_observed_source_with_note_lineage_can_pass_non_numeric_report():
    contract, report, sources = example()
    assert assess_quality(contract, report, sources)["status"] == "passed"


def test_contradictory_or_unobserved_qualitative_findings_remain_unverified():
    contract, report, sources = example()
    sources[0]["content"] = "经营亏损且存在风险。"
    report["sections"][0]["text"] = "经营盈利且完全没有风险。"
    report["coverage"][0]["excerpt"] = report["sections"][0]["text"]
    assessment = assess_quality(contract, report, sources)
    assert assessment["status"] == "incomplete"
    assert "narrative_unverified:风险" in assessment["issues"]


def test_observed_quote_cannot_drop_source_negation():
    contract, report, sources = example()
    sources[0]["content"] = "不能认定存在经营不确定性。"
    assert assess_quality(contract, report, sources)["status"] == "incomplete"


def test_requirement_heading_without_explicit_evidence_does_not_satisfy_coverage():
    contract, report, sources = example()
    report.pop("coverage", None)
    assessment = assess_quality(contract, report, sources)
    assert assessment["status"] == "incomplete"
    assert assessment["coverage"][0]["status"] == "missing"


def test_actual_host_file_observations_reach_projection_and_verify_numeric_claim(tmp_path):
    from types import SimpleNamespace

    from app.research_web.research_evidence import evidence_index, report_projection
    from app.research_web.research_quality_service import observations
    from app.research_web.resources.research_report import write_research_report
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "实际观测链")["id"]
    contract, report, _, fixture_observations = numeric_example()
    (store.directory(sid) / "inputs" / "revenue.txt").write_text(fixture_observations[0]["content"])
    sources = evidence_index(store.files(sid), [], [])
    source = sources[0]
    report["sources"] = [{"id": source["id"], "title": source["title"]}]
    report["sections"][0]["citations"] = [source["id"]]
    report["notes"][0]["citations"] = [source["id"]]
    report["coverage"] = [
        {"requirement_id": "r1", "section_ids": ["risk"], "excerpt": report["sections"][0]["text"]}
    ]
    for operand in report["numeric_claims"][0]["operands"]:
        operand["observation_id"] = source["id"]
    paths = write_research_report(store.directory(sid) / "outputs", report)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**row, "valid": True} for row in manifest["artifacts"]]}
    actual = observations(SimpleNamespace(store=store), sid, store.files(sid), sources)
    assert actual[0]["id"].startswith("file:")
    projected = report_projection(
        store,
        sid,
        store.files(sid),
        sources,
        contract["task_id"],
        delivery,
        contract=contract,
        observations=actual,
    )
    assert projected["quality"] == "passed"


def test_actual_host_dataset_observation_identifier_is_accepted(tmp_path):
    from types import SimpleNamespace

    from app.research_web.research_quality_service import observations

    contract, report, _ = example()
    source = {"id": "dataset:snapshot_abc", "title": "经营资料"}
    report["sources"][0]["id"] = source["id"]
    report["sections"][0]["citations"] = [source["id"]]
    report["notes"][0]["citations"] = [source["id"]]
    snapshots = SimpleNamespace(
        detail=lambda sid, did: {"id": did},
        read=lambda sid, did, name: json.dumps({"quote": "存在经营不确定性。"}).encode(),
    )
    actual = observations(
        SimpleNamespace(datahub=SimpleNamespace(snapshots=snapshots)), "sid", [], [source]
    )
    assert actual[0]["id"] == "dataset:snapshot_abc"
    assert assess_quality(contract, report, [source], actual)["status"] == "passed"


@pytest.mark.parametrize(
    "field,value", [("title", "另一资料"), ("url", "https://example.com/other")]
)
def test_source_identity_conflict_is_invalid_not_partial(field, value):
    contract, report, sources = example()
    report["sources"][0][field] = value
    assert assess_quality(contract, report, sources)["status"] == "invalid"


def test_search_snippet_and_missing_source_are_incomplete():
    contract, report, sources = example()
    sources[0].pop("content")
    sources[0].update(state="search_summary", excerpt="存在经营不确定性。")
    assert assess_quality(contract, report, sources)["status"] == "incomplete"
    assert assess_quality(contract, report, [])["status"] == "incomplete"


def numeric_example():
    contract, report, sources = example()
    report["sections"][0]["text"] = "本期收入增长20%。"
    report["coverage"][0]["excerpt"] = "本期收入增长20%。"
    content = "本期 收入 120 亿元；上期 收入 100 亿元。"
    observations = [
        {
            "id": "o1",
            "source_id": "file:abc",
            "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
    ]
    report["numeric_claims"] = [
        {
            "id": "growth",
            "section_id": "risk",
            "text": "收入增长20%",
            "value": "20",
            "unit": "%",
            "period": "本期",
            "operation": "percent_change",
            "operands": [
                {
                    "observation_id": "o1",
                    "value": "120",
                    "quote": "本期 收入 120 亿元",
                    "period": "本期",
                    "unit": "亿元",
                },
                {
                    "observation_id": "o1",
                    "value": "100",
                    "quote": "上期 收入 100 亿元",
                    "period": "上期",
                    "unit": "亿元",
                },
            ],
        }
    ]
    return contract, report, sources, observations


def test_numeric_claim_requires_actual_observation_and_exact_recalculation():
    contract, report, sources, observations = numeric_example()
    assert assess_quality(contract, report, sources)["status"] == "incomplete"
    assert assess_quality(contract, report, sources, observations)["status"] == "passed"
    report["numeric_claims"][0]["value"] = "25"
    report["sections"][0]["text"] = "本期收入增长25%。"
    report["numeric_claims"][0]["text"] = "收入增长25%"
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"


def test_one_verified_claim_cannot_clear_other_numbers_or_bless_model_observations():
    contract, report, sources, observations = numeric_example()
    report["sections"][0]["text"] += "利润为999亿元。"
    report["observations"] = observations
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"
    assert assess_quality(contract, report, sources)["status"] == "incomplete"


def test_observation_hash_unit_period_and_identity_mismatch_fail_closed():
    contract, report, sources, observations = numeric_example()
    for field, value in (("sha256", "0" * 64), ("source_id", "file:other")):
        changed = copy.deepcopy(observations)
        changed[0][field] = value
        assert assess_quality(contract, report, sources, changed)["status"] == "invalid"
    report["numeric_claims"][0]["operands"][0]["unit"] = "万美元"
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"


def test_sum_cannot_combine_previous_period_into_current_result():
    contract, report, sources, observations = numeric_example()
    claim = report["numeric_claims"][0]
    claim.update(operation="sum", value="220", unit="亿元", text="收入合计220亿元")
    report["sections"][0]["text"] = "本期收入合计220亿元。"
    report["coverage"][0]["excerpt"] = report["sections"][0]["text"]
    assessment = assess_quality(contract, report, sources, observations)
    assert assessment["status"] == "incomplete"
    assert "numeric_claim_unverified:growth" in assessment["issues"]


def test_same_period_sum_and_explicit_ratio_percentage_can_be_verified():
    contract, report, sources, observations = numeric_example()
    claim = report["numeric_claims"][0]
    claim.update(operation="ratio", value="120", unit="%", text="收入比率120%")
    report["sections"][0]["text"] = "本期收入比率120%。"
    report["coverage"][0]["excerpt"] = report["sections"][0]["text"]
    assert assess_quality(contract, report, sources, observations)["status"] == "passed"
    content = "本期 收入 120 亿元；本期 收入 100 亿元。"
    observations[0].update(content=content, sha256=hashlib.sha256(content.encode()).hexdigest())
    claim["operands"][1].update(period="本期", quote="本期 收入 100 亿元")
    claim.update(operation="sum", value="220", unit="亿元", text="收入合计220亿元")
    report["sections"][0]["text"] = "本期收入合计220亿元。"
    report["coverage"][0]["excerpt"] = report["sections"][0]["text"]
    assert assess_quality(contract, report, sources, observations)["status"] == "passed"


def test_operand_cannot_pair_value_with_another_metric_unit_in_same_quote():
    contract, report, sources, observations = numeric_example()
    content = "本期 收入120亿元，费用10美元。"
    observations[0].update(content=content, sha256=hashlib.sha256(content.encode()).hexdigest())
    claim = report["numeric_claims"][0]
    claim.update(operation="identity", value="120", unit="美元", text="本期收入120美元")
    claim["operands"] = [
        {"observation_id": "o1", "value": "120", "quote": content, "period": "本期", "unit": "美元"}
    ]
    report["sections"][0]["text"] = "本期收入120美元。"
    report["coverage"][0]["excerpt"] = report["sections"][0]["text"]
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"


def test_valid_number_cannot_bless_a_wrong_report_unit_or_additional_numeric_quote():
    contract, report, sources, observations = numeric_example()
    report["sections"][0]["text"] = "本期收入增长20美元。"
    report["numeric_claims"][0]["text"] = "收入增长20美元"
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"
    report["sections"][0]["text"] = "本期收入增长20%，利润999亿元。"
    report["numeric_claims"][0]["text"] = "收入增长20%，利润999亿元"
    assert assess_quality(contract, report, sources, observations)["status"] == "incomplete"


def test_cutoff_and_task_are_bound_to_host_contract():
    contract, report, sources = example()
    report["as_of"] = "2026-10-17"
    assert assess_quality(contract, report, sources)["status"] == "invalid"
    report["as_of"] = contract["as_of"]
    report["task_id"] = "b" * 24
    assert assess_quality(contract, report, sources)["status"] == "invalid"


def test_coverage_mapping_needs_real_section_excerpt_and_preserves_requirements():
    contract, report, sources = example()
    report["sections"][0]["heading"] = "研究结果"
    report["coverage"] = [
        {"requirement_id": "r1", "section_ids": ["risk"], "excerpt": "存在经营不确定性。"}
    ]
    assert assess_quality(contract, report, sources)["status"] == "passed"
    report["coverage"][0]["excerpt"] = "虚构的覆盖证据"
    assert assess_quality(contract, report, sources)["status"] == "incomplete"


def test_structured_claims_are_bounded_and_existing_payload_remains_valid():
    _, report, _ = example()
    assert validate_payload(report) is report
    report["numeric_claims"] = "verified"
    with pytest.raises(ValueError, match="numeric_claim"):
        validate_payload(report)


def saved_report(output):
    output.mkdir(exist_ok=True)
    _, report, _ = example()
    report["artifacts"] = []
    for kind in ("html", "docx", "pdf"):
        name = "research-report-old." + kind
        data = ("fixture-" + kind).encode()
        (output / name).write_bytes(data)
        report["artifacts"].append({"name": name, "sha256": hashlib.sha256(data).hexdigest()})
    (output / "research-report.json").write_text(json.dumps(report))
    return report


def test_archive_is_byte_verified_immutable_idempotent_and_task_bound(tmp_path):
    report = saved_report(tmp_path)
    version = archive_report_version(tmp_path, report["task_id"])
    assert len(version["files"]) == 4
    assert archive_report_version(tmp_path, report["task_id"]) == version
    archived = tmp_path / version["directory"] / version["files"][0]["stored_name"]
    assert archived.read_bytes() == (tmp_path / "research-report.json").read_bytes()
    with pytest.raises(ValueError, match="task_mismatch"):
        archive_report_version(tmp_path, "b" * 24)
    archived.chmod(0o600)
    archived.write_bytes(b"changed")
    with pytest.raises(ValueError, match="archive_changed"):
        archive_report_version(tmp_path, report["task_id"])


def test_archive_refuses_corrupt_or_symlink_artifacts_without_replacing_current(tmp_path):
    saved_report(tmp_path)
    artifact = tmp_path / "research-report-old.pdf"
    artifact.write_bytes(b"corrupt")
    before = (tmp_path / "research-report.json").read_bytes()
    with pytest.raises(ValueError, match="artifact_changed"):
        archive_report_version(tmp_path)
    assert (tmp_path / "research-report.json").read_bytes() == before
    artifact.unlink()
    artifact.symlink_to(tmp_path / "research-report-old.html")
    with pytest.raises(ValueError, match="alias"):
        archive_report_version(tmp_path)


def test_report_missing_one_artifact_can_continue_and_preserves_incomplete_history(tmp_path):
    from app.research_web.resources.research_report import write_research_report

    saved_report(tmp_path)
    (tmp_path / "research-report-old.pdf").unlink()
    _, report, _ = example()
    report["task_id"] = "b" * 24
    paths = write_research_report(tmp_path, report)
    assert json.loads(paths["json"].read_text())["task_id"] == "b" * 24
    versions = list_report_versions(tmp_path)
    assert versions[0]["task_id"] == "a" * 24
    assert versions[0]["missing_artifacts"] == ["research-report-old.pdf"]
    assert versions[0]["quality"] == "incomplete"
    assert len(versions[0]["files"]) == 3


def test_same_manifest_newly_available_artifact_creates_distinct_snapshot(tmp_path):
    saved_report(tmp_path)
    pdf = tmp_path / "research-report-old.pdf"
    original = pdf.read_bytes()
    pdf.unlink()
    incomplete = archive_report_version(tmp_path)
    pdf.write_bytes(original)
    complete = archive_report_version(tmp_path)
    assert incomplete["version_id"] != complete["version_id"]
    assert incomplete["missing_artifacts"] == [pdf.name]
    assert complete["missing_artifacts"] == []
    assert len(list_report_versions(tmp_path)) == 2


def test_version_listing_checks_every_byte_and_does_not_trust_model_quality(tmp_path):
    saved_report(tmp_path)
    version = archive_report_version(tmp_path)
    versions = list_report_versions(tmp_path)
    assert len(versions) == 1
    assert versions[0]["task_id"] == "a" * 24
    assert versions[0]["report"]["title"] == "风险说明"
    assert versions[0]["quality"] == "incomplete"
    destination = tmp_path / version["directory"] / version["files"][0]["stored_name"]
    destination.chmod(0o600)
    destination.write_bytes(b"corrupt")
    assert list_report_versions(tmp_path)[0]["quality"] == "invalid"


def test_new_report_archives_previous_report_and_artifact_identity_remains_unique(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.resources.research_report import write_research_report
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    output = store.directory(sid) / "outputs"
    _, old_report, _ = example()
    first = write_research_report(output, old_report)
    old_bytes = first["json"].read_bytes()
    _, new_report, sources = example()
    new_report["task_id"] = "b" * 24
    second = write_research_report(output, new_report)
    versions = list_report_versions(output)
    assert len(versions) == 1
    original = next(row for row in versions[0]["files"] if row["name"] == "research-report.json")
    assert (output / versions[0]["directory"] / original["stored_name"]).read_bytes() == old_bytes
    manifest = json.loads(second["json"].read_text())
    delivery = {"files": [{**row, "valid": True} for row in manifest["artifacts"]]}
    contract = make_contract(
        "b" * 24, "风险", ["风险"], "2026-10-16", "deep", previous_task_id="a" * 24
    )
    projected = report_projection(
        store, sid, store.files(sid), sources, "b" * 24, delivery, contract
    )
    assert projected["quality"] == "passed"
    assert projected["file_state"] == "available"


def test_frozen_projection_separates_missing_and_corrupt_files(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.resources.research_report import write_research_report
    from app.research_web.store import Store

    contract, report, sources = example()
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    missing = report_projection(store, sid, [], sources, "a" * 24, contract=contract)
    assert missing["quality"] == "incomplete"
    assert missing["file_state"] == "missing"
    paths = write_research_report(store.directory(sid) / "outputs", report)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**row, "valid": True} for row in manifest["artifacts"]]}
    paths["html"].write_bytes(b"corrupt")
    projected = report_projection(
        store, sid, store.files(sid), sources, "a" * 24, delivery, contract
    )
    assert projected["quality"] == "invalid"
    assert projected["file_state"] == "invalid"


def test_contract_projection_never_displays_prior_body_as_current_or_loses_invalid_status(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.resources.research_report import write_research_report
    from app.research_web.store import Store

    _, report, sources = example()
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    paths = write_research_report(store.directory(sid) / "outputs", report)
    contract = make_contract("b" * 24, "风险", ["风险"], "2026-10-16", "deep", "a" * 24)
    view = report_projection(store, sid, store.files(sid), sources, "b" * 24, contract=contract)
    assert view["quality"] == view["assessment"]["status"] == "incomplete"
    assert "previous_task_report" in view["issues"]
    assert "sections" not in view
    paths["json"].write_bytes(b"{invalid")
    invalid = report_projection(store, sid, store.files(sid), sources, "b" * 24, contract=contract)
    assert invalid["quality"] == invalid["assessment"]["status"] == "invalid"
