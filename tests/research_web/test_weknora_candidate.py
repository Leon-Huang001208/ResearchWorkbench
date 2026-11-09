"""Offline candidate checks never contact a service or fabricate live acceptance."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "weknora_candidate.py"
SPEC = importlib.util.spec_from_file_location("weknora_candidate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


def capacity_manifest():
    return {
        "schema_version": 1,
        "release": candidate.RELEASE,
        "source_revision": candidate.SOURCE_REVISION,
        "components": [
            {
                "name": name,
                "image": f"example.invalid/{name}@sha256:" + "a" * 64,
                "platform": "linux/arm64",
                "proof": {
                    "source_revision": candidate.SOURCE_REVISION,
                    "image_digest": "a" * 64,
                    "platform": "linux/arm64",
                    "evidence_sha256": "b" * 64,
                },
                "image_bytes": 100,
                "peak_memory_bytes": 10,
            }
            for name in sorted(candidate.COMPONENTS)
        ],
        "disk_bytes": {
            "originals": 10,
            "database": 20,
            "index": 30,
            "parsing": 40,
            "recovery": 60,
            "reserve": 50,
        },
        "memory_bytes": {"parsing_extra": 10, "reserve": 20},
    }


def material_manifest():
    return {
        "schema_version": 1,
        "owner_id": "owner-1",
        "materials": [
            {
                "source_id": "research-1",
                "owner_id": "owner-1",
                "kind": "research_material",
                "relative_path": "inputs/report.txt",
                "legacy_ref": "session:fixture:research-1",
            }
        ],
    }


def frozen_benchmark():
    citation = {"locator": "paragraph:1", "excerpt_sha256": "b" * 64}
    gold = {
        "schema_version": 1,
        "documents": [
            {"document_id": "doc-1", "original_sha256": "a" * 64, "citations": [citation]}
        ],
        "questions": [
            {"question_id": f"q-{i}", "expected_document_ids": ["doc-1"]} for i in range(20)
        ],
    }
    actual = {
        "schema_version": 1,
        "gold_sha256": candidate.canonical_sha256(gold),
        "questions": [
            {
                "question_id": f"q-{i}",
                "hits": [{"document_id": "doc-1", "original_sha256": "a" * 64, **citation}],
            }
            for i in range(20)
        ],
    }
    return gold, actual


def test_capacity_counts_peak_and_never_authorizes_deployment():
    result = candidate.capacity_plan(
        capacity_manifest(), available_disk_bytes=710, available_memory_bytes=80
    )
    assert result["status"] == "capacity_sufficient"
    assert result["required_disk_bytes"] == 710
    assert result["required_memory_bytes"] == 80
    assert result["deployment_authorized"] is False
    assert result["artifact_evidence"] == "declared_not_runtime_verified"


def test_capacity_reports_both_shortfalls():
    result = candidate.capacity_plan(
        capacity_manifest(), available_disk_bytes=700, available_memory_bytes=50
    )
    assert result["status"] == "capacity_insufficient"
    assert result["disk_shortfall_bytes"] == 10
    assert result["memory_shortfall_bytes"] == 30


def test_capacity_rejects_floating_or_wrong_source_images():
    for change in ("latest", "source", "platform", "proof", "duplicate"):
        manifest = capacity_manifest()
        component = manifest["components"][0]
        if change == "latest":
            component["image"] = "example.invalid/app:latest"
        elif change == "source":
            component["proof"]["source_revision"] = "0" * 40
        elif change == "platform":
            component["platform"] = "linux/amd64"
        elif change == "proof":
            component["proof"]["image_digest"] = "c" * 64
        else:
            manifest["components"][1] = copy.deepcopy(component)
        with pytest.raises(candidate.CandidateError):
            candidate.capacity_plan(
                manifest, available_disk_bytes=1000, available_memory_bytes=1000
            )


def test_capacity_rejects_underestimated_recovery_or_boolean_counts():
    manifest = capacity_manifest()
    manifest["disk_bytes"]["recovery"] = 59
    with pytest.raises(candidate.CandidateError, match="recovery_estimate_insufficient"):
        candidate.capacity_plan(manifest, available_disk_bytes=1000, available_memory_bytes=1000)
    with pytest.raises(candidate.CandidateError, match="available_disk_invalid"):
        candidate.capacity_plan(
            capacity_manifest(), available_disk_bytes=True, available_memory_bytes=1000
        )


def test_inventory_hashes_only_explicit_research_originals(tmp_path):
    (tmp_path / "inputs").mkdir()
    original = tmp_path / "inputs" / "report.txt"
    original.write_bytes(b"frozen research original")
    (tmp_path / "unlisted.txt").write_bytes(b"not scanned")
    before = original.stat()
    result = candidate.inventory(tmp_path, material_manifest())
    assert result["count"] == 1
    assert result["migration_performed"] is False
    assert (
        result["items"][0]["original_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
    )
    assert result["items"][0]["legacy_ref"] == "session:fixture:research-1"
    assert original.stat().st_ino == before.st_ino
    assert original.stat().st_mtime_ns == before.st_mtime_ns


def test_inventory_refuses_symlink_and_hardlink(tmp_path):
    (tmp_path / "inputs").mkdir()
    source = tmp_path / "original.txt"
    source.write_bytes(b"original")
    link = tmp_path / "inputs" / "report.txt"
    link.symlink_to(source)
    symlink_identity = link.lstat()
    try:
        with pytest.raises(candidate.CandidateError, match="inventory_read_failed"):
            candidate.inventory(tmp_path, material_manifest())
    finally:
        current = link.lstat()
        assert (current.st_dev, current.st_ino) == (
            symlink_identity.st_dev,
            symlink_identity.st_ino,
        )
        link.unlink()
    os.link(source, link)
    hardlink_identity = link.lstat()
    try:
        with pytest.raises(candidate.CandidateError, match="inventory_file_unsafe"):
            candidate.inventory(tmp_path, material_manifest())
    finally:
        current = link.lstat()
        assert (current.st_dev, current.st_ino) == (
            hardlink_identity.st_dev,
            hardlink_identity.st_ino,
        )
        link.unlink()
    assert source.read_bytes() == b"original"
    assert source.stat().st_nlink == 1


def test_inventory_refuses_unknown_owner_and_protected_kinds(tmp_path):
    for update in (
        {"owner_id": "other"},
        {"kind": "financial_snapshot"},
        {"kind": "template"},
        {"kind": "workbook"},
        {"kind": "formal_report"},
    ):
        manifest = material_manifest()
        manifest["materials"][0].update(update)
        with pytest.raises(candidate.CandidateError, match="inventory_material_not_admitted"):
            candidate.inventory(tmp_path, manifest)
    manifest = material_manifest()
    manifest["owner_id"] = "unknown"
    with pytest.raises(candidate.CandidateError, match="inventory_owner_missing"):
        candidate.inventory(tmp_path, manifest)


def test_inventory_refuses_escape_and_protected_paths(tmp_path):
    for path in (
        "../report.txt",
        "/tmp/report.txt",
        "inputs/../report.txt",
        "outputs/final.docx",
        "templates/template.docx",
        "inputs//report.txt",
    ):
        manifest = material_manifest()
        manifest["materials"][0]["relative_path"] = path
        with pytest.raises(candidate.CandidateError, match="inventory_path_invalid"):
            candidate.inventory(tmp_path, manifest)


def test_inventory_refuses_hash_drift_and_duplicates(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "report.txt").write_bytes(b"changed")
    manifest = material_manifest()
    manifest["materials"][0]["original_sha256"] = "a" * 64
    with pytest.raises(candidate.CandidateError, match="inventory_hash_mismatch"):
        candidate.inventory(tmp_path, manifest)
    manifest = material_manifest()
    manifest["materials"].append(copy.deepcopy(manifest["materials"][0]))
    with pytest.raises(candidate.CandidateError, match="inventory_duplicate_material"):
        candidate.inventory(tmp_path, manifest)


def test_benchmark_binds_gold_before_scoring_and_records_actual_sources():
    gold, actual = frozen_benchmark()
    result = candidate.benchmark(gold, actual)
    assert result["status"] == "passed"
    assert result["matched_questions"] == 20
    assert result["citation_coverage"] == 1
    assert result["live_acceptance"] is False
    assert result["question_results"][0]["actual_document_ids"] == ["doc-1"]
    gold["questions"][0]["expected_document_ids"] = ["changed"]
    with pytest.raises(candidate.CandidateError, match="benchmark_gold_binding_invalid"):
        candidate.benchmark(gold, actual)


def test_benchmark_requires_eighteen_matches():
    gold, actual = frozen_benchmark()
    for question in actual["questions"][:2]:
        question["hits"] = []
    assert candidate.benchmark(gold, actual)["status"] == "passed"
    actual["questions"][2]["hits"] = []
    result = candidate.benchmark(gold, actual)
    assert result["status"] == "failed"
    assert result["matched_questions"] == 17


def test_benchmark_rejects_unresolved_citation_despite_recall():
    gold, actual = frozen_benchmark()
    actual["questions"][0]["hits"][0]["excerpt_sha256"] = "c" * 64
    result = candidate.benchmark(gold, actual)
    assert result["matched_questions"] == 20
    assert result["status"] == "failed"
    assert result["verified_citations"] == 19


def test_benchmark_rejects_outside_corpus_and_repeated_question():
    gold, actual = frozen_benchmark()
    actual["questions"][0]["hits"][0]["document_id"] = "future-document"
    result = candidate.benchmark(gold, actual)
    assert result["scope_violations"] == 1
    assert result["status"] == "failed"
    actual["questions"][0]["question_id"] = "q-1"
    with pytest.raises(candidate.CandidateError, match="benchmark_response_scope_invalid"):
        candidate.benchmark(gold, actual)


def test_benchmark_refuses_wrong_count_or_more_than_top_eight():
    gold, actual = frozen_benchmark()
    actual["questions"][0]["hits"] *= 9
    with pytest.raises(candidate.CandidateError, match="benchmark_response_scope_invalid"):
        candidate.benchmark(gold, actual)
    gold["questions"].pop()
    actual["gold_sha256"] = candidate.canonical_sha256(gold)
    with pytest.raises(candidate.CandidateError, match="benchmark_question_count_invalid"):
        candidate.benchmark(gold, actual)


def test_cli_is_bounded_and_read_only(tmp_path):
    import subprocess
    import sys

    gold, actual = frozen_benchmark()
    gold_path = tmp_path / "gold.json"
    actual_path = tmp_path / "actual.json"
    gold_path.write_text(json.dumps(gold))
    actual_path.write_text(json.dumps(actual))
    command = [sys.executable, candidate.__file__, "benchmark", str(gold_path), str(actual_path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert len(output.encode()) < 4096
    assert 'question_results"' not in output
    assert json.loads(output)["live_acceptance"] is False
    actual_path.write_text("not-json")
    invalid = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert invalid.returncode == 2
    assert json.loads(invalid.stdout)["error"] == "input_read_failed"
