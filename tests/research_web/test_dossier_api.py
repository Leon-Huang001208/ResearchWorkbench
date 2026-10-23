"""User-triggered dossier routes bind opaque context without starting a model."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture
from test_dossiers import isolate_runtime_credentials

from app.research_web.main import create_app
from app.research_web.mcp_runtime.service import MCPRuntimeService
from app.research_web.service import ResearchService
from app.research_web.store import Store

__all__ = ["isolate_runtime_credentials"]


@pytest.fixture
def api(tmp_path):
    native = NativeFixture()
    research = ResearchService(
        native, Store(tmp_path), mcp_runtime=MCPRuntimeService(enabled=False)
    )
    with TestClient(create_app(research)) as client:
        research.connected = {"mux", "host"}
        yield client, native, research


def prepared(api):
    client, _native, research = api
    dossier = client.post(
        "/api/research/dossiers",
        json={
            "title": "长期判断",
            "subject": {"kind": "company", "key": "600519.SH", "label": "贵州茅台"},
            "idempotency_key": "create-0001",
        },
    ).json()
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    (research.store.directory(sid) / "inputs" / "source.txt").write_text("已取得材料")
    request = {
        "expected_revision": 1,
        "idempotency_key": "evidence-0001",
        "source_session_id": sid,
        "reference": {"type": "file", "id": "inputs/source.txt"},
    }
    detail = client.post(f"/api/research/dossiers/{dossier['id']}/evidence", json=request).json()
    handoff = client.post(
        f"/api/research/dossiers/{dossier['id']}/handoff",
        json={
            "expected_revision": 2,
            "idempotency_key": "handoff-0001",
            "mode": "fingpt",
            "action": "update_view",
        },
    ).json()
    return dossier, sid, detail, handoff


def test_http_binds_only_explicit_handoff_to_one_session(api, monkeypatch):
    client, native, research = api
    _dossier, sid, _detail, handoff = prepared(api)
    assert not any(method == "session.prompt" for method, _payload in native.calls)
    hid = handoff["context"]["handoff_id"]
    unbound = client.post("/api/research/sessions", json={"source_scope": ["web"]}).json()["id"]
    invalid_scope = client.post(
        f"/api/research/sessions/{unbound}/messages",
        json={"text": handoff["prompt"], "dossier_handoff_id": hid},
        headers={"Idempotency-Key": "invalid-scope-0001"},
    )
    assert invalid_scope.status_code == 403
    created = client.post("/api/research/sessions", json={"source_scope": ["uploads"]})
    assert created.status_code == 201, created.text
    target = created.json()["id"]
    handle = handoff["context"]["evidence_handles"][0]
    assert not research.store.session(target).get("dossier_handoff_ids")
    sent = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": handoff["prompt"], "dossier_handoff_id": hid},
        headers={"Idempotency-Key": "dossier-send-0001"},
    )
    assert sent.status_code == 202, sent.text
    assert research.dossiers.read_handle(target, handle)["content"] == "已取得材料"
    assert research.dossiers.source_admitted(target, operation="read", source_id=handle)
    monkeypatch.setattr(research, "_model_tools_verified", lambda sid=None: True)
    assert research.native_admission(
        target, tool_name="research_read_source", source_operation="read", source_id=handle
    )["admitted"]
    assert not research.native_admission(
        target,
        tool_name="research_read_source",
        source_operation="read",
        source_id="web:" + "a" * 24,
    )["admitted"]
    assert research.store.session(target)["source_scope"] == ["uploads"]
    assert not research.dossiers.source_admitted(
        target, operation="read", source_id="web:" + "a" * 24
    )
    # Putting the exact draft into an ordinary chat does not bind the receipt.
    plain = client.post("/api/research/sessions", json={}).json()["id"]
    assert not research.store.session(plain).get("dossier_handoff_ids")
    assert not research.dossiers.source_admitted(plain, operation="read", source_id=handle)
    replay = client.post(
        f"/api/research/sessions/{plain}/messages",
        json={"text": handoff["prompt"], "dossier_handoff_id": hid},
        headers={"Idempotency-Key": "dossier-send-0002"},
    )
    assert replay.status_code == 409
    deleted = client.delete(f"/api/research/sessions/{sid}")
    assert deleted.status_code == 200
    purge = client.delete(f"/api/research/sessions/{sid}/permanent")
    assert purge.status_code == 409
    assert purge.json()["error"]["code"] == "dossier_evidence_retained"
    assert not any(
        method == "session.delete" and payload.get("sessionId") == sid
        for method, payload in native.calls
    )


def test_http_rejects_caller_provenance_and_handoff_replay_rechecks_permissions(api):
    client, _native, research = api
    dossier, sid, _detail, _handoff = prepared(api)
    forged = client.post(
        f"/api/research/dossiers/{dossier['id']}/evidence",
        json={
            "expected_revision": 3,
            "idempotency_key": "forged-0001",
            "source_session_id": sid,
            "reference": {"type": "file", "id": "inputs/source.txt"},
            "sha256": "f" * 64,
        },
    )
    assert forged.status_code == 422
    research.store.session(sid)["source_scope"] = ["web"]
    replay = client.post(
        f"/api/research/dossiers/{dossier['id']}/handoff",
        json={
            "expected_revision": 2,
            "idempotency_key": "handoff-0001",
            "mode": "fingpt",
            "action": "update_view",
        },
    )
    assert replay.status_code == 403
    assert replay.json()["error"]["code"] == "dossier_source_revoked"
    assert (
        client.get(f"/api/research/dossiers/{dossier['id']}").json()["evidence"][0]["state"]
        == "revoked"
    )


def test_report_link_preserves_host_quality_and_freezes_content_identity(api, monkeypatch):
    client, _native, research = api
    dossier, sid, _detail, _handoff = prepared(api)
    raw = b'{"draft":"not accepted"}'
    (research.store.directory(sid) / "outputs" / "research-report.json").write_bytes(raw)
    fid = next(
        item["id"] for item in research.store.files(sid) if item["name"] == "research-report.json"
    )

    async def host_detail(_sid):
        return {
            "research_report": {
                "quality": "incomplete",
                "issues": ["missing"],
                "file_id": fid,
                "content_sha256": hashlib.sha256(raw).hexdigest(),
                "sections": [{"text": "must not be copied into metadata"}],
            }
        }

    monkeypatch.setattr(research, "detail", host_detail)
    request = {
        "expected_revision": 3,
        "idempotency_key": "link-0001",
        "type": "report",
        "source_session_id": sid,
    }
    linked = client.post(f"/api/research/dossiers/{dossier['id']}/links", json=request)
    assert linked.status_code == 200, linked.text
    result = linked.json()
    assert result["links"][0]["quality"] == "incomplete"
    assert result["links"][0]["source_mode"] == "fingpt"
    assert "sections" not in result["links"][0]["report"]
    assert result["links"][0]["report"]["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (
        client.post(
            f"/api/research/dossiers/{dossier['id']}/links", json={**request, "quality": "passed"}
        ).status_code
        == 422
    )
    file_request = {
        "expected_revision": 4,
        "idempotency_key": "file-link-0001",
        "type": "file",
        "source_session_id": sid,
        "reference_id": "outputs/research-report.json",
    }
    file_linked = client.post(f"/api/research/dossiers/{dossier['id']}/links", json=file_request)
    assert file_linked.status_code == 200, file_linked.text
    assert file_linked.json()["links"][-1]["reference_id"] == fid


@pytest.mark.parametrize("failure", ["missing", "changed", "revoked"])
def test_one_unavailable_archived_source_does_not_lock_target_or_other_sources(api, failure):
    client, _native, research = api
    dossier, bad_sid, _detail, _unused = prepared(api)
    good_sid = client.post("/api/research/sessions", json={}).json()["id"]
    (research.store.directory(good_sid) / "inputs/source.txt").write_text("仍可核验的好材料")
    added = client.post(
        f"/api/research/dossiers/{dossier['id']}/evidence",
        json={
            "expected_revision": 3,
            "idempotency_key": "good-source-0001",
            "source_session_id": good_sid,
            "reference": {"type": "file", "id": "inputs/source.txt"},
        },
    )
    assert added.status_code == 200, added.text
    handoff = client.post(
        f"/api/research/dossiers/{dossier['id']}/handoff",
        json={
            "expected_revision": 4,
            "idempotency_key": "handoff-two-0001",
            "mode": "fingpt",
            "action": "update_view",
        },
    ).json()
    target = client.post("/api/research/sessions", json={"source_scope": ["uploads"]}).json()["id"]
    sent = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": handoff["prompt"], "dossier_handoff_id": handoff["context"]["handoff_id"]},
        headers={"Idempotency-Key": "send-two-0001"},
    )
    assert sent.status_code == 202, sent.text
    from test_delivery import finish

    finish((client, _native, research, target))
    bad_path = research.store.directory(bad_sid) / "inputs/source.txt"
    if failure == "missing":
        bad_path.unlink()
    elif failure == "changed":
        bad_path.write_text("已经改写的材料")
    else:
        research.store.session(bad_sid)["source_scope"] = ["web"]
    opened = client.get(f"/api/research/sessions/{target}")
    assert opened.status_code == 200, opened.text
    sources = opened.json()["research_sources"]
    bad = next(source for source in sources if source.get("source_session_id") == bad_sid)
    good = next(source for source in sources if source.get("source_session_id") == good_sid)
    assert bad["state"] == failure and bad["error_code"]
    assert good["state"] == "available"
    assert not research.dossiers.source_admitted(
        target, operation="read", source_id=bad["dossier_handle"]
    )
    assert research.dossiers.source_admitted(
        target, operation="read", source_id=good["dossier_handle"]
    )
    assert (
        research.dossiers.read_handle(target, good["dossier_handle"])["content"]
        == "仍可核验的好材料"
    )
    from app.research_web.store import StoreError

    with pytest.raises(StoreError):
        research.dossiers.read_handle(target, bad["dossier_handle"])
    observed = research.dossiers.observations(target, task_id="a" * 24, contract_sha="b" * 64)
    assert any(row["id"] == good["id"] for row in observed)
    assert not any(row["id"] == bad["id"] for row in observed)
    assert opened.json()["research_quality"]["status"] != "passed"
    plain = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": "继续分析仍可核验的材料"},
        headers={"Idempotency-Key": "plain-after-gap-0001"},
    )
    assert plain.status_code == 202, plain.text


def test_mutable_report_link_exposes_change_and_refuses_read(api, monkeypatch):
    client, _native, research = api
    dossier, sid, _detail, _handoff = prepared(api)
    path = research.store.directory(sid) / "outputs/research-report.json"
    original = b'{"version":1}'
    path.write_bytes(original)
    fid = next(
        item["id"] for item in research.store.files(sid) if item["name"] == "research-report.json"
    )

    async def host_detail(_sid):
        return {
            "research_report": {
                "file_id": fid,
                "content_sha256": hashlib.sha256(original).hexdigest(),
                "quality": "passed",
            }
        }

    monkeypatch.setattr(research, "detail", host_detail)
    linked = client.post(
        f"/api/research/dossiers/{dossier['id']}/links",
        json={
            "expected_revision": 3,
            "idempotency_key": "report-link-0001",
            "type": "report",
            "source_session_id": sid,
        },
    ).json()["links"][0]
    path.write_bytes(b'{"version":2}')
    viewed = client.get(f"/api/research/dossiers/{dossier['id']}").json()["links"][0]
    assert viewed["quality"] == "passed" and viewed["state"] == "changed"
    assert viewed["error_code"] == "dossier_evidence_changed"
    assert (
        client.get(f"/api/research/dossiers/{dossier['id']}/links/{linked['id']}").status_code
        == 409
    )
    path.unlink()
    assert (
        client.get(f"/api/research/dossiers/{dossier['id']}").json()["links"][0]["state"]
        == "missing"
    )


def test_report_link_prefers_existing_immutable_version(api, monkeypatch, tmp_path):
    from test_research_report import payload

    from app.research_web.resources.research_report import archive_report_version

    client, _native, research = api
    dossier, sid, _detail, _handoff = prepared(api)
    output = research.store.directory(sid) / "outputs"
    raw = json.dumps(payload(), ensure_ascii=False).encode()
    (output / "research-report.json").write_bytes(raw)
    archived = archive_report_version(output)
    fid = next(
        item["id"] for item in research.store.files(sid) if item["name"] == "research-report.json"
    )

    async def host_detail(_sid):
        return {
            "research_report": {
                "file_id": fid,
                "content_sha256": hashlib.sha256(raw).hexdigest(),
                "quality": "incomplete",
                "task_id": "a" * 24,
            }
        }

    monkeypatch.setattr(research, "detail", host_detail)
    linked = client.post(
        f"/api/research/dossiers/{dossier['id']}/links",
        json={
            "expected_revision": 3,
            "idempotency_key": "version-link-0001",
            "type": "report",
            "source_session_id": sid,
        },
    ).json()["links"][0]
    assert linked["report"]["version_id"] == archived["version_id"]
    (output / "research-report.json").write_text('{"new":"different report"}')
    viewed = client.get(f"/api/research/dossiers/{dossier['id']}").json()["links"][0]
    assert viewed["state"] == "available" and viewed["quality"] == "incomplete"
    preview = client.get(viewed["preview_url"])
    assert preview.status_code == 200, preview.text
    assert preview.json()["content"] == raw.decode()
    research.dossiers.backup_to(tmp_path / "immutable-linked-backup.sqlite3")


def test_unready_discovery_cannot_consume_dossier_handoff(api):
    client, native, research = api
    _dossier, _sid, _detail, handoff = prepared(api)
    hid = handoff["context"]["handoff_id"]
    target = client.post("/api/research/sessions", json={"source_scope": ["uploads"]}).json()["id"]
    row = research.store.session(target)
    row.update(purpose="discovery_research", discovery_creation_state="preparing")
    body = {"text": handoff["prompt"], "dossier_handoff_id": hid}
    response = client.post(
        f"/api/research/sessions/{target}/messages",
        json=body,
        headers={"Idempotency-Key": "discovery-pending-0001"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "discovery_session_not_ready"
    assert not row.get("dossier_handoff_ids")
    assert not any(method == "session.prompt" for method, _payload in native.calls)
    ordinary = client.post("/api/research/sessions", json={"source_scope": ["uploads"]}).json()[
        "id"
    ]
    accepted = client.post(
        f"/api/research/sessions/{ordinary}/messages",
        json=body,
        headers={"Idempotency-Key": "discovery-ready-0001"},
    )
    assert accepted.status_code == 202, accepted.text
    assert research.store.session(ordinary)["dossier_handoff_ids"] == [hid]
