"""Incremental directory state is durable; upstream IO is an explicit test double."""

import asyncio
import copy
import hashlib
import shutil

import pytest

from app.research_web.store import StoreError


class Upstream:
    def __init__(self):
        self.documents = {}
        self.uploads = []
        self.parse_status = "completed"
        self.timeout_after_upload = False
        self.on_upload = None
        self.originals = {}

    async def knowledge_bases(self):
        return [{"id": "kb1", "tenant_id": 101, "created_by": "user1"}]

    async def upload(self, kb_id, filename, content, metadata):
        if self.on_upload:
            self.on_upload()
        identifier = "d" + str(len(self.documents) + 1)
        document = {
            "id": identifier,
            "kb_id": kb_id,
            "file_hash": hashlib.md5(content).hexdigest(),
            "parse_status": self.parse_status,
            "enable_status": "enabled",
            "metadata": metadata,
        }
        self.documents[identifier] = document
        self.originals[identifier] = content
        self.uploads.append((filename, content, metadata))
        if self.timeout_after_upload:
            self.timeout_after_upload = False
            raise StoreError("timeout", "weknora_timeout", 504)
        return copy.deepcopy(document)

    async def document(self, identifier):
        return copy.deepcopy(self.documents[identifier])

    async def original(self, identifier):
        return self.originals[identifier]

    async def documents_in_base(self, kb_id):
        return [copy.deepcopy(row) for row in self.documents.values() if row["kb_id"] == kb_id]


def service(tmp_path, upstream=None, *, account="account"):
    from app.research_web.knowledge_backend.sync import KnowledgeSyncService

    upstream = upstream or Upstream()
    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    account_root = tmp_path / account
    account_root.mkdir(mode=0o700, exist_ok=True)
    binding = {"origin": "https://knowledge.test", "user_id": "user1", "workspace_id": "101"}

    async def authorize():
        return upstream, dict(binding)

    result = KnowledgeSyncService(account_root, authorize, default_root=inbox)
    return result, upstream, inbox, binding


@pytest.mark.asyncio
async def test_two_stable_scans_publish_exact_bytes_and_restart_reuses_state(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "report.md").write_bytes(b"first original")
    await sync.configure("kb1", True)
    await sync.scan()
    assert sync.current_documents() == []
    await sync.scan()
    current = sync.current_documents()
    assert len(current) == 1
    assert current[0]["document_id"] == "d1"
    assert current[0]["version"] == 1
    assert current[0]["path"] == "report.md"
    assert sync.snapshot(current[0]["sha256"]) == b"first original"
    sync.close()
    resumed, _, _, _ = service(tmp_path, upstream)
    await resumed.scan()
    assert resumed.current_documents() == current
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_failed_new_version_keeps_old_current_and_history(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "report.txt"
    path.write_bytes(b"old")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    path.write_bytes(b"new")
    upstream.parse_status = "failed"
    await sync.scan()
    await sync.scan()
    assert sync.current_documents()[0]["document_id"] == "d1"
    assert sync.snapshot(sync.current_documents()[0]["sha256"]) == b"old"
    assert len(sync.history("report.txt")) == 2
    assert sync.status()["error_count"] == 1


@pytest.mark.asyncio
async def test_delete_withdraws_current_without_deleting_upstream_or_history(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "report.pdf"
    path.write_bytes(b"pdf original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    row = sync.current_documents()[0]
    path.unlink()
    await sync.scan()
    assert sync.current_documents() == []
    assert sync.history("report.pdf")[0]["document_id"] == row["document_id"]
    assert sync.snapshot(row["sha256"]) == b"pdf original"
    assert list(upstream.documents) == ["d1"]
    assert sync.status()["items"][0]["tombstone"] is True


@pytest.mark.asyncio
async def test_missing_root_and_partial_scan_never_withdraw_current(tmp_path, monkeypatch):
    sync, _, inbox, _ = service(tmp_path)
    path = inbox / "report.md"
    path.write_bytes(b"original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    current = sync.current_documents()
    moved = inbox.with_name("offline")
    inbox.rename(moved)
    assert (await sync.scan())["last_scan_result"] == "failed"
    assert sync.current_documents() == current
    moved.rename(inbox)
    from app.research_web.knowledge_backend import sync as module

    def broken_scandir(_fd):
        raise PermissionError("denied")

    monkeypatch.setattr(module.os, "scandir", broken_scandir)
    assert (await sync.scan())["last_scan_result"] == "failed"
    assert sync.current_documents() == current


@pytest.mark.asyncio
async def test_duplicate_and_rename_reuse_content_identity(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "a.txt"
    path.write_bytes(b"same original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    path.rename(inbox / "renamed.txt")
    (inbox / "copy.md").write_bytes(b"same original")
    await sync.scan()
    await sync.scan()
    assert {row["path"] for row in sync.current_documents()} == {"renamed.txt", "copy.md"}
    assert {row["document_id"] for row in sync.current_documents()} == {"d1"}
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_upload_timeout_reconciles_hash_and_kb_without_duplicate_upload(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.docx").write_bytes(b"original")
    upstream.timeout_after_upload = True
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    await sync.scan()
    assert len(upstream.uploads) == 1
    assert sync.current_documents()[0]["document_id"] == "d1"


@pytest.mark.asyncio
async def test_source_mutation_during_upload_never_promotes_stale_version(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "a.txt"
    path.write_bytes(b"old")
    await sync.configure("kb1", True)
    await sync.scan()
    upstream.on_upload = lambda: path.write_bytes(b"new")
    await sync.scan()
    assert sync.current_documents() == []
    assert upstream.uploads[0][1] == b"old"
    upstream.on_upload = None
    await sync.scan()
    await sync.scan()
    assert sync.snapshot(sync.current_documents()[0]["sha256"]) == b"new"


@pytest.mark.asyncio
async def test_hidden_temp_symlink_unsupported_and_large_files_are_not_uploaded(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / ".hidden.txt").write_bytes(b"hidden")
    (inbox / "~$draft.docx").write_bytes(b"temp")
    (inbox / "draft.tmp.txt").write_bytes(b"temp")
    (inbox / "image.png").write_bytes(b"png")
    (tmp_path / "outside.txt").write_bytes(b"outside")
    (inbox / "link.txt").symlink_to(tmp_path / "outside.txt")
    (inbox / "valid.txt").write_bytes(b"valid")
    with (inbox / "large.pdf").open("wb") as handle:
        handle.truncate(8 * 1024 * 1024 + 1)
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    assert [row[0] for row in upstream.uploads] == ["valid.txt"]


@pytest.mark.asyncio
async def test_pending_parse_is_polled_after_restart_without_reupload(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.md").write_bytes(b"original")
    upstream.parse_status = "processing"
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    assert sync.current_documents() == []
    sync.close()
    upstream.documents["d1"]["parse_status"] = "completed"
    resumed, _, _, _ = service(tmp_path, upstream)
    await resumed.scan()
    assert resumed.current_documents()[0]["document_id"] == "d1"
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_inbox_cannot_be_claimed_by_another_account(tmp_path):
    sync, upstream, _, _ = service(tmp_path)
    await sync.configure("kb1", True)
    other, _, _, _ = service(tmp_path, upstream, account="other")
    with pytest.raises(StoreError) as failure:
        await other.configure("kb1", True)
    assert failure.value.code == "knowledge_sync_source_bound"


@pytest.mark.asyncio
async def test_binding_change_and_other_root_cannot_leak_current(tmp_path):
    sync, _, inbox, binding = service(tmp_path)
    (inbox / "a.txt").write_bytes(b"original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    with pytest.raises(StoreError) as failure:
        await sync.configure("kb1", True, root=tmp_path)
    assert failure.value.code == "knowledge_sync_root_restricted"
    binding["user_id"] = "someone-else"
    assert not sync.matches_binding(binding)
    assert (await sync.scan())["last_error"] == "knowledge_sync_binding_changed"


@pytest.mark.asyncio
async def test_copied_state_is_rejected_by_account_owner(tmp_path):
    sync, upstream, _, _ = service(tmp_path)
    await sync.configure("kb1", True)
    sync.close()
    shutil.copytree(tmp_path / "account" / "knowledge-sync", tmp_path / "other" / "knowledge-sync")
    with pytest.raises(StoreError) as failure:
        service(tmp_path, upstream, account="other")
    assert failure.value.code == "knowledge_sync_owner_invalid"


def test_networkfree_diagnostic_does_not_create_lock_or_database(tmp_path):
    from app.research_web.knowledge_backend.sync import KnowledgeSyncService

    root = tmp_path / "empty-account"
    root.mkdir(mode=0o700)
    sync = KnowledgeSyncService(root)
    assert sync.status()["configured"] is False
    assert sync.preservation() is None
    assert list(root.iterdir()) == []


@pytest.mark.asyncio
async def test_authorization_revocation_stops_scan_and_pauses_auto_sync(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.txt").write_bytes(b"first")
    (inbox / "b.txt").write_bytes(b"second")
    await sync.configure("kb1", True)
    await sync.scan()

    async def revoked(_identifier):
        raise StoreError("denied", "weknora_auth_denied", 401)

    upstream.document = revoked
    status = await sync.scan()
    assert status["enabled"] is False
    assert status["last_error"] == "weknora_auth_denied"
    assert status["connectivity"] == "failed"
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_scan_deadline_is_reported_without_tombstones(tmp_path, monkeypatch):
    from app.research_web.knowledge_backend import sync as module

    sync, _, _, _ = service(tmp_path)
    await sync.configure("kb1", True)

    async def stalled():
        await asyncio.sleep(10)

    sync.authorize = stalled
    monkeypatch.setattr(module, "SCAN_TIMEOUT", 0.001)
    status = await sync.scan()
    assert status["last_error"] == "knowledge_sync_timeout"
    assert status["last_scan_result"] == "failed"


@pytest.mark.asyncio
async def test_maintenance_refusal_is_a_store_error_without_mutation(tmp_path, monkeypatch):
    from app.research_web.knowledge_backend import sync as module
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    sync, _, _, _ = service(tmp_path)
    await sync.configure("kb1", True)
    before = sync.preservation()

    def busy():
        raise MaintenanceBusy("maintenance")

    monkeypatch.setattr(module, "admission", busy)
    with pytest.raises(StoreError) as failure:
        await sync.scan()
    assert failure.value.code == "knowledge_maintenance_busy"
    assert sync.preservation() == before


@pytest.mark.asyncio
async def test_ineligible_supported_paths_expose_relative_reasons_and_scan_limits(tmp_path):
    sync, _, inbox, _ = service(tmp_path)
    (inbox / "empty.pdf").touch()
    with (inbox / "large.pdf").open("wb") as handle:
        handle.truncate(8 * 1024 * 1024 + 1)
    (tmp_path / "outside-secret.txt").write_bytes(b"outside")
    (inbox / "link.txt").symlink_to(tmp_path / "outside-secret.txt")
    await sync.configure("kb1", True)
    status = await sync.scan()
    reasons = {row["path"]: row["error"] for row in status["items"]}
    assert reasons == {
        "empty.pdf": "knowledge_sync_file_empty",
        "large.pdf": "knowledge_sync_file_too_large",
        "link.txt": "knowledge_sync_symlink_ignored",
    }
    assert status["skipped_count"] == 3
    assert status["limits"]["max_file_bytes"] == 8 * 1024 * 1024
    assert status["limits"]["max_scan_files"] == 1000
    assert status["limits"]["max_scan_bytes"] == 64 * 1024 * 1024
    assert status["limits"]["max_preservation_bytes"] == 256 * 1024 * 1024
    assert "outside-secret" not in str(status)


@pytest.mark.asyncio
async def test_skipped_status_list_is_bounded_and_existing_current_is_preserved(tmp_path):
    sync, _, inbox, _ = service(tmp_path)
    path = inbox / "previous.txt"
    path.write_bytes(b"original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    previous = sync.current_documents()
    path.write_bytes(b"")
    for index in range(130):
        (inbox / f"empty-{index}.txt").touch()
    status = await sync.scan()
    assert sync.current_documents() == previous
    assert status["skipped_count"] == 131
    assert len(status["skipped_items"]) == 128


@pytest.mark.asyncio
async def test_known_pending_document_recovers_from_transient_timeout_without_reupload(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.txt").write_bytes(b"original")
    upstream.parse_status = "processing"
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    original_document = upstream.document

    async def timeout(_identifier):
        raise StoreError("timeout", "weknora_timeout", 504)

    upstream.document = timeout
    await sync.scan()
    upstream.document = original_document
    upstream.documents["d1"]["parse_status"] = "completed"
    await sync.scan()
    assert sync.current_documents()[0]["document_id"] == "d1"
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_manual_scan_rechecks_failed_parse_without_reuploading_bad_bytes(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.txt").write_bytes(b"original")
    upstream.parse_status = "failed"
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    assert sync.status()["error_count"] == 1
    upstream.documents["d1"]["parse_status"] = "completed"
    await sync.scan()
    assert sync.current_documents() == []
    await sync.scan(force=True)
    assert sync.current_documents()[0]["document_id"] == "d1"
    assert len(upstream.uploads) == 1


@pytest.mark.asyncio
async def test_snapshot_capacity_refuses_new_bytes_and_preserves_current(tmp_path, monkeypatch):
    from app.research_web.knowledge_backend import sync_storage as module

    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "a.txt"
    path.write_bytes(b"accepted original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    current = sync.current_documents()
    monkeypatch.setattr(module, "MAX_DATABASE_BYTES", sync.store.path.stat().st_size + 48 * 1024)
    monkeypatch.setattr(module, "SQLITE_RESERVE_BYTES", 16 * 1024)
    path.write_bytes(b"n" * (40 * 1024))
    status = await sync.scan()
    assert status["last_error"] == "knowledge_sync_storage_budget"
    assert status["last_scan_result"] == "failed"
    assert sync.current_documents() == current
    assert sync.snapshot(current[0]["sha256"]) == b"accepted original"
    assert len(upstream.uploads) == 1
    assert len(sync.history("a.txt")) == 1
    assert sync.preservation() is not None


@pytest.mark.asyncio
async def test_pending_upload_is_not_starved_by_slow_current_audit(tmp_path, monkeypatch):
    from app.research_web.knowledge_backend import sync as module

    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a-current.txt").write_bytes(b"current")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    original_document = upstream.document

    async def slow_current(identifier):
        if identifier == "d1":
            await asyncio.sleep(0.1)
        return await original_document(identifier)

    upstream.document = slow_current
    monkeypatch.setattr(module, "SCAN_TIMEOUT", 0.02)
    (inbox / "z-new.txt").write_bytes(b"new")
    await sync.scan()
    await sync.scan()
    assert {row["path"] for row in sync.current_documents()} == {"a-current.txt", "z-new.txt"}


@pytest.mark.asyncio
async def test_pending_cursor_advances_after_deadline_and_survives_restart(tmp_path, monkeypatch):
    from app.research_web.knowledge_backend import sync as module

    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a-slow.txt").write_bytes(b"slow")
    (inbox / "b-ready.txt").write_bytes(b"ready")
    await sync.configure("kb1", True)
    await sync.scan()
    original_document = upstream.document

    async def slow_first(identifier):
        if identifier == "d1":
            await asyncio.sleep(0.1)
        return await original_document(identifier)

    upstream.document = slow_first
    monkeypatch.setattr(module, "SCAN_TIMEOUT", 0.02)
    await sync.scan()
    sync.close()
    resumed, _, _, _ = service(tmp_path, upstream)
    await resumed.scan()
    assert [row["path"] for row in resumed.current_documents()] == ["b-ready.txt"]
    assert len(upstream.uploads) == 2
