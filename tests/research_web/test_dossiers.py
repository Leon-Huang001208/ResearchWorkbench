"""Long-lived metadata never rewrites or certifies original research evidence."""

import asyncio
import hashlib
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.research_web.dossiers import DossierService
from app.research_web.dossiers.lock import retention_lock
from app.research_web.store import Store, StoreError


@pytest.fixture(autouse=True)
def isolate_runtime_credentials(monkeypatch):
    """Archive tests neither need the host Keychain nor a live MCP runtime."""
    import keyring

    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    values = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, account: values.get((service, account))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, account, value: values.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, account: values.pop((service, account), None)
    )


def service(tmp_path):
    store = Store(tmp_path / "personal")
    research = SimpleNamespace(store=store)
    research.dossiers = DossierService(research)
    return research


def create(research, key="create-0001"):
    return research.dossiers.create(
        {
            "title": "公司研究",
            "subject": {"kind": "company", "key": "600519.SH", "label": "贵州茅台"},
            "idempotency_key": key,
        }
    )


def upload(research, text="原始材料"):
    row = research.store.create("fingpt", "来源会话")
    path = research.store.directory(row["id"]) / "inputs" / "source.txt"
    path.write_text(text)
    research.store.files(row["id"])
    return row, path


def bind(research, dossier, sid, key="evidence-0001"):
    return research.dossiers.add_evidence(
        dossier["id"],
        {
            "expected_revision": dossier["revision"],
            "idempotency_key": key,
            "source_session_id": sid,
            "reference": {"type": "file", "id": "inputs/source.txt"},
            "locator": "第1段",
        },
    )


def test_reads_never_initialize_dossier_storage(tmp_path):
    research = service(tmp_path)
    before = set(research.store.root.rglob("*"))
    assert research.dossiers.list() == {"items": [], "next_cursor": None}
    with pytest.raises(StoreError) as error:
        research.dossiers.get("d" * 32)
    assert error.value.status == 404
    with pytest.raises(StoreError):
        research.dossiers.read_evidence("d" * 32, "e" * 32)
    assert set(research.store.root.rglob("*")) == before


def test_idempotency_versions_and_reopen(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    assert create(research) == dossier
    request = {
        "expected_revision": 1,
        "idempotency_key": "opinion-0001",
        "kind": "opinion",
        "title": "初判",
        "body": "尚待验证",
        "state": "open",
        "reason": "初次记录",
        "evidence_ids": [],
    }
    changed = research.dossiers.add_record(dossier["id"], request)
    assert changed["revision"] == 2
    assert research.dossiers.add_record(dossier["id"], request) == changed
    with pytest.raises(StoreError) as error:
        research.dossiers.add_record(dossier["id"], {**request, "body": "不同内容"})
    assert error.value.code == "dossier_idempotency_conflict"
    record_id = changed["records"][0]["id"]
    research.dossiers.add_record(
        dossier["id"],
        {
            **request,
            "expected_revision": 2,
            "idempotency_key": "opinion-0002",
            "record_id": record_id,
            "body": "新证据反驳",
            "state": "refuted",
        },
    )
    reopened = DossierService(SimpleNamespace(store=Store(research.store.root)))
    assert reopened.get(dossier["id"])["records"][0]["body"] == "新证据反驳"
    assert len(reopened.timeline(dossier["id"])["items"]) == 3
    command = "from pathlib import Path; from types import SimpleNamespace; from app.research_web.store import Store; from app.research_web.dossiers import DossierService; import sys; print(DossierService(SimpleNamespace(store=Store(Path(sys.argv[1])))).get(sys.argv[2])['revision'])"
    completed = subprocess.run(
        [sys.executable, "-c", command, str(research.store.root), dossier["id"]],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "3"


def test_transaction_failure_preserves_revision_and_idempotency(tmp_path, monkeypatch):
    research = service(tmp_path)
    dossier = create(research)
    request = {"expected_revision": 1, "idempotency_key": "patch-0001", "title": "修订标题"}

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("injected transaction failure")

    with monkeypatch.context() as patch:
        patch.setattr(research.dossiers.metadata, "_append_event", fail)
        with pytest.raises(StoreError):
            research.dossiers.patch(dossier["id"], request)
    assert research.dossiers.get(dossier["id"])["revision"] == 1
    assert research.dossiers.patch(dossier["id"], request)["revision"] == 2


def test_concurrent_revision_only_one_wins(tmp_path):
    research = service(tmp_path)
    dossier = create(research)

    def update(number):
        try:
            research.dossiers.patch(
                dossier["id"],
                {
                    "expected_revision": 1,
                    "idempotency_key": f"patch-{number:04}",
                    "title": str(number),
                },
            )
            return "ok"
        except StoreError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, [1, 2]))
    assert results.count("ok") == 1
    assert 409 in results


def test_evidence_identity_missing_change_revocation_and_soft_delete(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    row, path = upload(research)
    detail = bind(research, dossier, row["id"])
    item = detail["evidence"][0]
    assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert item["published_at"] is None
    assert item["locator"] == "第1段"
    assert research.dossiers.read_evidence(dossier["id"], item["id"])["content"] == "原始材料"
    research.store.soft_delete(row["id"])
    assert research.dossiers.read_evidence(dossier["id"], item["id"])["content"] == "原始材料"
    row["source_scope"] = ["web"]
    with pytest.raises(StoreError) as error:
        research.dossiers.read_evidence(dossier["id"], item["id"])
    assert error.value.code == "dossier_source_revoked"
    row["source_scope"] = ["uploads"]
    path.write_text("篡改材料")
    assert research.dossiers.get(dossier["id"])["evidence"][0]["state"] == "changed"
    with pytest.raises(StoreError):
        research.dossiers.read_evidence(dossier["id"], item["id"])
    path.unlink()
    assert research.dossiers.get(dossier["id"])["evidence"][0]["state"] == "missing"
    research.store.mark_native_deleted(row["id"])
    with pytest.raises(StoreError) as error:
        research.store.purge(row["id"])
    assert error.value.code == "dossier_evidence_retained"
    assert row["id"] in research.store.data["sessions"]


def test_cross_root_and_path_escape_denied(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    row, path = upload(research)
    other = SimpleNamespace(store=Store(tmp_path / "other"))
    other.dossiers = DossierService(other)
    with pytest.raises(StoreError):
        other.dossiers.get(dossier["id"])
    for invalid in ["../outside.txt", str(path), "inputs/../source.txt", "inputs\\source.txt"]:
        with pytest.raises(StoreError):
            research.dossiers.add_evidence(
                dossier["id"],
                {
                    "expected_revision": 1,
                    "idempotency_key": "escape-0001",
                    "source_session_id": row["id"],
                    "reference": {"type": "file", "id": invalid},
                },
            )
    path.unlink()
    path.symlink_to(tmp_path / "outside.txt")
    (tmp_path / "outside.txt").write_text("private")
    with pytest.raises(StoreError):
        bind(research, dossier, row["id"])


def test_retention_and_pin_commit_share_same_lock(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    row, _ = upload(research)
    with retention_lock(research.store.root):

        def competing():
            with pytest.raises(StoreError) as error:
                bind(research, dossier, row["id"])
            return error.value.code

        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(competing).result() == "dossier_retention_busy"
    assert research.dossiers.get(dossier["id"])["evidence"] == []
    detail = bind(research, dossier, row["id"])
    assert len(detail["evidence"]) == 1


def test_handoff_is_frozen_draft_and_handles_require_registration(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    source, _ = upload(research)
    detail = bind(research, dossier, source["id"])
    target = research.store.create("fingpt", "继续研究")
    request = {
        "expected_revision": 2,
        "idempotency_key": "handoff-0001",
        "mode": "fingpt",
        "action": "update_view",
    }
    handoff = research.dossiers.handoff(dossier["id"], request)
    assert handoff["auto_send"] is False
    assert handoff["context"]["revision"] == 2
    research.dossiers.bind_handoff(target["id"], handoff["context"]["handoff_id"])
    handle = handoff["context"]["evidence_handles"][0]
    assert research.dossiers.read_handle(target["id"], handle)["content"] == "原始材料"
    assert (
        research.store.session(target["id"])["dossier_evidence"][handle]["sha256"]
        == detail["evidence"][0]["sha256"]
    )
    research.dossiers.patch(
        dossier["id"], {"expected_revision": 3, "idempotency_key": "patch-0001", "title": "变化"}
    )
    assert research.dossiers.handoff(dossier["id"], request) == handoff
    assert handoff["context"]["revision"] == 2


def test_consistent_backup_restore_validates_originals_and_owner(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    row, path = upload(research)
    bind(research, dossier, row["id"])
    backup = tmp_path / "dossiers.snapshot.sqlite3"
    receipt = research.dossiers.backup_to(backup)
    research.dossiers.patch(
        dossier["id"], {"expected_revision": 2, "idempotency_key": "patch-0001", "title": "待恢复"}
    )
    before = research.dossiers.metadata.path.read_bytes()
    path.write_text("原件已变")
    with pytest.raises(StoreError):
        research.dossiers.restore_from(backup, expected_sha256=receipt["sha256"])
    assert research.dossiers.metadata.path.read_bytes() == before
    other = DossierService(SimpleNamespace(store=Store(tmp_path / "other")))
    with pytest.raises(StoreError) as error:
        other.restore_from(backup, expected_sha256=receipt["sha256"])
    assert error.value.code == "dossier_storage_identity_mismatch"
    path.write_text("原始材料")
    research.dossiers.restore_from(backup, expected_sha256=receipt["sha256"])
    assert research.dossiers.get(dossier["id"])["title"] == "公司研究"
    assert research.dossiers.metadata.retained_by(row["id"]) == [dossier["id"]]


def test_failed_first_write_can_be_retried_without_new_database_identity(tmp_path, monkeypatch):
    research = service(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(
            research.dossiers.metadata,
            "_append_event",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("injected")),
        )
        with pytest.raises(StoreError):
            create(research)
    assert research.dossiers.list()["items"] == []
    assert create(research)["revision"] == 1


def test_reference_and_retention_rollback_together(tmp_path, monkeypatch):
    research = service(tmp_path)
    dossier = create(research)
    row, _ = upload(research)
    with monkeypatch.context() as patch:
        patch.setattr(
            research.dossiers.metadata,
            "_append_event",
            lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("after pin inserted")),
        )
        with pytest.raises(StoreError):
            bind(research, dossier, row["id"])
    assert research.dossiers.get(dossier["id"])["revision"] == 1
    assert research.dossiers.get(dossier["id"])["evidence"] == []
    assert research.dossiers.metadata.retained_by(row["id"]) == []
    assert len(bind(research, dossier, row["id"])["evidence"]) == 1


def test_forged_provenance_and_company_name_identity_rejected(tmp_path):
    research = service(tmp_path)
    dossier = create(research)
    row, _ = upload(research)
    with pytest.raises(StoreError) as error:
        research.dossiers.add_evidence(
            dossier["id"],
            {
                "expected_revision": 1,
                "idempotency_key": "forged-0001",
                "source_session_id": row["id"],
                "reference": {"type": "file", "id": "inputs/source.txt"},
                "sha256": "0" * 64,
                "published_at": "2020-01-01",
            },
        )
    assert error.value.status == 422
    with pytest.raises(StoreError):
        research.dossiers.create(
            {
                "title": "不按名称合并",
                "subject": {"kind": "company", "key": "MaoTai", "label": "贵州茅台"},
                "idempotency_key": "forged-0002",
            }
        )


def test_dataset_retains_original_manifest_after_soft_delete_without_file_alias(tmp_path):
    from app.research_web.datahub.contracts import Query
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.snapshots import Snapshots

    research = service(tmp_path)
    dossier = create(research)
    row = research.store.create("fingpt", "历史数据来源")
    snapshots = Snapshots(research.store)
    research.datahub = SimpleNamespace(snapshots=snapshots)
    manifest = snapshots.publish(
        row["id"],
        Query(source="fund_nav", code="000001"),
        Result(
            rows=[{"date": "2026-01-01", "nav": 1.2}],
            status="complete",
            as_of="2026-01-01",
            pagination_complete=True,
        ),
    )
    request = {
        "expected_revision": 1,
        "idempotency_key": "dataset-0001",
        "source_session_id": row["id"],
        "reference": {"type": "dataset", "id": manifest["dataset_id"]},
    }
    detail = research.dossiers.add_evidence(dossier["id"], request)
    evidence = detail["evidence"][0]
    assert evidence["published_at"] is None
    assert evidence["coverage"]["as_of"] == "2026-01-01"
    research.store.soft_delete(row["id"])
    read = research.dossiers.read_evidence(dossier["id"], evidence["id"], full=True)
    assert read["manifest"]["dataset_id"] == manifest["dataset_id"]
    assert json.loads(read["content"])[0]["nav"] == 1.2
    with pytest.raises(StoreError) as error:
        research.dossiers.add_evidence(
            dossier["id"],
            {
                **request,
                "expected_revision": 2,
                "idempotency_key": "alias-0001",
                "reference": {
                    "type": "file",
                    "id": f"inputs/datasets/{manifest['dataset_id']}/rows.json",
                },
            },
        )
    assert error.value.code == "dossier_evidence_alias_denied"


@pytest.mark.asyncio
async def test_native_delete_checks_pins_before_rpc_and_holds_fence_during_rpc(tmp_path):
    from test_api import NativeFixture

    from app.research_web.service import ResearchService

    native = NativeFixture()
    research = ResearchService(native, Store(tmp_path / "personal"))
    dossier = create(research)
    row, _ = upload(research)
    bind(research, dossier, row["id"])
    research.store.soft_delete(row["id"])
    with pytest.raises(StoreError) as error:
        await research.permanent_delete_session(row["id"])
    assert error.value.code == "dossier_evidence_retained"
    assert not any(method == "session.delete" for method, _ in native.calls)

    fresh, _ = upload(research)
    research.store.soft_delete(fresh["id"])
    entered, release = asyncio.Event(), asyncio.Event()
    rpc = native.rpc

    async def delayed(method, payload):
        if method == "session.delete":
            entered.set()
            await release.wait()
        return await rpc(method, payload)

    native.rpc = delayed
    deletion = asyncio.create_task(research.permanent_delete_session(fresh["id"]))
    await asyncio.wait_for(entered.wait(), 2)
    with pytest.raises(StoreError) as error:
        bind(research, {**dossier, "revision": 2}, fresh["id"], "racing-0001")
    assert error.value.code == "dossier_retention_busy"
    release.set()
    assert await deletion == {"id": fresh["id"], "purged": True}


@pytest.mark.asyncio
async def test_host_read_handle_registers_canonical_evidence_and_quality_observations(tmp_path):
    from app.research_web.research_quality_service import observations
    from app.research_web.research_web_sources import read_source
    from app.research_web.resources.research_report import canonical_source

    research = service(tmp_path)
    research.lock = asyncio.Lock()
    dossier = create(research)
    row, _ = upload(research, "2025年营业收入100亿元。")
    bind(research, dossier, row["id"])
    target = research.store.create("fingpt", "续研")
    target["source_scope"] = ["uploads"]
    handoff = research.dossiers.handoff(
        dossier["id"],
        {
            "expected_revision": 2,
            "idempotency_key": "handoff-0001",
            "mode": "fingpt",
            "action": "update_view",
        },
    )
    research.dossiers.bind_handoff(target["id"], handoff["context"]["handoff_id"])
    handle = handoff["context"]["evidence_handles"][0]
    result = await read_source(research, target["id"], "read", handle)
    listed = await read_source(research, target["id"], "list")
    assert listed["sources"][0]["dossier_handle"] == handle
    source = canonical_source(listed["sources"], result["observation_id"])
    assert source["id"].startswith("file:")
    values = observations(
        research, target["id"], [], listed["sources"], task_id="a" * 24, contract_sha="b" * 64
    )
    assert any(
        value["id"] == source["id"] and value["content"] == "2025年营业收入100亿元。"
        for value in values
    )
    assert (research.store.root / "sessions" / row["id"] / "inputs/source.txt").is_file()
    assert not (research.store.directory(target["id"]) / "inputs/source.txt").exists()
