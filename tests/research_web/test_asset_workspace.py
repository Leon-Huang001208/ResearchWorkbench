"""Asset workspace state, personal observations and alert regressions."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    async def rpc(self, method, payload):
        if method == "host.describe":
            return {"version": "fixture", "provider": "fixture", "cwd": payload.get("cwd")}
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": True}}}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def api(tmp_path: Path):
    service = ResearchService(NativeFixture(), Store(tmp_path))

    async def query(sid, call_id, request):
        capability = request.capability
        if capability == "market_snapshot":
            return {
                "dataset_id": "11111111-1111-1111-1111-111111111111",
                "name": "贵州茅台快照",
                "capability": capability,
                "source": "akshare",
                "provider": "akshare",
                "status": "snapshot",
                "row_count": 1,
                "as_of": "2026-09-05T07:00:00+00:00",
                "actual_range": {"start_date": None, "end_date": None},
                "missing": [],
                "limitations": [],
                "files": [],
                "sample": [{"asset": "600519", "price": 1500.0, "change_pct": 2.1}],
            }
        if capability == "market_bars":
            return {
                "dataset_id": "22222222-2222-2222-2222-222222222222",
                "name": "贵州茅台历史行情",
                "capability": capability,
                "source": "akshare",
                "provider": "akshare",
                "status": "complete",
                "row_count": 2,
                "as_of": "2026-09-05",
                "actual_range": {"start_date": "2026-09-04", "end_date": "2026-09-05"},
                "missing": [],
                "limitations": [],
                "files": [],
                "sample": [
                    {"date": "2026-09-04", "close": 1490.0, "volume": 10},
                    {"date": "2026-09-05", "close": 1500.0, "volume": 11},
                ],
            }
        raise ValueError("provider unavailable")

    service.datahub.query = query
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service


def _wait(client, observation_id):
    for _ in range(50):
        item = client.get(f"/api/research/assets/observations/{observation_id}").json()
        if item["status"] != "running":
            return item
    return item


def test_asset_observation_tracks_each_block_and_freezes_handoff_context(api):
    client, _ = api
    response = client.post(
        "/api/research/assets/observations",
        json={
            "asset": "600519.SH",
            "asset_type": "stock",
            "sections": ["overview", "history", "financials"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
        headers={"Idempotency-Key": "asset-observation-0001"},
    )
    assert response.status_code == 202, response.text
    repeated = client.post(
        "/api/research/assets/observations",
        json={
            "asset": "600519.SH",
            "asset_type": "stock",
            "sections": ["overview", "history", "financials"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
        headers={"Idempotency-Key": "asset-observation-0001"},
    )
    assert repeated.json()["id"] == response.json()["id"]

    item = _wait(client, response.json()["id"])
    assert item["status"] == "partial"
    assert item["blocks"]["overview"]["status"] == "complete"
    assert item["blocks"]["history"]["status"] == "complete"
    assert item["blocks"]["financials"]["status"] == "error"
    assert item["dataset_ids"] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    assert "sample" not in item["blocks"]["overview"]["dataset"]


def test_watchlist_notes_and_alert_false_to_true_deduplication(api):
    client, service = api
    watchlist = client.post("/api/research/watchlists", json={"name": "核心观察"}).json()
    added = client.post(
        f"/api/research/watchlists/{watchlist['id']}/items",
        json={"asset": "600519.SH", "asset_type": "stock", "name": "贵州茅台"},
    )
    assert added.status_code == 201
    duplicate = client.post(
        f"/api/research/watchlists/{watchlist['id']}/items",
        json={"asset": "600519.SH", "asset_type": "stock", "name": "贵州茅台"},
    )
    assert duplicate.status_code == 409

    note = client.post(
        "/api/research/asset-notes",
        json={"asset": "600519.SH", "text": "关注渠道库存。"},
    ).json()
    patched = client.patch(
        f"/api/research/asset-notes/{note['id']}", json={"text": "关注渠道库存与批价。"}
    ).json()
    assert patched["text"].endswith("批价。")

    alert = client.post(
        "/api/research/asset-alerts",
        json={
            "asset": "600519.SH",
            "field": "price",
            "operator": "gte",
            "threshold": 1499,
            "cooldown_minutes": 60,
        },
    ).json()
    first = service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1500.0, "as_of": "2026-09-05"}
    )
    second = service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1501.0, "as_of": "2026-09-05"}
    )
    assert len(first) == 1
    assert second == []
    assert client.get("/api/research/asset-notifications").json()["items"][0]["alert_id"] == alert["id"]

    # stale/unavailable never trigger; a false result resolves the active edge.
    assert service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "unavailable", "price": 1600.0}
    ) == []
    service.asset_workspace.evaluate_alerts(
        "600519.SH", {"status": "snapshot", "price": 1400.0, "as_of": "2026-09-05"}
    )
    assert service.store.data["asset_alerts"][alert["id"]]["condition_active"] is False


def test_personal_asset_resources_reject_unknown_ids_and_bad_polling(api):
    client, _ = api
    assert client.patch(
        "/api/research/asset-notes/00000000-0000-0000-0000-000000000000",
        json={"text": "x"},
    ).status_code == 400
    assert client.post("/api/research/watchlists", json={"name": "x", "polling_minutes": 10}).status_code == 422
