"""Failed/crashed web captures never become uploaded-file authority."""

import hashlib

import pytest
import test_source_capture_proof as source_fixtures
from source_capture_fixture import fixed_response
from test_source_capture_proof import owned_read

from app.research_web import research_web_sources as reader
from app.research_web.store import StoreError

api = source_fixtures.api


def file_alias_denied(api, service, sid, identifier):
    client = api[0]
    relative = "inputs/web-" + identifier[4:] + ".txt"
    fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
    service.store.files(sid)
    # Even stale indexes from a previous process cannot authorize the alias.
    service.store.session(sid)["files"][fid] = relative
    for scope in (["uploads"], ["uploads", "web"]):
        service.store.session(sid)["source_scope"] = scope
        with pytest.raises(StoreError):
            service.dossiers._resolve(sid, {"type": "file", "id": relative})
        for action in ("preview", "download"):
            assert client.get(f"/api/research/sessions/{sid}/files/{fid}/{action}").status_code in {
                403,
                409,
            }
        target = client.post("/api/research/sessions", json={}).json()["id"]
        response = client.post(
            f"/api/research/sessions/{target}/file-references",
            json={
                "source_session_id": sid,
                "file_id": fid,
                "expected_sha256": hashlib.sha256(b"orphan source body").hexdigest(),
            },
        )
        assert response.status_code in {403, 409}
    assert not any(item["id"] == fid for item in service.store.files(sid))


def test_body_sync_failure_rolls_back_owned_body(api, monkeypatch):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"orphan source body")
    )
    original = reader.sync_directory
    calls = []

    def sync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise StoreError("injected body directory sync failure")
        return original(fd)

    monkeypatch.setattr(reader, "sync_directory", sync)
    with pytest.raises(StoreError):
        perform()
    assert identifier not in service.store.session(sid).get("web_evidence", {})
    assert not (service.store.directory(sid) / ("inputs/web-" + identifier[4:] + ".txt")).exists()


@pytest.mark.parametrize("proof_damage", ["valid", "missing", "corrupt"])
def test_real_crash_orphan_is_denied_even_with_web_permission(api, monkeypatch, proof_damage):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"orphan source body")
    )
    perform()
    service.store.session(sid)["web_evidence"].pop(identifier)
    proof = service.store.root / ".control/source-captures" / sid / (identifier[4:] + ".json")
    if proof_damage == "missing":
        proof.unlink()
    elif proof_damage == "corrupt":
        proof.write_bytes(b"bad")
    service.store.save()
    file_alias_denied(api, service, sid, identifier)


def test_cleanup_failure_still_does_not_create_upload_authority(api, monkeypatch):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"orphan source body")
    )
    original = reader.sync_directory
    calls = []

    def sync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise StoreError("injected body directory sync failure")
        return original(fd)

    def unlink(*_args):
        raise StoreError("injected cleanup failure")

    monkeypatch.setattr(reader, "sync_directory", sync)
    monkeypatch.setattr(reader, "unlink_file", unlink)
    with pytest.raises(StoreError):
        perform()
    monkeypatch.setattr(reader, "sync_directory", original)
    assert (service.store.directory(sid) / ("inputs/web-" + identifier[4:] + ".txt")).exists()
    file_alias_denied(api, service, sid, identifier)


@pytest.mark.parametrize("stage", ["write", "readback", "index"])
def test_postproof_failures_remove_only_this_exclusive_body(api, monkeypatch, stage):
    service, sid, identifier, perform, responses = owned_read(
        api, monkeypatch, fixed_response(b"orphan source body")
    )
    if stage == "write":
        original = reader._write_capture_body

        def write(folder, name, raw, ownership):
            original(folder, name, raw, ownership)
            raise StoreError("injected post-create write failure")

        monkeypatch.setattr(reader, "_write_capture_body", write)
    elif stage == "readback":
        original = reader.read_file

        def read(fd, name, **kwargs):
            return b"wrong readback" if name.startswith("web-") else original(fd, name, **kwargs)

        monkeypatch.setattr(reader, "read_file", read)
    else:
        original = service.store.save

        def save():
            if identifier in service.store.session(sid).get("web_evidence", {}):
                raise StoreError("injected index failure")
            return original()

        monkeypatch.setattr(service.store, "save", save)
    with pytest.raises(StoreError):
        perform()
    assert identifier not in service.store.session(sid).get("web_evidence", {})
    assert not (service.store.directory(sid) / ("inputs/web-" + identifier[4:] + ".txt")).exists()
    assert (
        service.store.root / ".control/source-captures" / sid / (identifier[4:] + ".json")
    ).exists()
    with pytest.raises(StoreError):
        perform()
    assert len(responses) == 1


def test_exclusive_create_failure_never_deletes_preexisting_file(api, monkeypatch):
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"orphan source body")
    )
    path = service.store.directory(sid) / ("inputs/web-" + identifier[4:] + ".txt")
    path.write_bytes(b"pre-existing object")
    before = path.stat()
    with pytest.raises(StoreError):
        perform()
    assert path.read_bytes() == b"pre-existing object"
    assert (path.stat().st_dev, path.stat().st_ino) == (before.st_dev, before.st_ino)
    assert identifier not in service.store.session(sid).get("web_evidence", {})


def test_published_source_and_real_uuid_upload_keep_original_authority(api, monkeypatch):
    client = api[0]
    service, sid, identifier, perform, _ = owned_read(
        api, monkeypatch, fixed_response(b"published source body")
    )
    perform()
    source = service.store.session(sid)["web_evidence"][identifier]
    for action in ("preview", "download"):
        response = client.get(f"/api/research/sessions/{sid}/files/{source['file_id']}/{action}")
        assert response.status_code == 200 and response.content == b"published source body"
    assert (
        service.dossiers._resolve(sid, {"type": "source", "id": identifier})[1]
        == b"published source body"
    )
    with pytest.raises(StoreError):
        service.dossiers._resolve(sid, {"type": "file", "id": source["path"]})
    service.store.session(sid)["source_scope"] = ["uploads"]
    assert (
        client.get(f"/api/research/sessions/{sid}/files/{source['file_id']}/download").status_code
        == 403
    )
    response = client.post(
        f"/api/research/sessions/{sid}/uploads",
        files={"files": ("web-" + identifier[4:] + ".md", b"ordinary upload", "text/markdown")},
    )
    assert response.status_code == 200, response.text
    uploaded = response.json()["items"][0]
    relative = service.store.session(sid)["files"][uploaded["id"]]
    assert not reader.source_file_identifier(service.store.session(sid), relative)
    assert client.get(uploaded["url"]).content == b"ordinary upload"
    assert service.dossiers._resolve(sid, {"type": "file", "id": relative})[1] == b"ordinary upload"
    target = client.post("/api/research/sessions", json={}).json()["id"]
    copied = client.post(
        f"/api/research/sessions/{target}/file-references",
        json={
            "source_session_id": sid,
            "file_id": uploaded["id"],
            "expected_sha256": hashlib.sha256(b"ordinary upload").hexdigest(),
        },
    )
    assert copied.status_code == 201, copied.text
