"""Real HTTP framing, private producer proof and owned-source completeness."""

import asyncio
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import test_scenario_handoffs as scenario_fixtures
from source_capture_fixture import fixed_response, offline_http

from app.research_web import research_web_sources as reader
from app.research_web.resources.research_report import source_id
from app.research_web.scenario_handoffs import resolve_reference
from app.research_web.scenario_pack_inputs import qualify_pack_materials
from app.research_web.store import StoreError

api = scenario_fixtures.api
URL = "https://capture.invalid/article"


def owned_read(api, monkeypatch, wire):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    identifier = source_id(URL)
    responses = offline_http(monkeypatch, wire)

    def perform():
        return asyncio.run(
            reader.read_source(
                service,
                sid,
                "read",
                identifier,
                search_activities=[
                    {
                        "id": "framing-search",
                        "title": "web_search",
                        "status": "completed",
                        "detail": json.dumps(
                            {"results": [{"title": "Offline framing", "url": URL}]}
                        ),
                    }
                ],
            )
        )

    return service, sid, identifier, perform, responses


def qualify(service, sid, identifier):
    metadata = resolve_reference(service, sid, {"type": "source", "id": identifier})[0]
    day = (
        datetime.fromisoformat(metadata["acquired_at"])
        .astimezone(ZoneInfo("Asia/Shanghai"))
        .date()
        .isoformat()
    )
    return qualify_pack_materials(
        service,
        "research-prep",
        {"as_of": day, "research_scope": {"cutoff_at": day + "T23:59:59+08:00"}},
        [metadata],
    )


def test_standard_response_early_eof_is_rejected_before_persistence(api, monkeypatch):
    service, sid, identifier, perform, responses = owned_read(
        api, monkeypatch, fixed_response(b"hello", length=100)
    )
    with pytest.raises(StoreError) as error:
        perform()
    assert error.value.code == "research_source_incomplete"
    assert responses[0].length == 95
    assert identifier not in service.store.session(sid).get("web_evidence", {})
    assert not (service.store.directory(sid) / ("inputs/web-" + identifier[4:] + ".txt")).exists()


@pytest.mark.parametrize("mode", ["length", "chunked", "eof"])
def test_complete_real_response_has_versioned_proof_and_exact_framing(api, monkeypatch, mode):
    body = b"hello captured bytes"
    wire = fixed_response(body)
    if mode == "chunked":
        wire = (
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n14\r\n"
            + body
            + b"\r\n0\r\n\r\n"
        )
    elif mode == "eof":
        wire = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n" + body
    service, sid, identifier, perform, _ = owned_read(api, monkeypatch, wire)
    actual = perform()
    saved = service.store.session(sid)["web_evidence"][identifier]
    assert saved["capture_schema"] == "research_web_capture_v1"
    proof_path = service.store.root / ".control/source-captures" / sid / (identifier[4:] + ".json")
    raw = proof_path.read_bytes()
    assert saved["capture_proof"] == {
        "schema": "research_web_capture_proof_v1",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    proof = json.loads(raw)
    assert (
        proof["producer"]["framing"]
        == {"length": "content_length", "chunked": "chunked_stdlib", "eof": "close_delimited_eof"}[
            mode
        ]
    )
    assert proof["producer"]["declared_length"] == (len(body) if mode == "length" else None)
    assert proof["producer"]["response_body_bytes"] == len(body)
    assert actual["content"].encode() == body
    result = qualify(service, sid, identifier)
    assert result.input["records_by_kind"]["source-version"][0]["full_text_available"] is True


@pytest.mark.parametrize("body", [b"5\r\nhe", b"5\r\nhello\r\n"])
def test_real_incomplete_chunked_is_not_saved(monkeypatch, body):
    offline_http(
        monkeypatch,
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n" + body,
    )
    with pytest.raises(StoreError):
        reader.fetch_document(URL)


@pytest.mark.parametrize("length", [b"-1", b"hello", b"5, 5"])
def test_unknown_or_invalid_declared_length_is_not_guessed(monkeypatch, length):
    offline_http(
        monkeypatch,
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: "
        + length
        + b"\r\n\r\nhello",
    )
    with pytest.raises(StoreError):
        reader.fetch_document(URL)


@pytest.mark.parametrize("damage", ["marker", "missing", "corrupt", "raw", "hash", "time", "scope"])
def test_capture_proof_or_body_changes_and_revocation_are_denied(api, monkeypatch, damage):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"complete capture")
    )
    perform()
    record = service.store.session(sid)["web_evidence"][identifier]
    proof = service.store.root / ".control/source-captures" / sid / (identifier[4:] + ".json")
    if damage == "marker":
        record.pop("capture_proof")
    elif damage == "missing":
        proof.unlink()
    elif damage == "corrupt":
        proof.write_bytes(b"corrupt proof")
    elif damage == "raw":
        (service.store.directory(sid) / record["path"]).write_bytes(b"changed body")
    elif damage == "hash":
        record["sha256"] = "f" * 64
    elif damage == "time":
        record["fetched_at"] = "2026-01-01T00:00:00Z"
    else:
        service.store.session(sid)["source_scope"] = ["uploads"]
    with pytest.raises(StoreError):
        resolve_reference(service, sid, {"type": "source", "id": identifier})
    # This is an original immutable URL cache, never a silent replacement fetch.
    monkeypatch.setattr(reader, "fetch_owned_document", lambda *_: pytest.fail("must not refetch"))
    with pytest.raises(StoreError):
        asyncio.run(reader.read_source(service, sid, "read", identifier))


def test_legacy_structurally_complete_source_is_readable_but_never_certified(api, monkeypatch):
    from copy import deepcopy

    client, service = api
    _, sid, identifier, perform, _ = owned_read(api, monkeypatch, fixed_response(b"legacy body"))
    perform()
    old = deepcopy(service.store.session(sid)["web_evidence"][identifier])
    old.pop("capture_schema")
    old.pop("capture_proof")
    legacy = client.post("/api/research/sessions", json={}).json()["id"]
    (service.store.directory(legacy) / old["path"]).write_bytes(b"legacy body")
    service.store.session(legacy)["files"][old["file_id"]] = old["path"]
    service.store.session(legacy)["web_evidence"] = {identifier: old}
    service.store.save()
    result = qualify(service, legacy, identifier)
    assert result.input["records_by_kind"]["source-version"][0]["full_text_available"] is False
    assert "source_capture_completeness_unknown" in {gap["code"] for gap in result.missing}
    monkeypatch.setattr(
        reader, "fetch_owned_document", lambda *_: pytest.fail("legacy must not refetch")
    )
    value = asyncio.run(reader.read_source(service, legacy, "read", identifier))
    assert value["content"] == "legacy body"
    assert "capture_proof" not in service.store.session(legacy)["web_evidence"][identifier]


def test_metadata_proof_validation_does_not_open_revoked_body(api, monkeypatch):
    service, sid, _, perform, _ = owned_read(api, monkeypatch, fixed_response(b"metadata proof"))
    perform()
    service.store.session(sid)["source_scope"] = ["uploads"]
    original_open = service.store.open_file
    monkeypatch.setattr(
        service.store, "open_file", lambda *_: pytest.fail("body opened before permission")
    )
    assert reader._stored_records(service.store, sid)
    assert reader.stored_sources(service.store, sid)[0]["state"] == "revoked"
    with pytest.raises(StoreError) as error:
        resolve_reference(service, sid, {"type": "source", "id": source_id(URL)})
    assert error.value.code == "dossier_source_revoked"
    monkeypatch.setattr(service.store, "open_file", original_open)


def test_capture_proof_only_real_preservation_and_exact_restore(api, monkeypatch, tmp_path_factory):
    import shutil

    from test_workbench_operations import NativeFixture

    from app.research_web.dossier_preservation import snapshot_dossiers
    from app.research_web.multiuser.preservation import compare_snapshot, snapshot
    from app.research_web.service import ResearchService
    from app.research_web.store import Store
    from research_workbench_entrypoint.resident.model_provider_upgrade import asset_index_snapshot

    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"restore exact body")
    )
    perform()
    root = service.store.root
    assert not (root / "dossiers").exists()
    path = f".control/source-captures/{sid}/{identifier[4:]}.json"
    before = snapshot(root)
    assert path in before["files"]
    assert snapshot_dossiers(root, create_lock=False)["schema_version"] == 1
    assert not (root / "dossiers").exists()
    home = tmp_path_factory.mktemp("proof-restored-home")
    (home / "server/users").mkdir(parents=True)
    restored = home / "research-web"
    if restored == root or restored.is_relative_to(root):
        raise AssertionError("restore destination must be outside source")
    restored.mkdir(mode=0o700)
    for name in ("index.json", ".dossier-retention.lock"):
        shutil.copy2(root / name, restored / name)
    for name in ("sessions", ".control/source-captures"):
        (restored / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copytree(root / name, restored / name)
    assert (restored / path).read_bytes() == (root / path).read_bytes()
    assert compare_snapshot(before, snapshot(restored))["preserved"]
    resident_before = asset_index_snapshot(home)
    assert "@dossiers" in resident_before["primary"]
    recovered = ResearchService(NativeFixture(), Store(restored))
    _, actual = recovered.dossiers._resolve(sid, {"type": "source", "id": identifier})
    assert actual == b"restore exact body"
    from research_workbench_entrypoint.resident.evidence import UpdateBlocked

    source_record = recovered.store.session(sid)["web_evidence"][identifier]
    body_path = restored / "sessions" / sid / source_record["path"]
    body_path.write_bytes(b"body-only change")
    with pytest.raises(RuntimeError):
        snapshot(restored)
    with pytest.raises(UpdateBlocked, match="dossier_preservation_failed"):
        asset_index_snapshot(home)
    body_path.write_bytes(actual)
    assert asset_index_snapshot(home) == resident_before
    (restored / path).unlink()
    with pytest.raises(StoreError):
        recovered.dossiers._resolve(sid, {"type": "source", "id": identifier})
    with pytest.raises(RuntimeError):
        snapshot(restored)
    with pytest.raises(UpdateBlocked, match="dossier_preservation_failed"):
        asset_index_snapshot(home)
    (restored / path).write_bytes((root / path).read_bytes())
    (restored / path).chmod(0o600)
    assert recovered.dossiers._resolve(sid, {"type": "source", "id": identifier})[1] == actual
    (restored / path).write_bytes(b"corrupt")
    with pytest.raises(StoreError):
        recovered.dossiers._resolve(sid, {"type": "source", "id": identifier})
    assert service.dossiers._resolve(sid, {"type": "source", "id": identifier})[1] == actual


@pytest.mark.parametrize("failure", ["proof_write", "index_publish"])
def test_atomic_publish_failure_does_not_publish_or_overwrite_capture(api, monkeypatch, failure):
    service, sid, identifier, perform, responses = owned_read(
        api, monkeypatch, fixed_response(b"never partial success")
    )
    original_write, original_save = reader.write_new, service.store.save
    if failure == "proof_write":

        def write(fd, name, raw):
            if name == identifier[4:] + ".json":
                raise StoreError("test proof write failure")
            return original_write(fd, name, raw)

        monkeypatch.setattr(reader, "write_new", write)
    else:

        def save():
            if identifier in service.store.session(sid).get("web_evidence", {}):
                raise StoreError("test index publish failure")
            return original_save()

        monkeypatch.setattr(service.store, "save", save)
    with pytest.raises(StoreError):
        perform()
    assert identifier not in service.store.session(sid).get("web_evidence", {})
    from app.research_web.store import Store

    assert identifier not in Store(service.store.root).session(sid).get("web_evidence", {})
    proof = service.store.root / ".control/source-captures" / sid / (identifier[4:] + ".json")
    previous = proof.read_bytes() if proof.exists() else None
    monkeypatch.setattr(reader, "write_new", original_write)
    monkeypatch.setattr(service.store, "save", original_save)
    if previous is not None:
        with pytest.raises(StoreError):
            perform()
        assert proof.read_bytes() == previous
        assert len(responses) == 1  # no silent fetch to replace the orphan proof
        assert identifier not in service.store.session(sid).get("web_evidence", {})
    else:
        # Nothing durable was published; a separate explicit retry may create
        # its first capture, without replacing any old proof or body.
        assert perform()["content"] == "never partial success"


def test_purge_removes_only_retired_session_proof(api, monkeypatch):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"purge own proof")
    )
    perform()
    _, second, _, perform_second, _ = owned_read(api, monkeypatch, fixed_response(b"another proof"))
    perform_second()
    proof = service.store.root / ".control/source-captures" / second / (identifier[4:] + ".json")
    saved = proof.read_bytes()
    service.store.soft_delete(sid)
    service.store.mark_native_deleted(sid)
    service.store.purge(sid)
    assert not (service.store.root / ".control/source-captures" / sid).exists()
    assert proof.read_bytes() == saved
    assert (
        service.dossiers._resolve(second, {"type": "source", "id": identifier})[1]
        == b"another proof"
    )


def test_size_limits_stay_bounded_before_decoding(monkeypatch):
    offline_http(monkeypatch, fixed_response(b"hello", length=100))
    monkeypatch.setattr(reader, "MAX_BYTES", 4)
    with pytest.raises(StoreError) as error:
        reader.fetch_document(URL)
    assert error.value.code == "research_source_size_limit"


def test_transfer_body_and_extracted_utf8_are_separately_bound(monkeypatch):
    body = b"<p>caf\xe9</p>"
    wire = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=cp1252\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body
    )
    offline_http(monkeypatch, wire)
    document = reader.fetch_document(URL)
    producer = document["capture"]
    assert document["content"] == "caf\u00e9"
    assert producer["response_body_bytes"] == len(body)
    assert producer["utf8_bytes"] == len("caf\u00e9".encode())
    assert producer["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert producer["content_sha256"] == hashlib.sha256("caf\u00e9".encode()).hexdigest()


@pytest.mark.parametrize("damage", [None, "missing", "hash"])
def test_real_worker_json_protocol_keeps_and_validates_producer(monkeypatch, damage):
    real_parent = reader.fetch_owned_document
    offline_http(monkeypatch, fixed_response(b"worker round trip"))
    invoked = []

    class Worker:
        returncode = 0

        async def communicate(self, incoming):
            request = json.loads(incoming)
            assert request == {"url": URL}
            document = reader.fetch_document(request["url"])
            if damage == "missing":
                document.pop("capture")
            elif damage == "hash":
                document["capture"]["content_sha256"] = "f" * 64
            return reader.worker_document_bytes(document), b""

    async def create(*args, **kwargs):
        invoked.append(args)
        assert args[1:] == ("-m", "app.research_web.research_web_sources")
        return Worker()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    if damage is None:
        document = asyncio.run(real_parent(URL))
        assert (
            document["capture"]["content_sha256"]
            == hashlib.sha256(b"worker round trip").hexdigest()
        )
    else:
        with pytest.raises(StoreError) as error:
            asyncio.run(real_parent(URL))
        assert error.value.code == "research_source_capture_unverified"
    assert len(invoked) == 1
