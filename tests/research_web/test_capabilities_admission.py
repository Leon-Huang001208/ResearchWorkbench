"""Package selection, immutable resources and native activity serialization."""

import asyncio
import hashlib
import json
import os
import zipfile

import pytest
from test_api import NativeFixture
from test_capabilities import api as api_fixture
from test_capabilities import candidate, create

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError
from app.research_web.service import ResearchService
from app.research_web.store import Store

api = api_fixture


def test_pre_capability_receipt_still_replays_without_model(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    old_payload = {"text": "既有问题", "attachments": [], "skill": None, "expected_formats": []}
    digest = hashlib.sha256(json.dumps(old_payload, sort_keys=True).encode()).hexdigest()
    service.store.reserve(sid, "legacy-receipt", digest)
    service.store.receipt(sid, "legacy-receipt", "accepted")
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "既有问题"},
        headers={"Idempotency-Key": "legacy-receipt"},
    )
    assert response.status_code == 202
    assert not any(method == "session.prompt" for method, _ in native.calls)


def discovery(native, service):
    original = native.rpc

    async def rpc(method, payload):
        if method == "skill.list":
            return {
                "skills": [
                    {"name": row["native_name"]}
                    for row in service.capabilities.list()["items"]
                    if row["enabled"]
                ]
            }
        return await original(method, payload)

    native.rpc = rpc


@pytest.mark.parametrize("formats,required", [(None, ["md"]), ([], []), (["html"], ["html"])])
def test_selected_version_snapshot_formats_and_receipt(api, formats, required):
    client, native, service = api
    row = create(client)
    cid = row["id"]
    client.post(f"/api/research/capabilities/{cid}/publish")
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    discovery(native, service)
    payload = {
        "text": "开展研究",
        "capability_id": cid,
        "capability_version": 1,
        "tool_ids": ["af_run_script"],
    }
    if formats is not None:
        payload["expected_formats"] = formats
    result = client.post(
        f"/api/research/sessions/{sid}/messages",
        json=payload,
        headers={"Idempotency-Key": "capability-request"},
    )
    assert result.status_code == 202, result.text
    receipt = service.store.receipt(sid, "capability-request")
    assert receipt["delivery"]["required_formats"] == required
    selected = receipt["capability"]
    file = service.store.directory(sid) / selected["resource_path"] / "templates/report.md"
    assert file.read_text() == "# 研究报告"
    assert file.stat().st_mode & 0o222 == 0
    prompt = next(value for method, value in native.calls if method == "session.prompt")["content"][
        0
    ]["text"]
    assert prompt.startswith(f"/{selected['native_name']} ")
    assert selected["resource_path"] in prompt
    detail = client.get(f"/api/research/sessions/{sid}").json()
    assert detail["capability"]["version"] == 1


def test_cross_session_snapshot_and_disabled_idempotency(api):
    client, native, service = api
    row = create(client)
    cid = row["id"]
    client.post(f"/api/research/capabilities/{cid}/publish")
    discovery(native, service)
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    other = client.post("/api/research/sessions", json={}).json()["id"]
    payload = {
        "text": "问题",
        "capability_id": cid,
        "capability_version": 1,
        "expected_formats": [],
    }
    endpoint = f"/api/research/sessions/{sid}/messages"
    assert (
        client.post(endpoint, json=payload, headers={"Idempotency-Key": "old-request"}).status_code
        == 202
    )
    selected = service.store.receipt(sid, "old-request")["capability"]
    assert not (service.store.directory(other) / selected["resource_path"]).exists()
    # Simulate a later successfully completed turn and a management disable.
    service.capabilities.transition(cid, "disable")
    assert (
        client.post(endpoint, json=payload, headers={"Idempotency-Key": "old-request"}).status_code
        == 202
    )
    assert (
        client.post(
            endpoint.replace(sid, other), json=payload, headers={"Idempotency-Key": "new-request"}
        ).status_code
        == 409
    )
    assert (service.store.directory(sid) / selected["resource_path"] / "SKILL.md").is_file()


@pytest.mark.parametrize("state", ["parent", "child", "diagnostic", "disconnected", "unknown"])
def test_mutations_block_on_parent_child_uncertain_but_draft_is_retained(api, state):
    client, native, service = api
    row = create(client)
    cid = row["id"]
    client.post(f"/api/research/capabilities/{cid}/publish")
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    original = native.rpc

    async def rpc(method, payload):
        if method == "session.list" and state == "parent":
            return {"items": [{"sessionId": sid, "running": True}]}
        if method == "subagent.list" and state in {"child", "diagnostic"}:
            return {
                "entries": [
                    {
                        "id": "child",
                        "kind": "child" if state == "child" else "diagnostic",
                        "activity": "running",
                    }
                ]
            }
        return await original(method, payload)

    native.rpc = rpc
    if state == "disconnected":
        service.connected.clear()
    if state == "unknown":
        service.store.reserve(sid, "unknown", "digest")
    changed = candidate()
    changed["instructions"] += "\n待发布新指令。"
    base = f"/api/research/capabilities/{cid}"
    assert client.patch(base + "/draft", json=changed).status_code == 200
    for action in ("publish", "disable", "enable", "rollback"):
        response = client.post(
            base + "/" + action, json={"version": 1} if action == "rollback" else None
        )
        assert response.status_code == 409, response.text
    assert client.get(base).json()["draft"]["instructions"] == changed["instructions"]


@pytest.mark.asyncio
async def test_send_and_publication_use_same_mutex(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    service.connected = {"mux", "host"}
    row = service.capabilities.create(candidate())
    cid = row["id"]
    await service.change_capability(cid, "publish")
    sid = (await service.create())["id"]
    discovery(native, service)
    original = native.rpc
    entered, release = asyncio.Event(), asyncio.Event()

    async def rpc(method, payload):
        if method == "session.prompt":
            entered.set()
            await release.wait()
        return await original(method, payload)

    native.rpc = rpc
    sending = asyncio.create_task(
        service.send(
            sid, "研究", "race-request", formats=[], capability_id=cid, capability_version=1
        )
    )
    await asyncio.wait_for(entered.wait(), 2)
    changing = asyncio.create_task(service.change_capability(cid, "disable"))
    await asyncio.sleep(0)
    assert not changing.done()
    release.set()
    await sending
    with pytest.raises(CapabilityError, match="尚未确认"):
        await changing
    assert service.capabilities.row(cid)["status"] == "enabled"


def test_publication_io_failure_keeps_old_mapping_or_blocks(api, monkeypatch):
    client, _, service = api
    row = create(client)
    cid = row["id"]
    base = f"/api/research/capabilities/{cid}"
    first = client.post(base + "/publish").json()
    client.patch(base + "/draft", json=candidate())
    original = os.replace

    def denied(source, destination):
        if str(destination).endswith(f"af-{cid}-v2"):
            raise OSError("simulated native rename failure")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", denied)
    assert client.post(base + "/publish").status_code == 503
    assert (service.capabilities.native_root / first["native_name"] / "SKILL.md").is_file()
    assert service.capabilities.row(cid)["version"] == 1
    assert service.capabilities.row(cid)["has_draft"]
    restored = CapabilityCatalog(service.store.root)
    assert restored.row(cid)["version"] == 1 or restored.data["pending"]


def test_creation_session_actual_artifacts_to_draft_no_auto_execute(api):
    client, native, service = api
    created = client.post(
        "/api/research/capabilities/creation-sessions",
        json={"kind": "skill", "goal": "研究上传资料"},
    )
    assert created.status_code == 201, created.text
    assert not created.json()["auto_submitted"] and not created.json()["auto_published"]
    assert not any(method == "session.prompt" for method, _ in native.calls)
    sid = created.json()["id"]
    assert client.get(f"/api/research/sessions/{sid}").json()["purpose"] == "capability_creation"
    output = service.store.directory(sid) / "outputs"
    (output / "SKILL.md").write_text(candidate()["instructions"])
    (output / "capability.json").write_text(json.dumps(candidate()["metadata"]))
    fid = next(f["id"] for f in service.store.files(sid) if f["name"] == "SKILL.md")
    response = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert response.status_code == 201, response.text
    assert response.json()["source"] == "conversation" and response.json()["status"] == "draft"
    assert response.json()["version"] is None
    assert response.json()["origin"]["session_id"] == sid
    other = client.post("/api/research/sessions", json={}).json()["id"]
    assert (
        client.post(
            "/api/research/capabilities/from-artifact", json={"session_id": other, "file_id": fid}
        ).status_code
        == 409
    )


def test_tampered_version_resource_refuses_snapshot(api):
    client, native, service = api
    row = create(client)
    cid = row["id"]
    client.post(f"/api/research/capabilities/{cid}/publish")
    source = service.capabilities.version_path(cid, 1) / "templates/report.md"
    source.chmod(0o600)
    source.write_text("tampered")
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    discovery(native, service)
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "研究", "capability_id": cid, "capability_version": 1},
        headers={"Idempotency-Key": "tampered-version"},
    )
    assert response.status_code == 503
    assert not any(method == "session.prompt" for method, _ in native.calls)


def test_native_auto_skill_resources_are_snapshotted_before_plain_send(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    result = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "解读我的资料"},
        headers={"Idempotency-Key": "native-auto-skill"},
    )
    assert result.status_code == 202
    root = service.store.directory(sid)
    assert (root / "resources/capabilities/document-reading/1/templates/report.md").is_file()
    assert len(service.store.receipt(sid, "native-auto-skill")["capability_catalog"]) == 6


def test_creation_zip_is_scoped_downloadable_and_importable(api):
    client, _, service = api
    sid = client.post(
        "/api/research/capabilities/creation-sessions", json={"goal": "生成候选包"}
    ).json()["id"]
    output = service.store.directory(sid) / "outputs" / "candidate.zip"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("SKILL.md", candidate()["instructions"])
        archive.writestr("capability.json", json.dumps(candidate()["metadata"]))
    files = client.get(f"/api/research/sessions/{sid}/files").json()["items"]
    assert len(files) == 1 and files[0]["name"] == "candidate.zip"
    result = client.post(
        "/api/research/capabilities/from-artifact",
        json={"session_id": sid, "file_id": files[0]["id"]},
    )
    assert result.status_code == 201 and result.json()["status"] == "draft"
    other = client.post("/api/research/sessions", json={}).json()["id"]
    (service.store.directory(other) / "outputs" / "candidate.zip").write_bytes(output.read_bytes())
    assert client.get(f"/api/research/sessions/{other}/files").json()["items"] == []
