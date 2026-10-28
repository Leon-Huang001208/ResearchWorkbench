"""Source selection uses current Host bytes without a second research sender."""

import copy
import hashlib
import json
import os
import sys

import pytest
import test_pack_owned_sources as owned
from test_api import isolated_keyring  # noqa: F401

from app.research_web.scenarios.pack_catalog import ui_methods

api = owned.api


def selection(api, monkeypatch, kind="topic", identity="中国制造业景气"):
    client, service, sid, identifier, metadata, values, _ = owned.captured_source(api, monkeypatch)
    values["subject"] = {"kind": kind, "identity": identity}
    return (
        client,
        service,
        {
            "handoff": {
                "source_session_id": sid,
                "target_mode": "fingpt",
                "section": "documents",
                "source_scope": ["datahub", "uploads", "web"],
                "scenario_id": "pack-research-prep",
                "scenario_inputs": values,
            },
            "sources": [{"source_session_id": sid, "id": identifier, "sha256": metadata["sha256"]}],
        },
    )


def test_ui_method_version_is_actual():
    assert ui_methods("research-prep")[0]["version"] == "1.1.0"


def test_original_asset_bundle_file_stays_unsupported_analysis_material(api, monkeypatch):
    _client, _service, _target, context, _source = owned.source_handoff(
        api, monkeypatch, send=False
    )
    unsupported = {
        gap["id"]
        for gap in context["pack_qualification"]["missing"]
        if gap["code"] == "material_schema_unsupported"
    }
    assert "inputs/owned-bundle.json" in unsupported
    assert {ref["reference"]["type"] for ref in context["references"]} == {"source", "file"}


@pytest.mark.parametrize(
    "kind,identity",
    [("stock", "600600.SH"), ("industry", "sw:801890"), ("topic", "中国制造业景气")],
)
def test_preview_read_only_and_freeze_original_handoff(api, monkeypatch, kind, identity):
    client, service, body = selection(api, monkeypatch, kind, identity)
    before = copy.deepcopy(service.store.data)
    files = sorted(
        p.relative_to(service.store.root).as_posix()
        for p in service.store.root.rglob("*")
        if p.is_file()
    )
    preview = client.post("/api/research/source-selections/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert service.store.data == before
    assert files == sorted(
        p.relative_to(service.store.root).as_posix()
        for p in service.store.root.rglob("*")
        if p.is_file()
    )
    assert preview.json()["qualification"]["executable_methods"] == ["deduplicate_source_versions"]
    frozen = client.post(
        "/api/research/source-selections/freeze",
        json={**body, "preview_sha256": preview.json()["preview_sha256"]},
        headers={"Idempotency-Key": "source-select-freeze-test"},
    )
    assert frozen.status_code == 200, frozen.text
    result = frozen.json()
    assert result["state"] == "prepared"
    confirmed = preview.json()["qualification"]
    actual = result["scenario_context"]["pack_qualification"]
    for field in ("missing", "status", "executable_methods", "input_sha256"):
        assert actual[field] == confirmed[field]
    assert actual == confirmed
    assert result["scenario_context"]["scenario"]["inputs"]["subject"] == {
        "kind": kind,
        "identity": identity,
    }
    assert {v["reference"]["type"] for v in result["lineage"]} == {"source", "file"}
    again = client.post(
        "/api/research/source-selections/freeze",
        json={**body, "preview_sha256": preview.json()["preview_sha256"]},
        headers={"Idempotency-Key": "source-select-freeze-test"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["session_id"] == result["session_id"]
    assert len(service.store.data["sessions"]) == len(before["sessions"]) + 1


def preview_freeze(client, body, *, key="source-selection-extra", preview=None):
    if preview is None:
        response = client.post("/api/research/source-selections/preview", json=body)
        assert response.status_code == 200, response.text
        preview = response.json()["preview_sha256"]
    return client.post(
        "/api/research/source-selections/freeze",
        json={**body, "preview_sha256": preview},
        headers={"Idempotency-Key": key},
    )


@pytest.mark.parametrize("prior", ["fresh", "unknown", "prepared", "publishing"])
def test_precreation_proof_never_reclassifies_prior_outcomes(api, monkeypatch, prior):
    from app.research_web import scenario_source_selection as adapter
    from app.research_web.client import RuntimeFailure
    from app.research_web.store import StoreError

    client, service, body = selection(api, monkeypatch)
    preview = client.post("/api/research/source-selections/preview", json=body).json()[
        "preview_sha256"
    ]
    calls = []
    original_rpc = service.client.rpc

    async def rpc(method, payload):
        calls.append(method)
        if prior == "unknown" and method == "session.create":
            raise RuntimeFailure("offline lost Native result", "fixture_unknown")
        return await original_rpc(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    if prior == "publishing":
        writer = adapter.write_new

        def lost_file(fd, name, raw):
            if json.loads(raw).get("schema") == adapter.SCHEMA:
                raise StoreError(
                    "offline publication unknown", "source_selection_write_unknown", 409
                )
            return writer(fd, name, raw)

        monkeypatch.setattr(adapter, "write_new", lost_file)
    target = None
    if prior != "fresh":
        first = preview_freeze(client, body, preview=preview)
        if prior == "prepared":
            assert first.status_code == 200, first.text
            target = first.json()["session_id"]
        else:
            assert first.status_code >= 400, first.text
            assert "handoff_outcome" not in first.json()["error"]
    sid = body["handoff"]["source_session_id"]
    service.store.session(sid)["source_scope"] = ["datahub", "uploads"]
    response = preview_freeze(client, body, preview=preview)
    assert response.status_code == 403, response.text
    error = response.json()["error"]
    if prior == "fresh":
        assert error["handoff_outcome"] == "not_created"
        assert not service.store.data["handoffs"]
    else:
        assert "handoff_outcome" not in error
    lookup = client.get("/api/research/handoff-requests/source-selection-extra")
    if prior == "unknown":
        assert lookup.json()["state"] == "creation_outcome_unknown"
    elif prior == "prepared":
        assert lookup.json()["state"] == "context_unavailable"
        assert next(iter(service.store.data["handoffs"].values()))["session_id"] == target
    else:
        assert lookup.status_code == 404
        assert "handoff_outcome" not in lookup.json()["error"]
    assert calls.count("session.create") == int(prior in {"unknown", "prepared"})


def test_safe_list_duplicate_and_multi_session_captures(api, monkeypatch):
    client, service, body = selection(api, monkeypatch)
    _, _, second = selection(api, monkeypatch)
    sid = body["handoff"]["source_session_id"]
    before = copy.deepcopy(service.store.data)
    result = client.get(f"/api/research/source-selections/sessions/{sid}")
    assert result.status_code == 200, result.text
    assert service.store.data == before
    item = result.json()["items"][0]
    assert {"path", "body", "content", "excerpt", "url", "capture_proof"}.isdisjoint(item)
    assert item["source_role"] == item["language"] == item["region"] == "unknown"
    body["sources"] *= 2
    assert client.post("/api/research/source-selections/preview", json=body).status_code == 422
    body["sources"][1] = second["sources"][0]
    frozen = preview_freeze(client, body)
    assert frozen.status_code == 200, frozen.text
    refs = [r for r in frozen.json()["lineage"] if r["reference"]["type"] == "source"]
    assert len(refs) == 2 and refs[0]["sha256"] == refs[1]["sha256"]
    assert refs[0]["source_session_id"] != refs[1]["source_session_id"]
    for ref in refs:
        service.store.session(ref["source_session_id"])["deleted_at"] = "2026-10-28T00:00:00Z"
        from app.research_web.scenario_handoffs import assert_handoff_deletable
        from app.research_web.store import StoreError

        with pytest.raises(StoreError):
            assert_handoff_deletable(service.store, ref["source_session_id"])


@pytest.mark.parametrize("change", ["scope", "body", "proof", "deleted", "parameters", "foreign"])
def test_preview_changes_rejected_before_file_or_native(api, monkeypatch, change):
    client, service, body = selection(api, monkeypatch)
    response = client.post("/api/research/source-selections/preview", json=body)
    assert response.status_code == 200, response.text
    sid = body["handoff"]["source_session_id"]
    session = service.store.session(sid)
    source = session["web_evidence"][body["sources"][0]["id"]]
    if change == "scope":
        session["source_scope"] = ["datahub", "uploads"]
    elif change == "body":
        (service.store.directory(sid) / source["path"]).write_bytes(b"changed")
    elif change == "proof":
        source["title"] = "changed producer metadata"
    elif change == "deleted":
        service.store.soft_delete(sid)
        session["native_deleted_at"] = "2026-10-28T00:00:00Z"
        service.store.purge(sid)
    elif change == "parameters":
        body["handoff"]["scenario_inputs"]["question"] += "新问题"
    else:
        from uuid import uuid4

        body["sources"][0]["source_session_id"] = str(uuid4())
    count = len(service.store.data["sessions"])
    result = preview_freeze(client, body, preview=response.json()["preview_sha256"])
    assert result.status_code in {400, 403, 409}, result.text
    assert len(service.store.data["sessions"]) == count
    assert not service.store.data["handoffs"]
    assert not list(service.store.root.glob("sessions/*/inputs/source-selections/*.json"))


def test_changed_key_and_manifest_and_target_revocation(api, monkeypatch):
    client, service, body = selection(api, monkeypatch)
    frozen = preview_freeze(client, body)
    assert frozen.status_code == 200, frozen.text
    target = frozen.json()["session_id"]
    changed = copy.deepcopy(body)
    changed["handoff"]["scenario_inputs"]["question"] += "changed"
    assert preview_freeze(client, changed).status_code == 409
    manifest_ref = next(r for r in frozen.json()["lineage"] if r["reference"]["type"] == "file")
    path = (
        service.store.directory(manifest_ref["source_session_id"]) / manifest_ref["reference"]["id"]
    )
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    assert client.get(f"/api/research/sessions/{target}").status_code == 409
    assert preview_freeze(client, body).status_code == 409
    path.write_bytes(original)
    forged = json.loads(original)
    forged["sources"][0]["sha256"] = "0" * 64
    forged_bytes = json.dumps(forged).encode()
    path.write_bytes(forged_bytes)
    material = {
        "source_session_id": manifest_ref["source_session_id"],
        "file_id": hashlib.sha256(manifest_ref["reference"]["id"].encode()).hexdigest()[:24],
        "sha256": hashlib.sha256(forged_bytes).hexdigest(),
    }
    forged_body = copy.deepcopy(body["handoff"])
    forged_body["workspace_material"] = material
    forged_body["scenario_inputs"]["material_ids"] = ["file:" + material["file_id"]]
    denied = client.post("/api/research/scenarios/pack-research-prep/prepare", json=forged_body)
    assert denied.status_code == 409, denied.text
    assert denied.json()["error"]["code"] == "source_selection_manifest_invalid"
    path.write_bytes(original)
    service.store.session(target)["source_scope"] = ["datahub", "uploads"]
    assert client.get(f"/api/research/sessions/{target}").status_code == 409


def test_unknown_native_create_is_never_repeated(api, monkeypatch):
    from app.research_web.client import RuntimeFailure

    client, service, body = selection(api, monkeypatch)
    calls = []
    original = service.client.rpc

    async def rpc(method, payload):
        calls.append(method)
        if method == "session.create":
            raise RuntimeFailure("offline unknown creation", "fixture_unknown")
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    response = preview_freeze(client, body)
    assert response.status_code >= 400, response.text
    replay = preview_freeze(client, body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["state"] == "creation_outcome_unknown"
    assert calls.count("session.create") == 1
    assert not any("send" in method or "message" in method for method in calls)
    assert len(list(service.store.root.glob("sessions/*/inputs/source-selections/*.json"))) == 1


def test_original_routes_and_closed_request_and_publish_unknown(api, monkeypatch):
    from app.research_web import scenario_source_selection as adapter
    from app.research_web.store import StoreError

    client, service, body = selection(api, monkeypatch)
    for field, value in [
        ("body", "forged"),
        ("owner", "forged"),
        ("rows", []),
        ("url", "https://example.org"),
    ]:
        forged = copy.deepcopy(body)
        forged["sources"][0][field] = value
        assert (
            client.post("/api/research/source-selections/preview", json=forged).status_code == 422
        )
    original = copy.deepcopy(body)
    for scenario in ["company-onepager", "industry-onepager", "research-prep", "pack-event-review"]:
        body["handoff"]["scenario_id"] = scenario
        assert client.post("/api/research/source-selections/preview", json=body).status_code == 422
    body = original
    preview = client.post("/api/research/source-selections/preview", json=body).json()[
        "preview_sha256"
    ]
    writer = adapter.write_new
    publications = []

    def fail_manifest(fd, name, raw):
        if json.loads(raw).get("schema") == adapter.SCHEMA:
            publications.append(name)
            raise StoreError("offline lost publication", "source_selection_write_unknown", 409)
        return writer(fd, name, raw)

    monkeypatch.setattr(adapter, "write_new", fail_manifest)
    assert preview_freeze(client, body, preview=preview).status_code == 409
    assert preview_freeze(client, body, preview=preview).status_code == 409
    assert len(publications) == 1
    assert not service.store.data["handoffs"]


def test_manifest_alone_does_not_pin_deleted_source(api, monkeypatch):
    from app.research_web import workbench

    client, service, body = selection(api, monkeypatch)
    original = workbench.create_handoff
    sid = body["handoff"]["source_session_id"]

    async def delete_before_intent(handoff, request, key):
        # Actual Store purge fence sees no durable handoff pin at this instant.
        row = service.store.session(sid)
        service.store.soft_delete(sid)
        row["native_deleted_at"] = "2026-10-28T00:00:00Z"
        service.store.purge(sid)
        return await original(handoff, request, key)

    monkeypatch.setattr(workbench, "create_handoff", delete_before_intent)
    response = preview_freeze(client, body)
    assert response.status_code >= 400, response.text
    assert not service.store.data["handoffs"]
    assert not service.store.data["sessions"]


def test_private_selection_receipts_enter_existing_preservation(api, monkeypatch, tmp_path):
    import shutil

    from app.research_web.client import RuntimeFailure
    from app.research_web.dossier_preservation import snapshot_dossiers

    client, service, body = selection(api, monkeypatch)

    async def lost(*_args, **_kwargs):
        raise RuntimeFailure("offline lost Native creation", "fixture_unknown")

    monkeypatch.setattr(service, "create", lost)
    frozen = preview_freeze(client, body)
    assert frozen.status_code >= 400, frozen.text
    assert (
        next(iter(service.store.data["handoffs"].values()))["state"] == "creation_outcome_unknown"
    )
    folder = service.store.root / ".control/source-selections"
    expected = {p.relative_to(service.store.root).as_posix() for p in folder.iterdir()}
    assert len(expected) == 2
    before = snapshot_dossiers(service.store.root)
    assert expected <= set(before["files"])
    restored = tmp_path.with_name(tmp_path.name + "-restored")
    shutil.copytree(service.store.root, restored)
    assert snapshot_dossiers(restored)["files"] == before["files"]
    assert not (restored / "dossiers").exists()
    receipt = next(p for p in folder.iterdir() if not p.name.startswith("key-"))
    receipt.write_bytes(receipt.read_bytes() + b" ")
    assert snapshot_dossiers(service.store.root)["files"] != before["files"]


@pytest.mark.skipif(
    sys.platform != "darwin" or not os.environ.get("RWB_DSH_TEST_SOURCE"),
    reason="Exact pinned DSH and macOS Native sandbox required",
)
def test_selection_manifest_actual_native_guard_execution(api, monkeypatch, tmp_path):
    import test_pack_execution_host as native

    from app.research_web.scenario_handoffs import fingerprint

    client, service, body = selection(api, monkeypatch)
    calls = []
    original = service.client.rpc

    async def rpc(method, payload):
        calls.append(method)
        if method == "skill.list":
            return {
                "skills": [
                    {"name": p.name} for p in service.capabilities.prepare_native_root().iterdir()
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    frozen = preview_freeze(client, body)
    assert frozen.status_code == 200, frozen.text
    assert not any("send" in method or "message" in method for method in calls)
    result = frozen.json()
    sid, context = result["session_id"], result["scenario_context"]
    assert service._model_tools_verified(sid)
    # Explicit offline NativeFixture admission only; no provider or LLM executes.
    sent = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "执行冻结原件去重", "expected_formats": []},
        headers={"Idempotency-Key": "source-select-native-test"},
    )
    assert sent.status_code == 202, sent.text
    descriptor = {
        "capability_id": context["pack_seal"]["capability_id"],
        "version": context["pack_seal"]["version"],
        "context_sha256": fingerprint(context),
        "input_manifest_sha256": context["pack_seal"]["manifest_sha256"],
    }
    captured = (
        client,
        service,
        sid,
        context,
        descriptor,
        {"X-Research-Data-Key": service.datahub.control["token"]},
    )
    monkeypatch.setattr(native, "admitted", lambda *_args: captured)
    native.test_actual_dsh_skill_guard_toolruntime_host_and_sandbox(
        api, monkeypatch, tmp_path, False
    )
    receipt = service._task_capabilities(sid)[0]
    assert receipt["pack_executions"][0]["state"] == "saved"
