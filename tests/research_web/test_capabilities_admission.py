"""Package selection, immutable resources and native activity serialization."""

import asyncio
import hashlib
import json
import os
import re
import zipfile

import pytest
from test_api import NativeFixture
from test_capabilities import api as api_fixture
from test_capabilities import candidate, create

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError, Metadata, Step
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


def test_new_messages_accept_brand_neutral_data_tools_and_reject_unknown_tools(api):
    client, _native, _service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    accepted = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "读取基金资料", "tool_ids": ["datahub_get_fund_data"]},
        headers={"Idempotency-Key": "brand-neutral-data-tool"},
    )
    assert accepted.status_code == 202

    legacy_sid = client.post("/api/research/sessions", json={}).json()["id"]
    rejected = client.post(
        f"/api/research/sessions/{legacy_sid}/messages",
        json={"text": "未知入口", "tool_ids": ["removed_product_tool"]},
        headers={"Idempotency-Key": "legacy-data-tool"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "tool_unavailable"


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
        "tool_ids": ["research_run_script"],
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
        if str(destination).endswith(f"rwb-{cid}-v2"):
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


def creation_artifacts(api, kind="skill"):
    client, _, service = api
    created = client.post(
        "/api/research/capabilities/creation-sessions", json={"kind": kind, "goal": "生成候选包"}
    ).json()
    sid = created["id"]
    output = service.store.directory(sid) / "outputs"
    (output / "SKILL.md").write_text(candidate()["instructions"])
    (output / "capability.json").write_text(json.dumps(candidate()["metadata"]))
    return sid, output


@pytest.mark.parametrize("companion", ["capability.json", "workflow.json"])
@pytest.mark.parametrize("change", ["rename", "delete"])
def test_artifact_import_uses_current_companions_not_historical_index(api, companion, change):
    client, _, service = api
    sid, output = creation_artifacts(api)
    if companion == "workflow.json":
        (output / companion).write_text('{"steps":[{"title":"旧参考","instruction":"旧版本"}]}')
    inventory = service.store.files(sid)
    fid = next(file["id"] for file in inventory if file["name"] == "SKILL.md")
    old_id = next(file["id"] for file in inventory if file["name"] == companion)
    if change == "rename":
        (output / companion).rename(output / "draft-reference.json")
    else:
        (output / companion).unlink()
    result = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert result.status_code == 201, result.text
    assert result.json()["kind"] == "skill"
    assert result.json()["status"] == ("invalid" if companion == "capability.json" else "draft")
    if companion == "capability.json":
        assert (
            client.post(f"/api/research/capabilities/{result.json()['id']}/publish").status_code
            == 422
        )
    assert service.store.session(sid)["files"][old_id] == f"outputs/{companion}"
    if change == "rename":
        assert (output / "draft-reference.json").is_file()


@pytest.mark.parametrize(
    "content", ['{"steps":[{"title":"研究","instruction":"核实材料"}]}', "not json"]
)
def test_artifact_import_checks_current_workflow_companion(api, content):
    client, _, service = api
    sid, output = creation_artifacts(api, "workflow")
    (output / "workflow.json").write_text(content)
    fid = next(file["id"] for file in service.store.files(sid) if file["name"] == "SKILL.md")
    response = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    if content == "not json":
        assert response.status_code in {201, 422}, response.text
        if response.status_code == 201:
            assert response.json()["status"] == "invalid"
    else:
        assert response.status_code == 201 and response.json()["kind"] == "workflow"
        assert response.json()["status"] == "draft"
        assert response.json()["draft"]["steps"][0]["title"] == "研究"


@pytest.mark.parametrize("companion_name", ["capability.json", "workflow.json"])
@pytest.mark.parametrize("unsafe", ["symlink", "directory", "hardlink", "vanish_on_read"])
def test_current_unsafe_or_racing_companion_is_not_silently_ignored(
    api, monkeypatch, unsafe, companion_name
):
    client, _, service = api
    sid, output = creation_artifacts(api)
    if companion_name == "workflow.json":
        (output / companion_name).write_text('{"steps":[{"title":"研究","instruction":"核实"}]}')
    inventory = service.store.files(sid)
    fid = next(file["id"] for file in inventory if file["name"] == "SKILL.md")
    companion_id = next(file["id"] for file in inventory if file["name"] == companion_name)
    companion = output / companion_name
    if unsafe != "vanish_on_read":
        companion.rename(output / "reference.json")
        if unsafe == "symlink":
            companion.symlink_to(output / "reference.json")
        elif unsafe == "directory":
            companion.mkdir()
        else:
            os.link(output / "reference.json", companion)
    else:
        real_open = service.store.open_file

        def open_after_removal(session_id, file_id):
            if file_id == companion_id:
                companion.unlink()
            return real_open(session_id, file_id)

        monkeypatch.setattr(service.store, "open_file", open_after_removal)
    before = len(service.capabilities.list()["items"])
    result = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert result.status_code == 400, result.text
    assert len(service.capabilities.list()["items"]) == before
    assert service.store.session(sid)["files"][companion_id] == f"outputs/{companion_name}"


@pytest.mark.parametrize("kind", ["skill", "workflow"])
@pytest.mark.parametrize("zip_package", [False, True])
def test_creation_kind_conflict_is_explicit_without_rewriting_candidate(api, kind, zip_package):
    client, _, service = api
    sid, output = creation_artifacts(api, kind)
    if kind == "skill":
        (output / "workflow.json").write_text('{"steps":[{"title":"研究","instruction":"核实"}]}')
    selected = "SKILL.md"
    if zip_package:
        selected = "candidate.zip"
        with zipfile.ZipFile(output / selected, "w") as archive:
            for path in output.glob("*.json"):
                archive.write(path, path.name)
            archive.write(output / "SKILL.md", "SKILL.md")
    fid = next(file["id"] for file in service.store.files(sid) if file["name"] == selected)
    before = len(service.capabilities.list()["items"])
    response = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "creation_kind_conflict"
    assert (output / selected).is_file()
    assert len(service.capabilities.list()["items"]) == before
    if zip_package and kind == "skill":
        manual = client.post(
            "/api/research/capabilities/import",
            files={"file": ("candidate.zip", (output / selected).read_bytes())},
        )
        assert manual.status_code == 201 and manual.json()["kind"] == "workflow"


def test_explicit_skill_zip_does_not_bundle_other_session_workflow_reference(api):
    client, _, service = api
    sid, output = creation_artifacts(api)
    (output / "workflow.json").write_text('{"steps":[{"title":"参考","instruction":"不属于ZIP"}]}')
    with zipfile.ZipFile(output / "candidate.zip", "w") as archive:
        archive.write(output / "SKILL.md", "SKILL.md")
        archive.write(output / "capability.json", "capability.json")
    fid = next(file["id"] for file in service.store.files(sid) if file["name"] == "candidate.zip")
    result = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert result.status_code == 201 and result.json()["kind"] == "skill"
    assert result.json()["status"] == "draft" and (output / "workflow.json").is_file()


@pytest.mark.parametrize("kind", ["skill", "workflow"])
def test_creation_prompt_declares_actual_schema_without_automatic_execution(api, kind):
    client, native, _ = api
    result = client.post(
        "/api/research/capabilities/creation-sessions",
        json={"kind": kind, "goal": "仅生成Markdown报告"},
    ).json()
    prompt = result["draft"]
    schemas = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", prompt, re.DOTALL)]
    assert schemas, "创建提示缺少声明模型的 JSON schema"
    assert schemas[0] == Metadata.model_json_schema()
    assert "text/file/date/number" in prompt and "list[number]" in prompt
    assert "只列目标需要的格式" in prompt and "不要全选" in prompt
    assert "标准库" in prompt and "dependencies=[]" in prompt
    assert "outputs 已存在" in prompt and "不要探测宿主 cwd" in prompt
    assert "不添加未声明字段" in prompt
    if kind == "workflow":
        assert schemas[1] == Step.model_json_schema() and "workflow.json" in prompt
    else:
        assert len(schemas) == 1 and "workflow.json" not in prompt
    assert not result["auto_submitted"] and not result["auto_published"]
    assert not any(method == "session.prompt" for method, _ in native.calls)


@pytest.mark.parametrize("change", ["rename", "symlink"])
def test_selected_artifact_must_still_belong_to_current_safe_inventory(api, change):
    client, _, service = api
    sid, output = creation_artifacts(api)
    fid = next(file["id"] for file in service.store.files(sid) if file["name"] == "SKILL.md")
    (output / "SKILL.md").rename(output / "reference.md")
    if change == "symlink":
        (output / "SKILL.md").symlink_to(output / "reference.md")
    response = client.post(
        "/api/research/capabilities/from-artifact", json={"session_id": sid, "file_id": fid}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "artifact_not_output"
    assert service.store.session(sid)["files"][fid] == "outputs/SKILL.md"
