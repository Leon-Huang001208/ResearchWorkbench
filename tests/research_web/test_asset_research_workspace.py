"""Positive owned-data workspace path plus strict source/contract counterexamples."""

import hashlib
import json
from uuid import uuid4

import pytest
import test_workbench_operations as fixtures
from test_api import isolated_keyring  # noqa: F401

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result

api = fixtures.api


def seed(client, service, asset, period="2026-06-30", unit="万元"):
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    query = BusinessQuery(capability="financials", source="akshare", parameters={"asset": asset})
    dataset = service.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[
                {
                    "asset": asset,
                    "report_period": period,
                    "revenue": 120,
                    "relation_note": "600600.SH向601318.SH供应包装材料",
                }
            ],
            raw=[b"offline owned disclosure"],
            status="snapshot",
            fields=[{"name": "revenue", "unit": unit, "currency": "CNY", "basis": "合并累计"}],
            as_of=period,
        ),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
    )
    oid = str(uuid4())
    service.store.data["asset_observations"][oid] = {
        "id": oid,
        "session_id": sid,
        "asset": asset,
        "asset_type": "stock",
        "source": "akshare",
        "status": "completed",
        "created_at": 1,
        "updated_at": 1,
        "blocks": {"financials": {"status": "complete", "dataset": dataset}},
        "request": {"end_date": "2026-10-26", "frequency": "daily", "adjustment": "none"},
    }
    service.store.save()
    return oid, sid, dataset


def bundle(sid, dataset, service):
    raw = service.datahub.snapshots.read(sid, dataset["dataset_id"], "rows.json")
    proof = {
        "source_session_id": sid,
        "reference": {"type": "dataset", "id": dataset["dataset_id"]},
        "sha256": hashlib.sha256(raw).hexdigest(),
        "locator": {
            "kind": "json-cell",
            "row": 0,
            "field": "relation_note",
            "quote": "600600.SH向601318.SH供应包装材料",
        },
    }
    return {
        "schema": "asset-research-workspace/v1",
        "subject": "600600.SH",
        "summaries": [
            {
                "id": "summary-one",
                "title": "经营资料摘录",
                "text": proof["locator"]["quote"],
                "evidence": [proof],
            }
        ],
        "relations": [
            {
                "id": "supply-one",
                "from_identity": "600600.SH",
                "to_identity": "601318.SH",
                "relation": "供应包装材料",
                "evidence": [proof],
            }
        ],
    }


def test_import_readable_summary_comparison_and_relations_without_model(api):
    client, service = api
    oid, sid, dataset = seed(client, service, "600600.SH")
    peer, _, _ = seed(client, service, "601318.SH", "2026-03-31", "元")
    value = bundle(sid, dataset, service)
    response = client.post(
        f"/api/research/assets/research/import/{oid}",
        files={
            "file": (
                "workspace.json",
                json.dumps(value, ensure_ascii=False).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    imported = response.json()["material"]
    preview = client.post(
        "/api/research/assets/research/preview",
        json={"observation_id": oid, "comparison_observation_ids": [peer], "material": imported},
    )
    assert preview.status_code == 200, preview.text
    result = preview.json()
    assert result["summaries"][0]["text"] == value["summaries"][0]["text"]
    assert result["summaries"][0]["quality"] == "not_assessed"
    assert result["relations"][0]["status"] == "source_claim_unverified"
    assert len(result["comparisons"]) == 2
    rows = [item["records"][0] for item in result["comparisons"]]
    assert [row["period"] for row in rows] == ["2026-06-30", "2026-03-31"]
    assert [row["units"]["revenue"]["unit"] for row in rows] == ["万元", "元"]
    assert result["comparison_policy"] == "side_by_side_original_values_no_ranking"
    assert result["required_source_scope"] == ["datahub", "uploads"]
    assert len(service.store.data["sessions"]) == 2
    from test_scenario_handoffs import scenario_body

    selected = [
        dataset["dataset_id"] for item in result["comparisons"] for dataset in item["datasets"]
    ]
    body = scenario_body()
    body.update(
        source_session_id=sid,
        observation_id=oid,
        comparison_observation_ids=[peer],
        dataset_ids=selected,
        workspace_material=imported,
    )
    body["scenario_inputs"]["material_ids"] = [*selected, "file:" + imported["file_id"]]
    denied_scope = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "workspace-scope-denied"}
    )
    assert denied_scope.status_code == 422
    body["source_scope"] = ["datahub", "uploads"]
    frozen = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "workspace-confirmed"}
    )
    assert frozen.status_code == 201, frozen.text
    target = frozen.json()["session_id"]
    assert frozen.json()["scenario_context"]["comparisons"][0]["subject"]["identity"] == "601318.SH"
    assert len(frozen.json()["scenario_context"]["frozen_files"]) == 1
    assert len(service.datahub.snapshots.ids(target)) == 2
    service.store.session(sid)["source_scope"] = ["web"]
    denied = client.post(
        "/api/research/assets/research/preview", json={"observation_id": oid, "material": imported}
    )
    assert denied.status_code in {403, 409}
    source = client.get(result["relations"][0]["evidence"][0]["url"])
    assert source.status_code == 403
    assert client.get(frozen.json()["context_file"]["url"]).status_code == 403


@pytest.mark.parametrize("mutation", ["hash", "locator", "subject", "quality"])
def test_workspace_rejects_unbound_or_self_certified_material_before_import(api, mutation):
    client, service = api
    oid, sid, dataset = seed(client, service, "600600.SH")
    value = bundle(sid, dataset, service)
    if mutation == "hash":
        value["summaries"][0]["evidence"][0]["sha256"] = "0" * 64
    if mutation == "locator":
        value["summaries"][0]["evidence"][0]["locator"]["quote"] = "未出现在原件中的关系"
    if mutation == "subject":
        value["subject"] = "601318.SH"
    if mutation == "quality":
        value["quality"] = "passed"
    result = client.post(
        f"/api/research/assets/research/import/{oid}",
        files={"file": ("workspace.json", json.dumps(value).encode(), "application/json")},
    )
    assert result.status_code in {409, 422}, result.text
    assert not any(
        "asset-research/" in str(path) for path in service.store.session(sid)["files"].values()
    )
