"""Real local evidence IO with deterministic upstream permission failures, no models."""

import copy
import hashlib

import pytest

from app.research_web.knowledge_backend import models
from app.research_web.knowledge_backend.diagnostics import knowledge_diagnostic
from app.research_web.knowledge_backend.service import KnowledgeService
from app.research_web.knowledge_backend.storage import KnowledgeStore
from app.research_web.store import Store, StoreError


class Credentials:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


class Upstream:
    def __init__(self):
        self.active = True
        self.user = "user-a"
        self.original_bytes = b"original approved public research document"
        self.calls = []
        self.hit = {
            "chunk_id": "c1",
            "document_id": "d1",
            "kb_id": "kb1",
            "title": "Source",
            "content": "A cited paragraph",
            "chunk_index": 0,
            "start_at": 0,
            "end_at": 17,
        }
        self.download_allowed = True

    def factory(self, origin, token, workspace_id):
        assert origin == "https://knowledge.example.test"
        assert token.startswith("user-jwt-")
        assert workspace_id == "101"
        return self

    async def identity(self):
        self.calls.append("identity")
        if not self.active:
            raise StoreError("denied", "weknora_auth_denied", 403)
        return {"user_id": self.user, "workspace_id": "101", "role": "owner"}

    async def knowledge_bases(self):
        return [{"id": "kb1", "name": "Library"}]

    async def document(self, identifier):
        self.calls.append(("document", identifier))
        return {
            "id": identifier,
            "kb_id": "kb1",
            "title": "Source",
            "parse_status": "completed",
            "enable_status": "enabled",
            "file_hash": hashlib.md5(self.original_bytes).hexdigest(),
        }

    async def original(self, identifier):
        self.calls.append(("original", identifier))
        if not self.download_allowed:
            raise StoreError("denied", "weknora_scope_denied", 403)
        return self.original_bytes

    async def search(self, query, kb_ids, document_ids, limit):
        self.calls.append(("search", query, kb_ids, document_ids, limit))
        return [copy.deepcopy(self.hit)]

    async def chunks(self, identifier):
        return [copy.deepcopy(self.hit)]


@pytest.fixture
async def knowledge(tmp_path):
    upstream = Upstream()
    credentials = Credentials()
    service = KnowledgeService(
        Store(tmp_path / "owner-a"),
        credentials=credentials,
        client_factory=upstream.factory,
        origin="https://knowledge.example.test",
    )
    await service.bind("user-jwt-a", "101")
    return service, upstream, credentials


def approved():
    return models.Scope(
        report_period="2026-10-30",
        cutoff="2026-10-30T23:59:59+08:00",
        confirm_source_times=True,
        documents=[
            models.SourceApproval(
                document_id="d1",
                available_at="2026-10-28T09:00:00+08:00",
                time_evidence="operator reviewed dated original publication",
            )
        ],
    )


@pytest.mark.asyncio
async def test_report_scope_injected_before_query_and_original_hashed(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    assert scope["documents"][0]["sha256"] == hashlib.sha256(upstream.original_bytes).hexdigest()
    upstream.calls.clear()
    result = await service.search(
        models.Search(query="question", knowledge_base_ids=["kb1"], scope_id=scope["id"])
    )
    assert result["generated_answer"] is False
    call = ("search", "question", ["kb1"], ["d1"], 8)
    assert call in upstream.calls
    assert upstream.calls.index(("original", "d1")) < upstream.calls.index(call)


@pytest.mark.asyncio
async def test_future_material_rejected_before_any_upstream(knowledge):
    service, upstream, _ = knowledge
    body = approved()
    body.documents[0].available_at = "2026-11-01T09:00:00+08:00"
    upstream.calls.clear()
    with pytest.raises(StoreError, match="资料操作") as error:
        await service.create_scope(body)
    assert error.value.code == "knowledge_source_after_cutoff"
    assert upstream.calls == []


def test_unknown_or_naive_time_is_not_an_upload_date_fallback():
    with pytest.raises(ValueError):
        models.SourceApproval(
            document_id="d1", available_at="2026-10-30", time_evidence="unknown time"
        )
    with pytest.raises(ValueError):
        models.Search(query="q", knowledge_base_ids=["kb1"], document_ids=[])


@pytest.mark.asyncio
async def test_explicit_source_time_approval_is_required(knowledge):
    service, _, _ = knowledge
    body = approved()
    body.confirm_source_times = False
    with pytest.raises(StoreError) as error:
        await service.create_scope(body)
    assert error.value.code == "knowledge_source_approval_required"


@pytest.mark.asyncio
async def test_revocation_denies_every_new_operation(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    upstream.active = False
    for operation in (
        service.bases(),
        service.read(models.Read(document_id="d1")),
        service.search(models.Search(query="q", knowledge_base_ids=["kb1"])),
        service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]})),
    ):
        with pytest.raises(StoreError) as error:
            await operation
        assert error.value.status == 403


@pytest.mark.asyncio
async def test_identity_change_cannot_reuse_scope(knowledge):
    service, upstream, _ = knowledge
    await service.create_scope(approved())
    upstream.user = "user-b"
    with pytest.raises(StoreError) as error:
        await service.bases()
    assert error.value.code == "knowledge_identity_changed"


@pytest.mark.asyncio
async def test_report_cannot_request_another_document_or_library(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    for args in ({"document_ids": ["other"]}, {"knowledge_base_ids": ["other"]}):
        upstream.calls.clear()
        with pytest.raises(StoreError):
            await service.search(
                models.Search(
                    query="q", scope_id=scope["id"], **{"knowledge_base_ids": ["kb1"], **args}
                )
            )
        assert not any(isinstance(call, tuple) and call[0] == "search" for call in upstream.calls)


@pytest.mark.asyncio
async def test_original_changes_refuse_search_and_freeze(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    upstream.original_bytes = b"updated after report cutoff"
    with pytest.raises(StoreError) as error:
        await service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]}))
    assert error.value.code == "knowledge_original_changed"


@pytest.mark.asyncio
async def test_upstream_scope_violation_does_not_leak_hits(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())

    async def leaking_search(*_args, **_kwargs):
        return [{**upstream.hit, "document_id": "future-document"}]

    upstream.search = leaking_search
    with pytest.raises(StoreError) as error:
        await service.search(
            models.Search(query="q", knowledge_base_ids=["kb1"], scope_id=scope["id"])
        )
    assert error.value.code == "knowledge_upstream_scope_violation"


@pytest.mark.asyncio
async def test_shared_viewer_download_denied_without_escalation(knowledge):
    service, upstream, _ = knowledge
    upstream.download_allowed = False
    assert (await service.read(models.Read(document_id="d1")))["chunks"]
    with pytest.raises(StoreError) as error:
        await service.create_scope(approved())
    assert error.value.code == "weknora_scope_denied"


@pytest.mark.asyncio
async def test_freeze_survives_upstream_deletion_and_is_idempotent(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    body = models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]})
    evidence = await service.freeze(body)
    assert (await service.freeze(body))["id"] == evidence["id"]
    upstream.active = False
    restored = KnowledgeStore(service.store.root)
    assert (
        restored.read("evidence", evidence["id"])["excerpts"][0]["content"] == "A cited paragraph"
    )
    assert (
        restored.original(evidence["id"], evidence["documents"][0]["sha256"])
        == upstream.original_bytes
    )


@pytest.mark.asyncio
async def test_corrupt_frozen_original_never_reads_as_valid(knowledge):
    service, _, _ = knowledge
    scope = await service.create_scope(approved())
    evidence = await service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]}))
    path = (
        service.store.root
        / "knowledge-backend"
        / "evidence"
        / evidence["id"]
        / (evidence["documents"][0]["sha256"] + ".bin")
    )
    path.write_bytes(b"tampered")
    with pytest.raises(StoreError):
        service.store.read("evidence", evidence["id"])


@pytest.mark.asyncio
async def test_account_roots_have_separate_credentials_and_evidence(knowledge, tmp_path):
    service, upstream, credentials = knowledge
    other = KnowledgeService(
        Store(tmp_path / "owner-b"),
        credentials=credentials,
        client_factory=upstream.factory,
        origin=service.origin,
    )
    assert not other.status()["configured"]
    await other.bind("user-jwt-b", "101")
    assert service.namespace != other.namespace
    assert len(credentials.values) == 2
    scope = await service.create_scope(approved())
    with pytest.raises(StoreError):
        other.store.read("scopes", scope["id"])


def test_doctor_and_status_never_read_secrets_or_create_backend(tmp_path):
    store = Store(tmp_path / "owner")
    assert knowledge_diagnostic(store.root)["state"] == "unconfigured"
    assert not (store.root / "knowledge-backend").exists()
    service = KnowledgeService(store, origin="")
    assert service.status()["live_acceptance"] == "NOT_RUN"


@pytest.mark.asyncio
async def test_symlinked_backend_is_rejected_without_following(knowledge, tmp_path):
    _service, _, _ = knowledge
    folder = tmp_path / "attacker"
    folder.mkdir()
    (folder / "binding.json").write_text("{}")
    other = Store(tmp_path / "other-owner")
    link = other.root / "knowledge-backend"
    link.symlink_to(folder, target_is_directory=True)
    try:
        with pytest.raises(StoreError):
            KnowledgeService(other).status()
    finally:
        link.unlink()


@pytest.mark.asyncio
async def test_revocation_during_freeze_prevents_local_commit(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    previous = upstream.chunks

    async def revoked_after_read(identifier):
        result = await previous(identifier)
        upstream.active = False
        return result

    upstream.chunks = revoked_after_read
    with pytest.raises(StoreError) as error:
        await service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]}))
    assert error.value.status == 403
    assert not (service.store.root / "knowledge-backend/evidence").exists()


@pytest.mark.asyncio
async def test_failed_old_credential_retirement_is_explicit_and_recoverable(knowledge):
    service, _, credentials = knowledge
    old_ref = service.store.binding()["credential_ref"]

    def denied(_service, _account):
        raise RuntimeError("synthetic credential retirement denied")

    credentials.delete_password = denied
    status = await service.bind("user-jwt-replacement", "101")
    assert status["configured"] is True
    assert status["credential_cleanup_pending"] is True
    assert service.store.binding()["retained_credentials"] == [old_ref]
