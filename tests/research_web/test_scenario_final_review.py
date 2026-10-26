"""Real Host regressions for frozen projections and pre-create outcome proof."""

import copy
import json

import pytest
import test_workbench_operations as fixtures
from test_api import isolated_keyring  # noqa: F401
from test_asset_research_workspace import bundle, seed
from test_scenario_handoffs import scenario_body

from app.research_web.store import Store, StoreError

api = fixtures.api


def workspace(client, service):
    oid, sid, dataset = seed(client, service, "600600.SH")
    peer, _, peer_data = seed(client, service, "601318.SH")
    value = bundle(sid, dataset, service)
    imported = client.post(
        f"/api/research/assets/research/import/{oid}",
        files={"file": ("workspace.json", json.dumps(value).encode(), "application/json")},
    )
    assert imported.status_code == 201, imported.text
    material = imported.json()["material"]
    selected = [dataset["dataset_id"], peer_data["dataset_id"]]
    body = scenario_body()
    body.update(
        source_session_id=sid,
        observation_id=oid,
        comparison_observation_ids=[peer],
        dataset_ids=selected,
        workspace_material=material,
        source_scope=["datahub", "uploads"],
    )
    body["scenario_inputs"]["material_ids"] = [*selected, "file:" + material["file_id"]]
    return sid, body, value["summaries"][0]["text"]


@pytest.mark.parametrize("revoked", ["datahub", "uploads"])
def test_every_frozen_projection_rechecks_original_permission(api, revoked):
    client, service = api
    sid, body, secret = workspace(client, service)
    headers = {"Idempotency-Key": "workspace-revoked-projections"}
    first = client.post("/api/research/handoffs", json=body, headers=headers)
    assert first.status_code == 201, first.text
    target = first.json()["session_id"]
    assert secret in json.dumps(
        client.get(f"/api/research/sessions/{target}").json(), ensure_ascii=False
    )
    legacy_body = {
        "source_session_id": target,
        "target_mode": "fingpt",
        "section": "assets",
        "dataset_ids": service.datahub.snapshots.ids(target),
        "context": {"selected_text": secret},
    }
    legacy_headers = {"Idempotency-Key": "legacy-revoked-projection"}
    legacy = client.post("/api/research/handoffs", json=legacy_body, headers=legacy_headers)
    assert legacy.status_code == 201, legacy.text
    descendant = legacy.json()["session_id"]
    service.store.session(sid)["source_scope"].remove(revoked)
    service.store.save()
    before = len(service.store.data["sessions"])
    assert client.get(first.json()["context_file"]["url"]).status_code == 403
    detail = client.get(f"/api/research/sessions/{target}")
    assert detail.status_code == 403, detail.text
    assert client.get(f"/api/research/sessions/{descendant}").status_code == 403
    assert client.get(legacy.json()["context_file"]["url"]).status_code == 403
    for response in [
        client.get("/api/research/handoff-requests/workspace-revoked-projections"),
        client.post("/api/research/handoffs", json=body, headers=headers),
    ]:
        assert response.status_code in {200, 201}, response.text
        public = response.json()
        assert public["state"] == "context_unavailable"
        assert public["creation_state"] == "prepared"
        assert public["session_id"] == target
        assert not (
            {"scenario_context", "lineage", "draft", "copied_files", "context_file"} & public.keys()
        )
        assert secret not in json.dumps(public, ensure_ascii=False)
    assert len(service.store.data["sessions"]) == before
    for response in [
        client.get("/api/research/handoff-requests/legacy-revoked-projection"),
        client.post("/api/research/handoffs", json=legacy_body, headers=legacy_headers),
    ]:
        assert response.json()["state"] == "context_unavailable"
        assert "lineage" not in response.json()
        assert secret not in json.dumps(response.json(), ensure_ascii=False)
    service.store.session(sid)["source_scope"].append(revoked)
    assert client.get(f"/api/research/sessions/{target}").status_code == 200
    assert client.get(f"/api/research/sessions/{descendant}").status_code == 200
    assert (
        client.get("/api/research/handoff-requests/workspace-revoked-projections").json()["state"]
        == "prepared"
    )


def test_missing_comparison_is_proved_unsent_then_correctable(api):
    client, service = api
    _, body, _ = workspace(client, service)
    bad = copy.deepcopy(body)
    bad["dataset_ids"] = body["dataset_ids"][:1]
    bad["scenario_inputs"]["material_ids"].remove(body["dataset_ids"][1])
    before = len(service.store.data["sessions"])
    headers = {"Idempotency-Key": "missing-comparison-correction"}
    rejected = client.post("/api/research/handoffs", json=bad, headers=headers)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "scenario_comparison_material_missing"
    assert rejected.json()["error"]["handoff_outcome"] == "not_created"
    assert len(service.store.data["sessions"]) == before
    assert service.store.data["handoffs"] == {}
    missing = client.get("/api/research/handoff-requests/missing-comparison-correction")
    assert missing.status_code == 404
    assert "handoff_outcome" not in missing.json()["error"]
    corrected = client.post("/api/research/handoffs", json=body, headers=headers)
    assert corrected.status_code == 201, corrected.text
    assert len(service.store.data["sessions"]) == before + 1
    assert (
        corrected.json()["scenario_context"]["comparisons"][0]["subject"]["identity"] == "601318.SH"
    )
    conflict = client.post("/api/research/handoffs", json=bad, headers=headers)
    assert conflict.status_code == 409
    assert "handoff_outcome" not in conflict.json()["error"]


def test_unknown_intent_is_bodyless_and_never_reclassified_unsent(api, monkeypatch):
    client, service = api
    _, body, secret = workspace(client, service)
    calls = []

    async def lost(*args, **kwargs):
        calls.append(1)
        raise StoreError("创建后回执丢失", "scenario_inputs_invalid", 422)

    monkeypatch.setattr(service, "create", lost)
    headers = {"Idempotency-Key": "unknown-after-intent"}
    rejected = client.post("/api/research/handoffs", json=body, headers=headers)
    assert rejected.status_code == 422
    assert "handoff_outcome" not in rejected.json()["error"]
    service.store = Store(service.store.root)
    for response in [
        client.get("/api/research/handoff-requests/unknown-after-intent"),
        client.post("/api/research/handoffs", json=body, headers=headers),
    ]:
        public = response.json()
        assert public["state"] == "creation_outcome_unknown"
        assert set(public) <= {"id", "state", "mode"}
        assert secret not in json.dumps(public, ensure_ascii=False)
    assert calls == [1]
