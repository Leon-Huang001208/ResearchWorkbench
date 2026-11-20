"""Host HTTP keeps the DataKey read lane separate from explicit user writes."""

import pytest

from app.research_web import service as host_module
from app.research_web.main import _service_only_route_allowed
from tests.research_web import test_weknora_api as api_fixtures
from tests.research_web.test_weknora_current import CurrentSync


@pytest.fixture
def api(tmp_path, monkeypatch):
    yield from api_fixtures.api.__wrapped__(tmp_path, monkeypatch)


def session(client, host, upstream):
    assert (
        client.post(
            "/api/research/knowledge/binding",
            json={"token": "user-jwt-a", "workspace_id": "101"},
            headers={"X-Research-User-Action": "?1"},
        ).status_code
        == 200
    )
    host.knowledge.sync = CurrentSync(upstream)
    row = host.store.create("fingpt", "Current research")
    row.update(created=True, source_scope=["uploads"])
    host.store.save()
    return row["id"]


def test_login_requires_user_action_and_hides_invalid_input(api):
    client, _, _, _ = api
    payload = {"email": "real-user@example.test", "password": "password-canary"}
    assert client.post("/api/research/knowledge/login", json=payload).status_code == 403
    result = client.post(
        "/api/research/knowledge/login",
        json={**payload, "email": ["secret-email"]},
        headers={"X-Research-User-Action": "?1"},
    )
    assert (
        result.status_code == 422
        and "secret-email" not in result.text
        and "password-canary" not in result.text
    )


def test_login_stores_only_verified_token_and_never_password(api, monkeypatch, caplog):
    from app.research_web.knowledge_backend.client import WeKnoraClient

    client, host, _, _ = api

    async def login(origin, email, password):
        assert origin == "https://knowledge.example.test"
        assert email == "real-user@example.test" and password == "password-canary"
        return {"token": "user-jwt-a", "workspace_id": "101", "user_id": "user-a"}

    monkeypatch.setattr(WeKnoraClient, "login", login, raising=False)
    result = client.post(
        "/api/research/knowledge/login",
        json={"email": "real-user@example.test", "password": "password-canary"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["configured"] is True
    assert _service_only_route_allowed("POST", "/api/research/knowledge/login")
    assert (
        "real-user" not in result.text
        and "password-canary" not in result.text
        and "user-jwt-a" not in result.text
    )
    stored = (host.store.root / "knowledge-backend/binding.json").read_text()
    assert (
        "password-canary" not in stored and "real-user" not in stored and "user-jwt-a" not in stored
    )
    assert "password-canary" not in caplog.text and "real-user@example.test" not in caplog.text


def test_login_failure_preserves_prior_binding_without_error_details(api, monkeypatch):
    from app.research_web.knowledge_backend.client import WeKnoraClient
    from app.research_web.store import StoreError

    client, host, upstream, _ = api
    session(client, host, upstream)
    previous = host.knowledge.store.binding()

    async def denied(*args):
        raise StoreError(
            "real-user@example.test password-canary token-canary", "weknora_auth_denied", 401
        )

    monkeypatch.setattr(WeKnoraClient, "login", denied, raising=False)
    result = client.post(
        "/api/research/knowledge/login",
        json={"email": "real-user@example.test", "password": "password-canary"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert result.status_code == 401 and result.json()["error"]["code"] == "knowledge_login_failed"
    assert "canary" not in result.text and "real-user" not in result.text
    assert host.knowledge.store.binding() == previous


def test_login_identity_change_hides_old_sync_configuration(api, monkeypatch):
    from app.research_web.knowledge_backend.client import WeKnoraClient

    client, host, upstream, _ = api
    session(client, host, upstream)
    original_status = host.knowledge.sync.status
    host.knowledge.sync.status = lambda: {
        **original_status(),
        "items": [{"path": "private-old-path"}],
        "knowledge_base_id": "old-private-kb",
    }

    async def login(*args):
        upstream.user = "user-b"
        return {"token": "user-jwt-b", "workspace_id": "101", "user_id": "user-b"}

    monkeypatch.setattr(WeKnoraClient, "login", login, raising=False)
    result = client.post(
        "/api/research/knowledge/login",
        json={"email": "real-user@example.test", "password": "password-canary"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert result.status_code == 200, result.text
    status = result.json()["sync"]
    assert status["reconfiguration_required"] is True and status["enabled"] is False
    assert status["knowledge_base_id"] is None and status["items"] == []
    assert "private-old" not in client.get("/api/research/knowledge/sync").text


def test_login_identity_mismatch_cannot_replace_prior_binding(api, monkeypatch):
    from app.research_web.knowledge_backend.client import WeKnoraClient

    client, host, upstream, _ = api
    session(client, host, upstream)
    previous = host.knowledge.store.binding()

    async def login(*args):
        return {"token": "user-jwt-b", "workspace_id": "101", "user_id": "other-user"}

    monkeypatch.setattr(WeKnoraClient, "login", login, raising=False)
    result = client.post(
        "/api/research/knowledge/login",
        json={"email": "real-user@example.test", "password": "password-canary"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert result.status_code == 401 and host.knowledge.store.binding() == previous


def test_internal_current_query_read_only_and_user_selected_freeze(api):
    client, host, upstream, _ = api
    sid = session(client, host, upstream)
    headers = {"X-Research-Data-Key": host.datahub.control["token"]}
    response = client.post(
        "/api/research/internal/data/knowledge-query",
        json={"session_id": sid, "query": "q"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    hit_id = response.json()["items"][0]["hit_id"]
    result = client.post(
        "/api/research/internal/data/knowledge-read",
        json={"session_id": sid, "hit_id": hit_id},
        headers=headers,
    )
    assert result.status_code == 200 and result.json()["content"] == "A cited paragraph"
    selected = {"session_id": sid, "hit_ids": [hit_id]}
    assert client.post("/api/research/knowledge/freeze", json=selected).status_code == 403
    frozen = client.post(
        "/api/research/knowledge/freeze", json=selected, headers={"X-Research-User-Action": "?1"}
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["historical_eligible"] is False


def test_current_callback_rejects_caller_chosen_account_kb_or_path(api):
    client, host, upstream, _ = api
    sid = session(client, host, upstream)
    headers = {"X-Research-Data-Key": host.datahub.control["token"]}
    for field, value in (
        ("knowledge_base_ids", ["other"]),
        ("owner", "other"),
        ("path", "/private"),
    ):
        response = client.post(
            "/api/research/internal/data/knowledge-query",
            json={"session_id": sid, "query": "q", field: value},
            headers=headers,
        )
        assert response.status_code == 422
    assert not (host.store.root / "knowledge-backend/receipts").exists()


def test_sync_routes_require_user_action_and_keep_external_host_supported(api):
    client, _, _, _ = api
    assert client.get("/api/research/knowledge/sync").status_code == 200
    assert (
        client.post(
            "/api/research/knowledge/sync/config",
            json={"knowledge_base_id": "kb1", "enabled": True},
        ).status_code
        == 403
    )
    assert client.post("/api/research/knowledge/sync/scan", json={}).status_code == 403
    assert _service_only_route_allowed("GET", "/api/research/knowledge/sync")
    assert _service_only_route_allowed("POST", "/api/research/knowledge/sync/config")
    assert _service_only_route_allowed("POST", "/api/research/knowledge/sync/scan")


class Scheduler:
    def __init__(self):
        self.running = False
        self.jobs = {}

    def add_job(self, callback, trigger, **kwargs):
        self.jobs[kwargs["id"]] = {"callback": callback, "trigger": trigger, **kwargs}

    def start(self):
        self.running = True

    def get_job(self, name):
        return self.jobs.get(name)

    def remove_job(self, name):
        self.jobs.pop(name)


@pytest.mark.asyncio
async def test_service_only_start_arms_existing_scheduler_without_automation_history():
    class Sync:
        def status(self):
            return {"enabled": True}

    class Automations:
        scheduler = Scheduler()

        async def start(self):
            raise AssertionError("must not resume unrelated automations")

    host = object.__new__(host_module.ResearchService)
    host.service_only = True
    host.automations = Automations()
    host.knowledge = type(
        "Knowledge", (), {"sync": Sync(), "sync_status": lambda self: self.sync.status()}
    )()
    await host.start()
    job = host.automations.scheduler.get_job("knowledge-directory-sync")
    assert job["seconds"] == 60 and job["max_instances"] == 1 and job["coalesce"] is True
    assert host.automations.scheduler.running


@pytest.mark.asyncio
@pytest.mark.parametrize("service_only", [False, True])
async def test_knowledge_start_preserves_tenant_discovery_recovery(
    tmp_path, monkeypatch, service_only
):
    from app.research_web.store import Store
    from tests.research_web import test_discovery_tracking as tracking_fixtures
    from tests.research_web.test_api import NativeFixture

    tracking, previous, discovery = tracking_fixtures.setup(tmp_path / "owner")
    saved = await tracking.save(tracking_fixtures.body(discovery))
    tracking.enable(saved["id"], saved["definition_version"])
    assert tracking.has_enabled()
    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    monkeypatch.setenv("RWB_DISCOVERY_TRACKING_ENABLED", "1")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED", "0")
    host = host_module.ResearchService(NativeFixture(), Store(previous.store.root))
    host.service_only = service_only
    host.automations.now = previous.automations.now

    class Sync:
        def status(self):
            return {"enabled": True}

        def close(self):
            pass

    host.knowledge.sync = Sync()
    try:
        await host.start()
        assert host.automations.scheduler.get_job("knowledge-directory-sync") is not None
        restored = host.automations.scheduler.get_job("automation:" + saved["id"])
        assert (restored is not None) is (not service_only)
        assert host.automations.list_runs()["items"] == []
    finally:
        await host.close()
