"""Framework contracts, safe storage, routes and DSH binding regressions."""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.research_web.frameworks.base import FrameworkError
from app.research_web.frameworks.goldar.seed import build_seed
from app.research_web.frameworks.goldar.store import GoldSnapshotStore
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    def __init__(self):
        self.calls = []

    async def rpc(self, method, payload):
        self.calls.append((method, payload))
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": [{"name": "framework-research"}]}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def framework_api(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def test_catalog_and_gold_data_use_versioned_specific_contract(framework_api):
    client, _, _ = framework_api
    catalog = client.get("/api/research/frameworks")
    assert catalog.status_code == 200
    assert [item["slug"] for item in catalog.json()["items"]] == ["gold"]

    response = client.get("/api/research/frameworks/gold/data")
    assert response.status_code == 200
    payload = response.json()
    assert payload["framework"]["version"] == "1.0.0"
    assert payload["framework"]["source_revision"] == "758ae3848d"
    assert payload["snapshot"]["status"] == "待核验"
    assert payload["snapshot"]["options"]["sources"][0]["proxy"] is True
    assert "funds" not in payload["snapshot"]


def test_framework_session_is_bound_to_exact_snapshot_and_safe_preset(framework_api):
    client, native, service = framework_api
    revision = client.get("/api/research/frameworks/gold/data").json()["snapshot"]["revision"]
    response = client.post(
        "/api/research/frameworks/gold/sessions",
        json={"snapshot_revision": revision, "focus_section": "drivers"},
    )
    assert response.status_code == 201, response.text
    sid = response.json()["session"]["id"]
    creation = [call for call in native.calls if call[0] == "session.create"][-1][1]
    assert creation["agentPreset"] == "framework-explain"
    assert service.store.session(sid)["framework_binding"]["snapshot_revision"] == revision

    stale = client.post(
        f"/api/research/frameworks/gold/sessions/{sid}/messages",
        headers={"Idempotency-Key": "framework-stale-1"},
        json={"text": "解释实际利率", "expected_snapshot_revision": "f" * 64},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "framework_snapshot_changed"


def test_framework_explain_and_explicit_verify_use_separate_dsh_presets(framework_api):
    client, native, _ = framework_api
    revision = client.get("/api/research/frameworks/gold/data").json()["snapshot"]["revision"]
    created = client.post(
        "/api/research/frameworks/gold/sessions", json={"snapshot_revision": revision}
    ).json()
    sid = created["session"]["id"]
    explain = client.post(
        f"/api/research/frameworks/gold/sessions/{sid}/messages",
        headers={"Idempotency-Key": "framework-explain-1"},
        json={
            "text": "为什么仍待核验？",
            "expected_snapshot_revision": revision,
            "mode": "explain",
        },
    )
    assert explain.status_code == 202, explain.text

    verified = client.post(
        f"/api/research/frameworks/gold/sessions/{sid}/verify",
        headers={"Idempotency-Key": "framework-verify-1"},
        json={
            "question": "核验央行购金数据",
            "expected_snapshot_revision": revision,
        },
    )
    assert verified.status_code == 202, verified.text
    creations = [payload for method, payload in native.calls if method == "session.create"]
    assert [item["agentPreset"] for item in creations[-2:]] == [
        "framework-explain",
        "framework-verify",
    ]
    prompts = [
        payload["content"][0]["text"]
        for method, payload in native.calls
        if method == "session.prompt"
    ]
    assert "当前模式没有网页检索" not in prompts[0]
    assert prompts[-1].startswith("/framework-research ")
    assert "深度验证" in prompts[-1]


def test_gold_snapshot_store_rejects_symlink_and_preserves_strict_revision(tmp_path):
    store = GoldSnapshotStore(tmp_path / "gold")
    snapshot = store.read()
    assert snapshot.revision == build_seed().revision

    real = tmp_path / "outside.json"
    real.write_text("{}", encoding="utf-8")
    store.path.unlink()
    os.symlink(real, store.path)
    with pytest.raises(FrameworkError, match="符号链接"):
        store.read()


def test_gold_snapshot_store_preserves_and_migrates_legacy_fixture(tmp_path):
    root = tmp_path / "gold"
    root.mkdir()
    legacy = {
        "market_context": {"price": 2400},
        "research_state": {"label": "待核验"},
        "pricing_drivers": {"factors": []},
    }
    (root / "snapshot.json").write_text(json.dumps(legacy), encoding="utf-8")

    store = GoldSnapshotStore(root)

    assert store.read().schema_version == 1
    assert json.loads((root / "snapshot.legacy-v0.json").read_text(encoding="utf-8")) == legacy


@pytest.mark.asyncio
async def test_framework_runtime_start_and_close_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    service = ResearchService(NativeFixture(), Store(tmp_path))
    await service.frameworks.start()
    await service.frameworks.start()
    assert service.frameworks._started is True
    await service.frameworks.close()
    await service.frameworks.close()
    assert service.frameworks._started is False
