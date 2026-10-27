"""Real Host snapshot reads, hashes and account/scope authorization."""

import json
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import test_scenario_handoffs as scenario_fixtures

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.store import StoreError

api = scenario_fixtures.api


@pytest.mark.parametrize("asset", ["600600.SH", "600600.sh"])
def test_owned_baostock_snapshot_maps_actual_units_and_missing_calendar(api, asset):
    from app.research_web.scenario_handoffs import verify_material
    from app.research_web.scenario_pack_inputs import qualify_pack_materials

    client, service = api
    price_day = (datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)).isoformat()
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    query = BusinessQuery(
        capability="market_bars",
        source="baostock",
        parameters={
            "asset": asset,
            "asset_type": "stock",
            "adjustment": "none",
            "start_date": price_day,
            "end_date": price_day,
        },
    )
    dataset = service.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[
                {
                    "asset": "600600.SH",
                    "date": price_day,
                    "close": 68.2,
                    "trading_status": True,
                    "adjustment": "none",
                }
            ],
            raw=[
                json.dumps(
                    [
                        {
                            "code": "sh.600600",
                            "date": price_day,
                            "close": "68.2",
                            "adjustflag": "3",
                            "tradestatus": "1",
                        }
                    ]
                ).encode()
            ],
            status="snapshot",
            fields={"close": {"unit": "currency_per_share", "currency": "CNY"}},
            metadata={
                "provider_semantics_revision": "baostock-raw-sh-sz-v1",
                "upstream_id": "baostock",
            },
        ),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("baostock"),
    )
    as_of = (
        datetime.fromisoformat(dataset["retrieved_at"])
        .astimezone(ZoneInfo("Asia/Shanghai"))
        .date()
        .isoformat()
    )
    values = {
        "subject": {"kind": "stock", "identity": "600600.SH"},
        "as_of": as_of,
        "question": "事件价格资料核验",
        "material_ids": [dataset["dataset_id"]],
        "research_scope": {"cutoff_at": as_of + "T23:59:59+08:00"},
    }
    metadata, manifest = verify_material(service, sid, dataset["dataset_id"], values)
    result = qualify_pack_materials(service, "event-review", values, [metadata])
    rows = result.input["records_by_kind"]["daily-price"]
    assert len(rows) == 1
    assert rows[0]["close"] == 68.2
    assert rows[0]["unit"] == "CNY_per_share"
    assert rows[0]["origin"]["published_at"] is None
    assert rows[0]["origin"]["locator"]["record_id"] == "0"
    assert rows[0]["origin"]["locator"]["location"] == "/0"
    assert result.status == "partial"
    assert not result.input["source_coverage"]
    assert any(
        gap["code"] == "required_kind_missing" and gap["kind"] == "exchange-session"
        for gap in result.missing
    )
    service.store.session(sid)["source_scope"] = ["web"]
    with pytest.raises(StoreError):
        qualify_pack_materials(service, "event-review", values, [metadata])
    service.store.session(sid)["source_scope"] = ["datahub"]
    private = service.store.root / manifest["raw_files"][0]["path"]
    private.write_bytes(b"changed original")
    with pytest.raises(StoreError) as changed:
        qualify_pack_materials(service, "event-review", values, [metadata])
    assert changed.value.code == "dossier_raw_changed"


def test_source_inputs_reject_unowned_reference_and_caller_authority(api):
    from app.research_web.scenario_pack_inputs import qualify_pack_materials

    _, service = api
    values = {
        "subject": {"kind": "stock", "identity": "600600.SH"},
        "as_of": "2026-10-26",
        "research_scope": {"cutoff_at": "2026-10-26T23:59:59+08:00"},
    }
    with pytest.raises(StoreError):
        qualify_pack_materials(
            service,
            "event-review",
            values,
            [
                {
                    "source_session_id": str(uuid4()),
                    "reference": {"type": "dataset", "id": str(uuid4())},
                }
            ],
        )
    values["research_scope"]["qualified"] = True
    with pytest.raises(StoreError) as error:
        qualify_pack_materials(service, "event-review", values, [])
    assert error.value.code == "pack_scope_invalid"
    values["research_scope"] = {
        "cutoff_at": "2026-10-26T23:59:59+08:00",
        "methods": {"join_risk_windows": {"category_coverage": []}},
    }
    with pytest.raises(StoreError) as coverage:
        qualify_pack_materials(service, "position-risk", values, [])
    assert coverage.value.code == "pack_scope_invalid"


def test_pack_prepare_is_read_only_and_handoff_seals_then_rechecks_bytes(api):
    from app.research_web.scenario_handoffs import trusted_context

    client, service = api
    body = {
        "target_mode": "fingpt",
        "section": "assets",
        "scenario_id": "pack-event-review",
        "scenario_inputs": {
            "subject": {"kind": "stock", "identity": "600600.SH"},
            "as_of": "2026-10-27",
            "question": "保留缺数据证据",
            "material_ids": [],
            "research_scope": {"cutoff_at": "2026-10-27T23:59:59+08:00"},
        },
    }
    before = set(service.store.data["sessions"])
    preview = client.post("/api/research/scenarios/pack-event-review/prepare", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["pack_qualification"]["status"] == "blocked"
    assert set(service.store.data["sessions"]) == before
    response = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "pack-seal-test"}
    )
    assert response.status_code == 201, response.text
    sid = response.json()["session_id"]
    context = trusted_context(service, sid, check_capabilities=False)
    seal = context["pack_seal"]
    path = service.store.root / "sessions" / sid / seal["input_path"]
    assert path.is_file()
    assert path.stat().st_mode & 0o222 == 0
    with pytest.raises(StoreError) as blocked:
        trusted_context(service, sid)
    assert blocked.value.code == "pack_inputs_blocked"
    path.chmod(0o600)
    path.write_text("{}")
    with pytest.raises(StoreError) as changed:
        trusted_context(service, sid, check_capabilities=False)
    assert changed.value.code == "pack_input_changed"


def test_seal_write_failure_preserves_created_session_and_never_claims_not_created(
    api, monkeypatch
):
    from app.research_web import scenario_pack_inputs

    client, service = api
    body = {
        "target_mode": "fingpt",
        "section": "assets",
        "scenario_id": "pack-research-prep",
        "scenario_inputs": {
            "subject": {"kind": "topic", "identity": "公开资料"},
            "as_of": "2026-10-27",
            "question": "核对资料",
            "material_ids": [],
            "research_scope": {"cutoff_at": "2026-10-27T23:59:59+08:00"},
        },
    }

    def failed(*_args):
        raise StoreError("封印写入中断", "pack_fixture_disk_error", 409)

    monkeypatch.setattr(scenario_pack_inputs, "seal_pack_inputs", failed)
    before = set(service.store.data["sessions"])
    headers = {"Idempotency-Key": "seal-write-failure"}
    response = client.post("/api/research/handoffs", json=body, headers=headers)
    assert response.status_code == 409, response.text
    assert "handoff_outcome" not in response.json()["error"]
    created = set(service.store.data["sessions"]) - before
    assert len(created) == 1
    observed = client.get("/api/research/handoff-requests/seal-write-failure").json()
    assert observed["session_id"] in created
    replay = client.post("/api/research/handoffs", json=body, headers=headers)
    assert replay.status_code == 201
    assert set(service.store.data["sessions"]) - before == created


def test_direct_pack_selection_without_host_scenario_never_sends_model_work(api, monkeypatch):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    calls = []
    original = service.client.rpc

    async def observed(method, payload):
        calls.append(method)
        if method == "skill.list":
            return {
                "skills": [
                    {"name": path.name}
                    for path in service.capabilities.prepare_native_root().iterdir()
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", observed)
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "核验包", "capability_id": "research-pack-event-review"},
        headers={"Idempotency-Key": "no-seal-no-model"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "pack_input_unsealed"
    assert "session.prompt" not in calls
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    loaded = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "tool_name": "skill",
            "native_name": "research-pack-event-review",
            "loaded": True,
        },
        headers=headers,
    )
    assert loaded.status_code == 409
    assert loaded.json()["error"]["code"] == "pack_input_unsealed"
