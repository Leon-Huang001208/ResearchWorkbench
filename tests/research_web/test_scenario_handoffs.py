"""Scenario routes use real Store/catalog/snapshots and an offline native fixture."""

import copy
from uuid import uuid4

import pytest
import test_multiuser_gateway as gateway_fixtures
import test_workbench_operations as workbench_fixtures
from test_api import isolated_keyring  # noqa: F401
from test_multiuser_gateway import login

from app.research_web.client import RuntimeFailure
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.scenario_handoffs import requirements, selection, trusted_context
from app.research_web.scenarios import read_scenarios
from app.research_web.scenarios.pack_catalog import contracts as pack_contracts
from app.research_web.store import Store, StoreError

api = workbench_fixtures.api
server = gateway_fixtures.server


def test_scenario_catalog_is_read_only_and_reports_real_eligibility(api):
    client, service = api
    before = set(service.store.data["sessions"])
    response = client.get("/api/research/scenarios")
    assert response.status_code == 200, response.text
    assert [r["id"] for r in response.json()["items"]] == [
        r["id"] for r in [*read_scenarios(), *pack_contracts()]
    ]
    assert set(service.store.data["sessions"]) == before
    assert all("capabilities" in r for r in response.json()["items"])


def test_changed_handoff_replay_is_conflict(api):
    client, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    body = {
        "source_session_id": sid,
        "target_mode": "fingpt",
        "section": "assets",
        "context": {"a": 1},
    }
    headers = {"Idempotency-Key": "changed-request-test"}
    assert client.post("/api/research/handoffs", json=body, headers=headers).status_code == 201
    body["context"]["a"] = 2
    assert client.post("/api/research/handoffs", json=body, headers=headers).status_code == 409


@pytest.mark.parametrize("scenario", read_scenarios(), ids=lambda row: row["id"])
def test_client_cannot_certify_scenario_evidence(api, scenario):
    client, _ = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    body = {
        "source_session_id": sid,
        "target_mode": "fingpt",
        "section": "assets",
        "scenario_id": scenario["id"],
        "scenario_inputs": {**scenario["examples"][0], "evidence_eligibility": {"eligible": True}},
    }
    result = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "invalid-input-test"}
    )
    assert result.status_code == 422, result.text


def scenario_body(scenario_id="company-onepager"):
    return {
        "target_mode": "fingpt",
        "section": "assets",
        "scenario_id": scenario_id,
        "scenario_inputs": {
            "subject": {"kind": "stock", "identity": "600600.SH"},
            "as_of": "2026-10-26",
            "question": "核对盈利与证据缺口",
            "material_ids": [],
        },
    }


@pytest.mark.parametrize("scenario", read_scenarios(), ids=lambda row: row["id"])
def test_all_eight_methods_outputs_and_missing_reach_server_requirements(api, scenario):
    _, service = api
    selected = selection(service, scenario["id"], scenario["examples"][0])
    actual = requirements(selected)
    assert set(scenario["steps"]).issubset(actual)
    assert scenario["examples"][0]["as_of"] in actual[0]
    assert scenario["examples"][0]["subject"]["identity"] in actual[0]
    assert any("冻结证据缺口" in item for item in actual)
    assert any(all(x in item for x in scenario["expected_artifacts"]) for item in actual)


def test_prepare_freezes_and_revalidates_cutoff_scope_and_evidence(api):
    client, service = api
    source = client.post("/api/research/sessions", json={}).json()["id"]
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600600.SH"}
    )
    dataset = service.datahub.snapshots.publish(
        source,
        query,
        Result(
            rows=[{"date": "2026-06-30", "revenue": 100}],
            raw=[b"original financial"],
            status="snapshot",
            as_of="2026-06-30",
        ),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
    )
    body = scenario_body()
    body.update(source_session_id=source, dataset_ids=[dataset["dataset_id"]])
    body["scenario_inputs"]["material_ids"] = body["dataset_ids"]
    result = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "frozen-scenario-test"}
    )
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["scenario_context"]["scenario"]["status"] == "incomplete"
    context = trusted_context(service, record["session_id"])
    assert context["scenario"]["inputs"]["as_of"] == "2026-10-26"
    assert service.store.session(record["session_id"])["source_scope"] == ["datahub"]
    service.store.session(source)["source_scope"] = ["web"]
    with pytest.raises(StoreError, match="授权"):
        trusted_context(service, record["session_id"])
    target = record["session_id"]
    copied = service.datahub.snapshots.ids(target)[0]
    for path in [
        f"/api/research/sessions/{target}/datasets/{copied}/rows",
        f"/api/research/sessions/{target}/datasets/{copied}/files/rows.json",
        record["context_file"]["url"],
    ]:
        assert client.get(path).status_code == 403


def test_unknown_creation_survives_store_reload_without_second_create(api, monkeypatch):
    client, service = api
    calls = []

    async def lost(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeFailure("lost", "fixture_lost")

    monkeypatch.setattr(service, "create", lost)
    body = scenario_body()
    headers = {"Idempotency-Key": "unknown-create-scenario"}
    response = client.post("/api/research/handoffs", json=body, headers=headers)
    assert response.status_code >= 400
    loaded = Store(service.store.root)
    assert len(loaded.data["handoffs"]) == 1
    assert (
        client.get("/api/research/handoff-requests/unknown-create-scenario").json()["state"]
        == "creation_outcome_unknown"
    )
    replay = client.post("/api/research/handoffs", json=body, headers=headers)
    assert replay.json()["state"] == "creation_outcome_unknown"
    assert len(calls) == 1
    changed = copy.deepcopy(body)
    changed["scenario_inputs"]["as_of"] = "2026-10-25"
    assert client.post("/api/research/handoffs", json=changed, headers=headers).status_code == 409


def test_foreign_observation_and_forged_subject_fail_before_creation(api):
    client, service = api
    source = client.post("/api/research/sessions", json={}).json()["id"]
    other = client.post("/api/research/sessions", json={}).json()["id"]
    oid = str(uuid4())
    service.store.data["asset_observations"][oid] = {
        "session_id": other,
        "asset": "600600.SH",
        "asset_type": "stock",
        "blocks": {},
    }
    body = scenario_body()
    body.update(source_session_id=source, observation_id=oid)
    before = len(service.store.data["sessions"])
    result = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "foreign-observation"}
    )
    assert result.status_code == 403
    assert len(service.store.data["sessions"]) == before


def test_disabled_technicals_stays_blocked_and_cannot_use_alternate_capability(api):
    client, service = api
    body = scenario_body("technicals")
    before = len(service.store.data["sessions"])
    response = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "technical-disabled-test"}
    )
    assert response.status_code == 409, response.text
    assert len(service.store.data["sessions"]) == before


def test_new_reads_follow_authenticated_account_gateway(server):
    browser, _store, _pool, users, forwarded = server
    for path in ["/api/research/scenarios", "/api/research/handoff-requests/known-request"]:
        assert browser.get(path).status_code == 401
    assert login(browser).status_code == 200
    for path in ["/api/research/scenarios", "/api/research/handoff-requests/known-request"]:
        response = browser.get(path)
        assert response.status_code == 200
        assert response.json()["owner"] == users[1].id
    assert forwarded[-1].headers["x-rwb-tenant-gateway-key"] == users[1].id


@pytest.mark.asyncio
async def test_backend_reads_require_tenant_gateway_secret(tmp_path, monkeypatch):
    from test_multiuser_runtime import request

    from app.research_web import tenant_policy

    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    key = tmp_path / "gateway.key"
    key.write_text("g" * 43)
    key.chmod(0o600)
    monkeypatch.setenv("RWB_TENANT_GATEWAY_KEY_FILE", str(key))
    headers = [(tenant_policy.GATEWAY_HEADER.lower().encode(), b"g" * 43)]
    for path in ["/api/research/scenarios", "/api/research/handoff-requests/known-request"]:
        assert (await tenant_policy.check_request(request(path))).status_code == 403
        assert await tenant_policy.check_request(request(path, headers=headers)) is None


def test_actual_send_binds_server_requirements_and_cutoff_to_native_payload(api, monkeypatch):
    client, service = api
    body = scenario_body("news-query")
    prepared = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "actual-send-scene"}
    )
    assert prepared.status_code == 201, prepared.text
    sid = prepared.json()["session_id"]
    calls = []
    original = service.client.rpc

    async def native(method, payload):
        calls.append((method, payload))
        if method == "skill.list":
            return {
                "skills": [
                    {"name": row["native_name"]}
                    for row in service.capabilities.list()["items"]
                    if row["enabled"]
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", native)
    # The offline native/model fixture supplies its tool support proof. Host
    # capability/data readiness, receipts and quality contract remain real.
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid=None: True)
    message = {"text": "确认按冻结材料查询", "expected_formats": []}
    mismatch = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={**message, "research_as_of": "2026-10-25"},
        headers={"Idempotency-Key": "mismatch-scene-send"},
    )
    assert mismatch.status_code == 409
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json=message,
        headers={"Idempotency-Key": "actual-scene-send"},
    )
    assert response.status_code == 202, response.text
    receipt = service.store.receipt(sid, "actual-scene-send")
    assert receipt["research_contract"]["as_of"] == "2026-10-26"
    encoded = str(receipt["research_contract"])
    for step in prepared.json()["scenario_context"]["scenario"]["contract"]["steps"]:
        assert step in encoded
    prompts = [payload for method, payload in calls if method == "session.prompt"]
    assert len(prompts) == 1
    assert "Host冻结场景要求" in str(prompts[0])
    assert "news-query" in str(prompts[0])
    assert (
        client.post(
            f"/api/research/sessions/{sid}/messages",
            json=message,
            headers={"Idempotency-Key": "actual-scene-send"},
        ).status_code
        == 202
    )
    assert sum(method == "session.prompt" for method, _ in calls) == 1


def test_discovery_scenario_freezes_real_bundle_and_explicitly_executes_once(api, monkeypatch):
    from test_discovery import ARTICLE, EVENT

    client, service = api
    calls, native_sessions = [], {}
    original = service.client.rpc

    async def native(method, payload):
        calls.append((method, payload))
        if method == "skill.list":
            return {
                "skills": [
                    {"name": row["native_name"]}
                    for row in service.capabilities.list()["items"]
                    if row["enabled"]
                ]
            }
        if method == "session.create":
            native_sessions[payload["sessionId"]] = {
                "sessionId": payload["sessionId"],
                "cwd": payload["cwd"],
                "running": False,
            }
        if method == "session.list":
            return {"items": list(native_sessions.values())}
        return await original(method, payload)

    async def reader(path, params=None):
        if path == "/radar":
            return {"industries": [], "stats": {}}
        if path == "/intelligence":
            return {
                "as_of": None,
                "cache_stale": False,
                "logics": [],
                "reading": [copy.deepcopy(EVENT)],
            }
        return {
            "event": copy.deepcopy(EVENT),
            "articles": [copy.deepcopy(ARTICLE)],
            "revisions": [],
        }

    monkeypatch.setattr(service.client, "rpc", native)
    monkeypatch.setattr(service.discovery, "reader", reader)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid=None: True)
    feed = client.get("/api/research/discovery/feed").json()
    theme = feed["themes"][0]
    preview = client.get(
        "/api/research/discovery/selection",
        params={"feed_id": feed["feed_id"], "theme_id": theme["id"]},
    ).json()
    material_ids = [x["id"] for x in preview["themes"][0]["materials"]]
    values = scenario_body("news-query")["scenario_inputs"]
    values["material_ids"] = material_ids
    body = {
        "request_id": str(uuid4()),
        "feed_id": preview["feed_id"],
        "theme_id": theme["id"],
        "horizon": "medium",
        "material_ids": material_ids,
        "question": values["question"],
        "scenario_id": "news-query",
        "scenario_inputs": values,
    }
    headers = {"X-Research-User-Action": "?1"}
    bad = copy.deepcopy(body)
    bad["scenario_inputs"]["as_of"] = "2000-01-01"
    assert (
        client.post("/api/research/discovery/prepare", json=bad, headers=headers).status_code == 409
    )
    prepared = client.post("/api/research/discovery/prepare", json=body, headers=headers)
    assert prepared.status_code == 200, prepared.text
    frozen = prepared.json()
    assert frozen["scenario_context"]["scenario"]["inputs"]["as_of"] == "2026-10-26"
    assert sum(method == "session.prompt" for method, _ in calls) == 0
    hid = frozen["handoff_id"]
    result = client.post(
        f"/api/research/discovery/handoffs/{hid}/execute",
        json={"request_id": str(uuid4())},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "running", result.text
    assert sum(method == "session.prompt" for method, _ in calls) == 1
    replay = client.post(
        f"/api/research/discovery/handoffs/{hid}/execute",
        json={"request_id": str(uuid4())},
        headers=headers,
    )
    assert replay.status_code == 200
    assert sum(method == "session.prompt" for method, _ in calls) == 1
