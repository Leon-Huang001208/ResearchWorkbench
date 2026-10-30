"""Real owned file/snapshot IO proves content versions; no model or provider calls."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import Query
from app.research_web.datahub.providers import Result
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.specialists import SpecialistError, SpecialistLedger
from app.research_web.specialists.evidence import evidence_snapshot, verify_snapshots
from app.research_web.store import Store


@pytest.fixture
def owned(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "半导体证据版本")["id"]
    ledger = SpecialistLedger(store)
    ledger.create(
        sid,
        {"confirmed": True, "max_tokens": 100000, "max_calls": 12},
        "2026-10-28",
        {"model": "fixture"},
        "evidence-request",
    )
    service = SimpleNamespace(
        store=store, specialist_ledger=ledger, datahub=SimpleNamespace(snapshots=Snapshots(store))
    )
    return service, sid


def result(ref, *, artifacts=()):
    return {
        "conclusion": "有原件支持的受限判断",
        "evidence_ids": [ref],
        "as_of_date": "2026-10-28",
        "limitations": ["不认证历史PIT"],
        "artifact_ids": list(artifacts),
    }


def file(service, sid, path, raw):
    target = service.store.directory(sid) / path
    target.write_bytes(raw)
    items = service.store.files(sid)
    fid = hashlib.sha256(path.encode()).hexdigest()[:24]
    assert any(item["id"] == fid for item in items)
    return fid


def state(attempt_result, frozen):
    return {
        "attempts": {
            "attempt-a": {
                "status": "succeeded",
                "invalidated": False,
                "result": attempt_result,
                "evidence_snapshot": frozen,
            }
        }
    }


def dataset(service, sid):
    return service.datahub.snapshots.publish(
        sid,
        Query(source="fund_nav", code="000001"),
        Result(
            status="complete",
            as_of="2026-10-27",
            rows=[{"date": "2026-10-27", "nav": 1.2}],
            raw=[b'{"date":"2026-10-27","nav":1.2}'],
        ),
    )


def web(service, sid):
    ref = "web:" + "a" * 24
    path = "inputs/web-" + "a" * 24 + ".txt"
    body = "发布时间：2026-10-27\n半导体行业供需资料".encode()
    fid = file(service, sid, path, body)
    service.store.session(sid)["web_evidence"] = {
        ref: {
            "id": ref,
            "title": "行业原件",
            "url": "https://example.com/research",
            "state": "available",
            "file_id": fid,
            "path": path,
            "sha256": hashlib.sha256(body).hexdigest(),
            "response_sha256": "b" * 64,
            "fetched_at": "2026-10-28T01:00:00+00:00",
            "as_of": "2026-10-27",
            "date_evidence": [],
            "final_url": "https://example.com/research",
        }
    }
    service.store.save()
    return ref, fid


def test_same_path_file_id_cannot_reuse_overwritten_output(owned):
    service, sid = owned
    evidence = file(service, sid, "inputs/source.txt", b"original source")
    artifact = file(service, sid, "outputs/analysis.json", b'{"value":1}')
    output = result("file:" + evidence, artifacts=[artifact])
    frozen = evidence_snapshot(service, sid, output)
    assert verify_snapshots(service, sid, state(output, frozen)) == []
    assert file(service, sid, "outputs/analysis.json", b'{"value":2}') == artifact
    assert verify_snapshots(service, sid, state(output, frozen)) == ["attempt-a"]


def test_upload_mutation_or_missing_original_invalidates_result(owned):
    service, sid = owned
    fid = file(service, sid, "inputs/source.txt", b"original source")
    output = result("file:" + fid)
    frozen = evidence_snapshot(service, sid, output)
    path = service.store.directory(sid) / "inputs/source.txt"
    path.write_bytes(b"replacement source")
    assert verify_snapshots(service, sid, state(output, frozen)) == ["attempt-a"]
    path.unlink()
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, output)


def test_web_snapshot_binds_original_bytes_and_full_host_provenance(owned):
    service, sid = owned
    ref, _ = web(service, sid)
    output = result(ref)
    frozen = evidence_snapshot(service, sid, output)
    assert verify_snapshots(service, sid, state(output, frozen)) == []
    service.store.session(sid)["web_evidence"][ref]["title"] = "changed source identity"
    service.store.save()
    assert verify_snapshots(service, sid, state(output, frozen)) == ["attempt-a"]


def test_host_web_text_cannot_be_reclassified_as_uploaded_evidence(owned):
    service, sid = owned
    _, fid = web(service, sid)
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, result("file:" + fid))


def test_future_web_publication_is_rejected_even_when_acquired_today(owned):
    service, sid = owned
    ref, _ = web(service, sid)
    service.store.session(sid)["web_evidence"][ref]["as_of"] = "2026-10-29"
    with pytest.raises(SpecialistError, match="日期|晚于"):
        evidence_snapshot(service, sid, result(ref))


def test_dataset_snapshot_reads_manifest_public_bytes_and_private_raw(owned):
    service, sid = owned
    saved = dataset(service, sid)
    did = saved["dataset_id"]
    output = result("dataset:" + did)
    frozen = evidence_snapshot(service, sid, output)
    assert verify_snapshots(service, sid, state(output, frozen)) == []
    raw = service.store.root / ".control" / "snapshots" / sid / did / "raw-0001.bin"
    raw.write_bytes(b"mutated original response")
    assert verify_snapshots(service, sid, state(output, frozen)) == ["attempt-a"]
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, output)


def test_dataset_manifest_metadata_change_invalidates_even_if_bytes_match(owned):
    service, sid = owned
    saved = dataset(service, sid)
    did = saved["dataset_id"]
    output = result("dataset:" + did)
    frozen = evidence_snapshot(service, sid, output)
    private = service.store.root / ".control" / "snapshots" / sid / did / "manifest.json"
    public = service.store.directory(sid) / "inputs" / "datasets" / did / "manifest.json"
    metadata = json.loads(private.read_bytes())
    metadata["provider_metadata"] = {"revised_unit": "different"}
    raw = json.dumps(metadata).encode()
    private.write_bytes(raw)
    public.write_bytes(raw)
    assert verify_snapshots(service, sid, state(output, frozen)) == ["attempt-a"]


@pytest.mark.parametrize("change", ["clue", "future", "missing-original"])
def test_dataset_unqualified_future_and_missing_originals_are_rejected(owned, change):
    service, sid = owned
    saved = dataset(service, sid)
    did = saved["dataset_id"]
    private = service.store.root / ".control" / "snapshots" / sid / did
    public = service.store.directory(sid) / "inputs" / "datasets" / did
    metadata = json.loads((private / "manifest.json").read_bytes())
    if change == "clue":
        metadata["admission"] = {"report_admitted": False}
    elif change == "future":
        metadata["as_of"] = "2026-10-29"
    else:
        (private / "raw-0001.bin").unlink()
    raw = json.dumps(metadata).encode()
    (private / "manifest.json").write_bytes(raw)
    (public / "manifest.json").write_bytes(raw)
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, result("dataset:" + did))


def test_cross_account_snapshot_and_scope_revocation_are_rejected(owned, tmp_path):
    service, sid = owned
    saved = dataset(service, sid)
    other_store = Store(tmp_path / "another-account")
    other_sid = other_store.create("fingpt", "other")["id"]
    other_ledger = SpecialistLedger(other_store)
    other_ledger.create(
        other_sid,
        {"confirmed": True, "max_tokens": 100000, "max_calls": 12},
        "2026-10-28",
        {"model": "fixture"},
        "evidence-request",
    )
    other = SimpleNamespace(
        store=other_store,
        specialist_ledger=other_ledger,
        datahub=SimpleNamespace(snapshots=Snapshots(other_store)),
    )
    with pytest.raises(SpecialistError):
        evidence_snapshot(other, other_sid, result("dataset:" + saved["dataset_id"]))
    service.store.session(sid)["source_scope"] = ["uploads"]
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, result("dataset:" + saved["dataset_id"]))


def test_legacy_success_without_hashes_is_invalidated_and_late_results_are_skipped(owned):
    service, sid = owned
    assert verify_snapshots(
        service,
        sid,
        {
            "attempts": {
                "legacy": {"status": "succeeded", "result": {}},
                "late": {"status": "succeeded", "invalidated": True, "result": {}},
            }
        },
    ) == ["legacy"]


def test_original_symlink_is_rejected_by_real_store_reader(owned, tmp_path):
    service, sid = owned
    fid = file(service, sid, "inputs/source.txt", b"original")
    target = service.store.directory(sid) / "inputs/source.txt"
    target.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"foreign")
    target.symlink_to(outside)
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, result("file:" + fid))


def test_unregistered_reference_is_never_certified(owned):
    service, sid = owned
    with pytest.raises(SpecialistError):
        evidence_snapshot(service, sid, result("web:" + "f" * 24))


def test_evidence_read_limit_applies_to_combined_node_bytes(owned, monkeypatch):
    from app.research_web.specialists import evidence

    service, sid = owned
    fid = file(service, sid, "inputs/source.txt", b"123456")
    artifact = file(service, sid, "outputs/result.txt", b"789")
    monkeypatch.setattr(evidence, "MAX_BYTES", 8)
    with pytest.raises(SpecialistError, match="上限"):
        evidence_snapshot(service, sid, result("file:" + fid, artifacts=[artifact]))
