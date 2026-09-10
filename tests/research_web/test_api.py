"""BFF acceptance tests: native transport is replaced only for deterministic regressions."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.research_web.client import RuntimeFailure
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    def __init__(self):
        self.calls = []
        self.fail_prompt = False
        self.confirm_delete = True
        self.running = set()

    async def rpc(self, method, payload):
        self.calls.append((method, payload))
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "session.prompt" and self.fail_prompt:
            raise RuntimeFailure("connection lost")
        if method == "subagent.list":
            return {"entries": []}
        if method == "session.list":
            return {
                "items": [
                    {"sessionId": session_id, "running": True}
                    for session_id in sorted(self.running)
                ]
            }
        if method == "session.delete":
            return {"deletedSessionIds": [payload["sessionId"]] if self.confirm_delete else []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

    async def plugin_json(self, method, path, *, params=None, payload=None):
        self.calls.append(
            (f"plugin:{method}", {"path": path, "params": params, "payload": payload})
        )
        if path == "/research/tabbit/status":
            return {
                "status": "ready",
                "pluginVersion": "0.3.4",
                "browserVersion": "1.13.23",
                "launcherPresent": True,
                "onlineInstances": 1,
                "selectedInstance": "ABCDEF0123456789",
            }
        if path == "/research/tabbit/access":
            return {"accepted": True}
        if path == "/research/tabbit/tabs":
            return {
                "instanceId": "ABCDEF0123456789",
                "tabs": [
                    {
                        "tabId": 7,
                        "title": "Live research page",
                        "url": "https://example.com/live",
                        "active": True,
                        "state": "available",
                    }
                ],
            }
        if path == "/research/tabbit/live-extract":
            return {
                "markers": [
                    {
                        "tabId": tab_id,
                        "title": "Live research page",
                        "marker": f"@[Live research page](rwb-tabbit:{tab_id}-token)",
                    }
                    for tab_id in payload["tabIds"]
                ]
            }
        raise AssertionError(path)

    async def history(self, sid):
        return []

    async def close(self):
        pass

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def api(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def test_create_submit_duplicate_never_replays(api):
    client, native, _ = api
    created = client.post("/api/research/sessions", json={"mode": "fingpt"})
    assert created.status_code == 201
    sid = created.json()["id"]
    endpoint = f"/api/research/sessions/{sid}/messages"
    for _ in range(2):
        response = client.post(
            endpoint, json={"text": "你好"}, headers={"Idempotency-Key": "abcdefgh"}
        )
        assert response.status_code == 202, response.text
    assert len([call for call in native.calls if call[0] == "session.prompt"]) == 1
    assert (
        client.post(
            endpoint, json={"text": "别的问题"}, headers={"Idempotency-Key": "abcdefgh"}
        ).status_code
        == 400
    )


def test_tabbit_status_access_inventory_and_live_message(api):
    client, native, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]

    status = client.get("/api/research/runtime/tabbit")
    assert status.status_code == 200
    assert status.json()["status"] == "ready"
    assert status.json()["web_fetch_enabled"] is False

    denied = client.get(f"/api/research/sessions/{sid}/tabbit-tabs")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "tabbit_page_access_required"

    grant = client.post(f"/api/research/sessions/{sid}/tabbit-access", json={"decision": "approve"})
    assert grant.status_code == 200
    tabs = client.get(f"/api/research/sessions/{sid}/tabbit-tabs?q=research")
    assert tabs.status_code == 200
    assert tabs.json()["items"][0]["tab_id"] == 7

    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        headers={"Idempotency-Key": "tabbit-message-1"},
        json={
            "text": "总结这个页面",
            "tabbit_tabs": [{"tab_id": 7, "instance_id": "ABCDEF0123456789"}],
            "tabbit_live_confirmed": True,
        },
    )
    assert response.status_code == 202, response.text
    prompt = [call for call in native.calls if call[0] == "session.prompt"][-1][1]
    sent_text = prompt["content"][0]["text"]
    assert "@[Live research page](rwb-tabbit:7-token)" in sent_text


def test_tabbit_live_message_requires_confirmation_and_limits_selection(api):
    client, _, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    client.post(f"/api/research/sessions/{sid}/tabbit-access", json={"decision": "approve"})

    unconfirmed = client.post(
        f"/api/research/sessions/{sid}/messages",
        headers={"Idempotency-Key": "tabbit-message-2"},
        json={
            "text": "总结",
            "tabbit_tabs": [{"tab_id": 7, "instance_id": "ABCDEF0123456789"}],
        },
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["error"]["code"] == "tabbit_claim_confirmation_required"

    too_many = client.post(
        f"/api/research/sessions/{sid}/messages",
        headers={"Idempotency-Key": "tabbit-message-3"},
        json={
            "text": "总结",
            "tabbit_tabs": [
                {"tab_id": index, "instance_id": "ABCDEF0123456789"} for index in range(9)
            ],
            "tabbit_live_confirmed": True,
        },
    )
    assert too_many.status_code == 422


def test_tabbit_settings_validate_dependency_and_report_restart(api):
    client, _, _ = api
    invalid = client.put(
        "/api/research/runtime/tabbit",
        json={"browser_enabled": False, "web_fetch_enabled": True},
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "tabbit_web_fetch_requires_browser"

    saved = client.put(
        "/api/research/runtime/tabbit",
        json={
            "browser_enabled": True,
            "web_fetch_enabled": True,
            "instance_id": "ABCDEF0123456789",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["restart_required"] is True


def test_session_soft_delete_restore_is_recoverable_and_never_archives_native_history(api):
    client, native, service = api
    created = client.post("/api/research/sessions", json={}).json()
    sid = created["id"]
    artifact = service.store.directory(sid) / "outputs" / "retained.md"
    artifact.write_text("保留的研究产物")

    deleted = client.delete(f"/api/research/sessions/{sid}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"]
    assert sid not in {item["id"] for item in client.get("/api/research/sessions").json()["items"]}
    deleted_items = client.get("/api/research/sessions?view=deleted").json()["items"]
    assert [item["id"] for item in deleted_items] == [sid]
    assert deleted_items[0]["mode"] == "fingpt"
    assert client.get(f"/api/research/sessions/{sid}").status_code == 410
    assert client.get(f"/api/research/sessions/{sid}").json()["error"]["code"] == "session_deleted"
    assert artifact.read_text() == "保留的研究产物"
    assert not any(call[0] == "workspace.archiveSession" for call in native.calls)

    repeated = client.delete(f"/api/research/sessions/{sid}")
    assert repeated.status_code == 200
    assert repeated.json()["deleted_at"] == deleted.json()["deleted_at"]

    restored = client.post(f"/api/research/sessions/{sid}/restore")
    assert restored.status_code == 200
    assert "deleted_at" not in restored.json()
    assert sid in {item["id"] for item in client.get("/api/research/sessions").json()["items"]}
    assert client.get(f"/api/research/sessions/{sid}").status_code == 200
    assert artifact.read_text() == "保留的研究产物"
    assert client.post(f"/api/research/sessions/{sid}/restore").status_code == 200


def test_session_soft_delete_rejects_busy_and_unknown_sessions(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    service.store.session(sid)["status"] = "running"
    service.store.save()
    native.running.add(sid)

    busy = client.delete(f"/api/research/sessions/{sid}")
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "session_busy"
    assert client.get(f"/api/research/sessions/{sid}").status_code == 200

    unknown = client.delete("/api/research/sessions/00000000-0000-0000-0000-000000000000")
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "invalid_resource"
    assert client.get("/api/research/sessions?view=unknown").status_code == 422


def test_session_soft_delete_reconciles_stale_cached_running_state(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    service.store.data["sessions"][sid]["status"] = "running"
    service.store.save()

    response = client.delete(f"/api/research/sessions/{sid}")

    assert response.status_code == 200
    assert response.json()["deleted_at"]
    assert response.json()["status"] == "idle"


def test_deleted_session_can_be_permanently_deleted_with_native_confirmation(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    artifact = service.store.directory(sid) / "outputs" / "removed.md"
    artifact.write_text("永久删除")
    client.delete(f"/api/research/sessions/{sid}")

    response = client.delete(f"/api/research/sessions/{sid}/permanent")

    assert response.status_code == 200
    assert response.json() == {"id": sid, "purged": True}
    assert ("session.delete", {"sessionId": sid}) in native.calls
    assert not artifact.exists()
    assert sid not in service.store.data["sessions"]
    assert client.get(f"/api/research/sessions/{sid}").status_code == 400


def test_permanent_delete_removes_sealed_capabilities_and_private_datahub_state(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    session_root = service.store.directory(sid)
    sealed = session_root / "resources" / "capabilities" / "fund-research-workflow" / "2"
    sealed.mkdir(parents=True)
    capability = sealed / "SKILL.md"
    capability.write_text("# sealed capability")
    capability.chmod(0o400)
    sealed.chmod(0o500)

    private_paths = [
        service.store.root / ".control" / "snapshots" / sid,
        service.store.root / ".control" / "calls" / sid,
    ]
    for private in private_paths:
        private.mkdir(parents=True)
        (private / "record.json").write_text("{}")

    deleted = client.delete(f"/api/research/sessions/{sid}")
    assert deleted.status_code == 200, deleted.text

    response = client.delete(f"/api/research/sessions/{sid}/permanent")

    assert response.status_code == 200, response.text
    assert not session_root.exists()
    assert all(not private.exists() for private in private_paths)


def test_expired_deleted_session_is_purged_when_deleted_view_is_loaded(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    client.delete(f"/api/research/sessions/{sid}")
    service.store.session(sid, include_deleted=True)["deleted_at"] = 0
    service.store.save()

    response = client.get("/api/research/sessions?view=deleted")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert sid not in service.store.data["sessions"]


def test_expired_deleted_session_cannot_be_restored_before_the_next_purge_cycle(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    client.delete(f"/api/research/sessions/{sid}")
    service.store.session(sid, include_deleted=True)["deleted_at"] = 0
    service.store.save()

    response = client.post(f"/api/research/sessions/{sid}/restore")

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "session_restore_expired"
    assert service.store.session(sid, include_deleted=True)["deleted_at"] == 0


def test_permanent_delete_requires_soft_delete(api):
    client, _, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]

    response = client.delete(f"/api/research/sessions/{sid}/permanent")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_not_deleted"


def test_permanent_delete_keeps_tombstone_when_dsh_does_not_confirm(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    artifact = service.store.directory(sid) / "outputs" / "retained.md"
    artifact.write_text("仍可重试")
    client.delete(f"/api/research/sessions/{sid}")
    native.confirm_delete = False

    response = client.delete(f"/api/research/sessions/{sid}/permanent")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "native_session_delete_unconfirmed"
    assert service.store.session(sid, include_deleted=True)["deleted_at"]
    assert artifact.read_text() == "仍可重试"


@pytest.mark.asyncio
async def test_online_retention_loop_purges_without_opening_deleted_view(tmp_path, monkeypatch):
    import app.research_web.service as service_module

    monkeypatch.setattr(service_module, "SESSION_PURGE_INTERVAL_SECONDS", 0.01)
    service = ResearchService(NativeFixture(), Store(tmp_path))
    row = service.store.create("fingpt", "到期研究")
    service.store.soft_delete(row["id"])
    service.store.session(row["id"], include_deleted=True)["deleted_at"] = 0
    service.store.save()

    task = asyncio.create_task(service._retention_loop())
    try:
        for _ in range(100):
            if row["id"] not in service.store.data["sessions"]:
                break
            await asyncio.sleep(0.01)
        assert row["id"] not in service.store.data["sessions"]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_datahub_read_only_catalog_authenticated_queries_and_upgrade(api):
    import httpx
    from test_datahub import nav_page, nav_row

    from app.research_web.datahub import BusinessQuery

    client, native, service = api
    catalog = client.get("/api/research/data/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["capabilities"]) == 15
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    assert client.get(f"/api/research/sessions/{sid}").json()["datasets"] == []
    called = []

    def provider(request):
        called.append(request)
        return httpx.Response(200, json=nav_page([nav_row("2025-12-31")], 1))

    service.datahub.transport = httpx.MockTransport(provider)
    payload = {
        "session_id": sid,
        "call_id": "api-test",
        "query": BusinessQuery(
            capability="fund_data", parameters={"dataset": "nav", "code": "000001"}
        ).model_dump(),
    }
    for path in ("business-query", "cancel"):
        assert client.post(f"/api/research/internal/data/{path}", json=payload).status_code == 403
    assert called == []
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    response = client.post(
        "/api/research/internal/data/business-query", json=payload, headers=headers
    )
    assert response.status_code == 200, response.text
    dataset = response.json()
    did = dataset["dataset_id"]
    assert len(called) == 1
    prefix = f"/api/research/sessions/{sid}/datasets/{did}"
    assert client.get(prefix + "/rows?offset=0&limit=1").json()["total"] == 1
    assert client.get(prefix + "/rows?limit=501").status_code in {400, 422}
    detail = client.get(prefix).json()
    assert client.get(detail["files"][0]["url"]).status_code == 200
    assert client.get(f"/api/research/sessions/{sid}/files").json()["items"] == []
    assert len(client.get(f"/api/research/sessions/{sid}").json()["datasets"]) == 1
    source_text = f"请保留这段原文，继续分析 inputs/datasets/{did}/rows.json。"

    async def history_with_original_dataset(requested_sid):
        if requested_sid != sid:
            return []
        return [
            {
                "event": {
                    "seq": 1,
                    "type": "user/message",
                    "data": {
                        "id": "original-user-message",
                        "content": [{"type": "text", "text": source_text}],
                    },
                }
            }
        ]

    native.history = history_with_original_dataset
    service.loaded.discard(sid)
    upgraded = client.post(f"/api/research/sessions/{sid}/upgrade").json()
    new_sid = upgraded["id"]
    copied = client.get(f"/api/research/sessions/{new_sid}/datasets").json()["items"][0]
    assert copied["dataset_id"] != did
    copied_detail = client.get(
        f"/api/research/sessions/{new_sid}/datasets/{copied['dataset_id']}"
    ).json()
    assert copied_detail["origin_dataset_id"] == did
    assert copied_detail["retrieved_at"] == detail["retrieved_at"]
    assert copied_detail["origin_manifest_sha256"] == detail["manifest_sha256"]
    original_draft = "继续研究以下会话：\nuser: " + source_text
    assert upgraded["draft"].startswith(original_draft)
    handoff = upgraded["draft"][len(original_draft) :]
    assert f'"origin_dataset_id": "{did}"' in handoff
    assert f'"dataset_id": "{copied["dataset_id"]}"' in handoff
    assert copied_detail["origin_manifest_sha256"] in handoff
    assert copied_detail["manifest_sha256"] in handoff
    assert copied_detail["retrieved_at"] in handoff
    for item in copied_detail["files"]:
        assert item["path"] in handoff and item["sha256"] in handoff
        assert (service.store.directory(new_sid) / item["path"]).is_file()
    assert f"inputs/datasets/{did}/" not in handoff
    assert str(service.store.directory(sid)) not in handoff
    assert client.get(f"/api/research/sessions/{sid}").json()["messages"][0]["text"] == source_text
    assert client.get(copied_detail["files"][0]["url"]).status_code == 200
    assert client.get(prefix.replace(sid, new_sid)).status_code == 400
    assert len(called) == 1


def test_unknown_admission_not_retried(api):
    client, native, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    native.fail_prompt = True
    for _ in range(2):
        response = client.post(
            f"/api/research/sessions/{sid}/messages",
            json={"text": "你好"},
            headers={"Idempotency-Key": "abcdefgh"},
        )
        assert response.status_code == 503
    assert len([call for call in native.calls if call[0] == "session.prompt"]) == 1


def test_upload_ownership_and_preview_sandbox(api):
    client, _, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    uploaded = client.post(
        f"/api/research/sessions/{sid}/uploads",
        files=[("files", ("../note.md", b"# Notes", "text/markdown"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    file = uploaded.json()["items"][0]
    preview = client.get(file["preview_url"])
    assert preview.status_code == 200
    assert "sandbox" in preview.headers["content-security-policy"]
    assert "allow-same-origin" not in preview.headers["content-security-policy"]
    other = client.post("/api/research/sessions", json={}).json()["id"]
    assert client.get(file["url"].replace(sid, other)).status_code == 400


def test_cross_origin_and_invalid_credentials_do_not_leak_input(api):
    client, _, _ = api
    assert (
        client.post(
            "/api/research/sessions", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    response = client.put(
        "/api/research/runtime/model", json={"provider": "bad", "api_key": "secret-canary"}
    )
    assert response.status_code == 422
    assert "secret-canary" not in response.text


def test_no_dsh_connection_no_fake_success(api):
    client, _, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    service.connected.clear()
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "问题"},
        headers={"Idempotency-Key": "abcdefgh"},
    )
    assert response.status_code == 503


def test_model_selection_is_restored(tmp_path):
    store = Store(tmp_path)
    store.data["model"] = {"provider": "deepseek-official", "model": "custom-model"}
    store.save()
    assert (
        ResearchService(NativeFixture(), Store(tmp_path)).default_model["model"] == "custom-model"
    )


@pytest.mark.asyncio
async def test_unowned_instance_is_read_only(tmp_path):
    service = ResearchService(NativeFixture(), Store(tmp_path), expected_cwd=tmp_path / "owned")
    with pytest.raises(RuntimeFailure, match="专属"):
        await service.create()
    assert not any(method == "session.create" for method, _ in service.client.calls)


def test_skill_catalog_resumes_native_session_after_runtime_restart(api):
    client, native, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    original = native.rpc
    resumed = False

    async def cold_rpc(method, payload):
        nonlocal resumed
        if method == "session.models":
            assert payload == {"sessionId": sid}
            resumed = True
        if method == "skill.list" and not resumed:
            raise RuntimeFailure("not attached", "session-not-found")
        return await original(method, payload)

    native.rpc = cold_rpc
    response = client.get("/api/research/skills")
    assert response.status_code == 200, response.text
    assert resumed


def test_child_activity_comes_from_native_parent_scoped_history(api):
    client, native, _ = api
    sid = client.post("/api/research/sessions", json={"mode": "claw"}).json()["id"]
    original = native.rpc

    async def child_rpc(method, payload):
        if method == "subagent.list":
            return {
                "entries": [
                    {
                        "kind": "child",
                        "id": "child-1",
                        "mode": "continuable",
                        "label": "行业分析",
                        "activity": "inactive",
                    }
                ]
            }
        if method == "subagent.history":
            assert payload["parentSessionId"] == sid
            assert payload["childSessionId"] == "child-1"
            return {
                "events": [
                    {
                        "event": {
                            "seq": 1,
                            "type": "tool/call",
                            "data": {"callId": "tool-1", "name": "web_search", "arguments": "{}"},
                        }
                    },
                    {
                        "event": {
                            "seq": 2,
                            "type": "turn/end",
                            "data": {
                                "reason": {
                                    "kind": "error",
                                    "error": {"message": "search unavailable"},
                                }
                            },
                        }
                    },
                ],
                "hasMore": False,
            }
        return await original(method, payload)

    native.rpc = child_rpc
    detail = client.get(f"/api/research/sessions/{sid}").json()
    assert detail["subagents"][0]["status"] == "failed"
    assert detail["subagents"][0]["error"] == "search unavailable"
    assert detail["activities"][0]["agent_id"] == "child-1"


def test_active_child_keeps_parent_stoppable_in_detail_and_history(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={"mode": "claw"}).json()["id"]
    service.store.session(sid)["status"] = "completed"
    original = native.rpc

    async def child_rpc(method, payload):
        if method == "subagent.list":
            return {
                "entries": [
                    {
                        "kind": "child",
                        "id": "active-child",
                        "mode": "continuable",
                        "label": "分析",
                        "activity": "running",
                    }
                ]
            }
        if method == "subagent.history":
            return {"events": [], "hasMore": False}
        return await original(method, payload)

    native.rpc = child_rpc
    assert client.get(f"/api/research/sessions/{sid}").json()["status"] == "running"
    assert client.get("/api/research/sessions").json()["items"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_model_configuration_serializes_with_session_creation(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    await service.create()
    entered, release = asyncio.Event(), asyncio.Event()
    original = native.rpc

    async def blocked_rpc(method, payload):
        if method == "session.selectModel" and not release.is_set():
            entered.set()
            await release.wait()
        return await original(method, payload)

    native.rpc = blocked_rpc
    configuring = asyncio.create_task(service.configure_model("deepseek-official", "new-model"))
    await asyncio.wait_for(entered.wait(), 1)
    creating = asyncio.create_task(service.create())
    await asyncio.sleep(0)
    assert len(service.store.data["sessions"]) == 1
    assert service.default_model["model"] != "new-model"
    release.set()
    await asyncio.gather(configuring, creating)
    assert len(service.store.data["sessions"]) == 2
    assert service.store.data["model"]["model"] == "new-model"


def test_native_question_reply_requires_ownership_and_complete_answers(api):
    client, native, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    other = client.post("/api/research/sessions", json={}).json()["id"]
    service.questions["question-rpc"] = {
        "sessionId": sid,
        "questions": [{"id": "period", "question": "研究期间？"}],
    }
    replies = []

    async def respond(rpc_id, value):
        replies.append((rpc_id, value))
        return {"accepted": True}

    native.respond = respond
    endpoint = f"/api/research/sessions/{sid}/questions/question-rpc"
    body = {"answers": [{"id": "period", "selected": [], "custom": "2025"}]}
    assert client.post(endpoint.replace(sid, other), json=body).status_code == 400
    assert (
        client.post(endpoint, json={"answers": [{"id": "wrong", "custom": "2025"}]}).status_code
        == 400
    )
    assert not replies
    assert client.post(endpoint, json=body).status_code == 200
    assert replies == [("question-rpc", {"sessionId": sid, "answer": body})]


def test_image_attachment_is_forwarded_as_native_image_not_just_a_path(api):
    import base64

    client, native, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    image_bytes = b"\x89PNG\r\n\x1a\nfixture"
    uploaded = client.post(
        f"/api/research/sessions/{sid}/uploads",
        files=[("files", ("chart.png", image_bytes, "image/png"))],
    ).json()["items"][0]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "解读图片", "attachment_ids": [uploaded["id"]]},
        headers={"Idempotency-Key": "image-request"},
    )
    assert response.status_code == 202
    prompt = next(payload for method, payload in native.calls if method == "session.prompt")
    assert prompt["content"][1]["type"] == "image"
    assert base64.b64decode(prompt["content"][1]["data"]) == image_bytes


def test_each_claw_turn_appends_the_visible_language_contract_last(api):
    client, native, _ = api
    sid = client.post("/api/research/sessions", json={"mode": "claw"}).json()["id"]

    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "分析市场", "tool_ids": ["research_run_script"]},
        headers={"Idempotency-Key": "language-contract"},
    )

    assert response.status_code == 202
    prompt = next(payload for method, payload in native.calls if method == "session.prompt")
    text = prompt["content"][0]["text"]
    assert text.index("用户选择的研究工具意图") < text.index("使用 DSH 原生子 Agent")
    assert text.rstrip().endswith("不得直接以英文回答透传。")
    assert "所有可见过程说明、工具调用前后说明、提问、错误解释、总结和最终答复" in text
