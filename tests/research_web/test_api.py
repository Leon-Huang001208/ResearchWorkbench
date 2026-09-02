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

    async def rpc(self, method, payload):
        self.calls.append((method, payload))
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "session.prompt" and self.fail_prompt:
            raise RuntimeFailure("connection lost")
        if method == "subagent.list":
            return {"entries": []}
        if method == "session.list":
            return {"items": []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

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


def test_datahub_read_only_catalog_authenticated_queries_and_upgrade(api):
    import httpx
    from test_datahub import nav_page, nav_row

    from app.research_web.datahub import Query

    client, native, service = api
    capabilities = client.get("/api/research/data/capabilities")
    assert capabilities.status_code == 200
    assert len(capabilities.json()["items"]) == 5
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
        "query": Query(source="fund_nav", code="000001").model_dump(),
    }
    for path in ("query", "cancel"):
        assert client.post(f"/api/research/internal/data/{path}", json=payload).status_code == 403
    assert called == []
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    response = client.post("/api/research/internal/data/query", json=payload, headers=headers)
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
