"""Framework contracts, safe storage, routes and DSH binding regressions."""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_capabilities import isolate_keyring

from app.research_web.capabilities.seeds import seed_packages
from app.research_web.frameworks.base import FrameworkError
from app.research_web.frameworks.dollar.contracts import DollarSnapshot
from app.research_web.frameworks.dollar.seed import build_seed as build_dollar_seed
from app.research_web.frameworks.dollar.store import DollarSnapshotStore
from app.research_web.frameworks.goldar.seed import build_seed
from app.research_web.frameworks.goldar.store import GoldSnapshotStore
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    def __init__(self):
        self.calls = []
        self.skill_names = ["framework-research"]

    async def rpc(self, method, payload):
        self.calls.append((method, payload))
        if method == "credentials.describe":
            return {"credentials": {ref: {"configured": True} for ref in payload["refs"]}}
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "credentials.describe":
            return {
                "credentials": {
                    ref: {"configured": True, "writable": True} for ref in payload["refs"]
                }
            }
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": [{"name": name} for name in self.skill_names]}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def framework_api(tmp_path, monkeypatch, request):
    isolate_keyring(monkeypatch)
    declared_web_only = getattr(request, "param", None) == "declared_web_only"
    if declared_web_only:
        # Preserve the production package for other tests; this fixture owns a
        # manual package with the ID required by FrameworkService.
        monkeypatch.setattr(
            "app.research_web.capabilities.catalog.seed_packages",
            lambda: [item for item in seed_packages() if item[0] != "framework-research"],
        )
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    if declared_web_only:
        candidate = next(draft for cid, draft in seed_packages() if cid == "framework-research")
        candidate["metadata"].update(
            name="合成网页验证",
            description="仅验证框架预设路由的网页工具测试包，不证明内置数据能力可用。",
            required_tools=["web_search"],
            data_requirements=[],
        )
        candidate.update(
            instructions="---\nname: framework-research\ndescription: 合成网页验证\n---\n# 合成网页验证\n仅使用已注册网页搜索工具。",
            files=[],
            reviewed_scripts=[],
        )
        created = service.capabilities._create(candidate, source="manual", cid="framework-research")
        service.capabilities.publish(created["id"])
        service.capabilities.edit(created["id"], candidate)
        published = service.capabilities.publish(created["id"])
        native.skill_names = [service.capabilities.selection(created["id"])["native_name"]]
        assert published["version"] == 2
        assert service.capability_readiness(created["id"])["admitted"] is True
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def test_catalog_and_framework_data_use_versioned_specific_contracts(framework_api):
    client, _, _ = framework_api
    catalog = client.get("/api/research/frameworks")
    assert catalog.status_code == 200
    assert [item["slug"] for item in catalog.json()["items"]] == [
        "gold",
        "dollar",
        "ai-economy",
        "bond-framework",
        "elnino",
        "fund-track-selection",
        "memory-chips-60",
        "inference-chips-42",
        "model-hardware-chain",
        "gold-cycle",
        "ainvest",
    ]

    response = client.get("/api/research/frameworks/gold/data")
    assert response.status_code == 200
    payload = response.json()
    assert payload["framework"]["version"] == "2.0.0"
    assert payload["framework"]["source_revision"] == ("758ae3848dc32adf2b361fdd070f98cbc75ce496")
    assert payload["snapshot"]["schema_version"] == 2
    assert payload["snapshot"]["status"] == "待核验"
    assert payload["snapshot"]["options"]["sources"][0]["proxy"] is True
    assert "funds" not in payload["snapshot"]

    dollar = client.get("/api/research/frameworks/dollar/data")
    assert dollar.status_code == 200
    dollar_payload = dollar.json()
    assert dollar_payload["framework"]["version"] == "1.0.0"
    assert dollar_payload["framework"]["source_revision"] == (
        "2c210b45577905c0e8ec5f9c061e7069a6cb3b96"
    )
    assert dollar_payload["snapshot"]["schema_version"] == 1
    assert dollar_payload["snapshot"]["quantity_q"]["key"] == "Q"
    assert dollar_payload["snapshot"]["cross_border_x"]["key"] == "X"
    assert dollar_payload["snapshot"]["status"] == "待核验"


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


@pytest.mark.parametrize("framework_api", ["declared_web_only"], indirect=True)
def test_framework_explain_and_explicit_verify_use_separate_dsh_presets(framework_api):
    client, native, service = framework_api
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
    selection = service.capabilities.selection("framework-research")
    assert selection["version"] == 2
    assert prompts[-1].startswith(f"/{selection['native_name']} ")
    assert "深度验证" in prompts[-1]
    for prompt in prompts:
        context, _ = json.JSONDecoder().raw_decode(prompt[prompt.index('{"binding":') :])
        assert context["binding"]["snapshot_revision"] == revision
        assert context["allocation"]["availability"] == "not_connected"
        assert "correlations" not in context["allocation"]
        assert "scenarios" not in context["allocation"]


def test_builtin_framework_verify_missing_data_contract_fails_closed(framework_api):
    client, native, service = framework_api
    readiness = service.capability_readiness("framework-research")
    assert readiness["admitted"] is False
    assert {item["code"] for item in readiness["missing"]} == {"data_contract_missing"}
    revision = client.get("/api/research/frameworks/gold/data").json()["snapshot"]["revision"]
    created = client.post(
        "/api/research/frameworks/gold/sessions", json={"snapshot_revision": revision}
    ).json()
    sid = created["session"]["id"]
    native.calls.clear()
    verified = client.post(
        f"/api/research/frameworks/gold/sessions/{sid}/verify",
        headers={"Idempotency-Key": "builtin-framework-no-contract"},
        json={"question": "核验央行购金数据", "expected_snapshot_revision": revision},
    )
    assert verified.status_code == 409, verified.text
    assert verified.json()["error"]["code"] == "capability_data_unavailable"
    assert not any(method == "session.prompt" for method, _ in native.calls)
    assert service.capabilities.row("framework-research")["version"] == 1


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

    assert store.read().schema_version == 2
    assert json.loads((root / "snapshot.legacy-v0.json").read_text(encoding="utf-8")) == legacy


def test_gold_snapshot_store_backs_up_v1_before_migrating_to_v2(tmp_path):
    root = tmp_path / "gold"
    root.mkdir()
    legacy = build_seed().model_dump(mode="json")
    legacy["schema_version"] = 1
    (root / "snapshot.json").write_text(json.dumps(legacy), encoding="utf-8")

    store = GoldSnapshotStore(root)

    assert store.read().schema_version == 2
    assert json.loads((root / "snapshot.legacy-v1.json").read_text(encoding="utf-8")) == legacy


def test_dollar_store_is_strict_and_blocks_unverified_published_state(tmp_path):
    store = DollarSnapshotStore(tmp_path / "dollar")
    assert store.read().revision == build_dollar_seed().revision
    invalid = store.read().model_dump(mode="json")
    invalid["status"] = "偏松"
    invalid["research_state"]["label"] = "偏松"

    with pytest.raises(ValidationError, match="requires 待核验"):
        DollarSnapshot.model_validate(invalid)


def test_framework_session_cannot_cross_framework_boundary(framework_api):
    client, _, _ = framework_api
    gold_revision = client.get("/api/research/frameworks/gold/data").json()["snapshot"]["revision"]
    dollar_revision = client.get("/api/research/frameworks/dollar/data").json()["snapshot"][
        "revision"
    ]
    sid = client.post(
        "/api/research/frameworks/gold/sessions",
        json={"snapshot_revision": gold_revision},
    ).json()["session"]["id"]

    response = client.post(
        f"/api/research/frameworks/dollar/sessions/{sid}/messages",
        headers={"Idempotency-Key": "framework-cross-boundary"},
        json={"text": "解释Q维度", "expected_snapshot_revision": dollar_revision},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "framework_session_mismatch"


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


def test_static_embeds_are_dated_and_cannot_create_bot(framework_api):
    client, native, _ = framework_api
    payload = client.get("/api/research/frameworks/ainvest/data").json()
    assert payload["framework"]["display"] == {
        "kind": "static-embed",
        "url": "/frameworks-embed/ainvest/",
        "imported_at": "2026-10-14",
        "bot_enabled": False,
    }
    assert payload["snapshot"]["coverage"] == 0
    assert payload["snapshot"]["as_of"] == "2026-10-14"
    before = len(native.calls)
    response = client.post(
        "/api/research/frameworks/ainvest/sessions",
        json={"snapshot_revision": payload["snapshot"]["revision"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "framework_bot_unavailable"
    assert len(native.calls) == before


def test_native_display_retains_snapshot_and_collector_identity(framework_api):
    client, _, service = framework_api
    for slug, model in (("gold", GoldSnapshotStore), ("dollar", DollarSnapshotStore)):
        runtime = service.frameworks.registry.get(slug)
        assert isinstance(runtime.store, model)
        before = runtime.snapshot().model_dump(mode="json")
        payload = client.get(f"/api/research/frameworks/{slug}/data").json()
        assert payload["snapshot"] == before
        assert payload["framework"]["display"]["kind"] == "native-embed"
        assert payload["framework"]["display"]["bot_enabled"] is True
    assert service.frameworks.scheduler.gold.store is service.frameworks.registry.get("gold").store
    assert (
        service.frameworks.scheduler.dollar.store is service.frameworks.registry.get("dollar").store
    )


def test_embed_resources_are_same_origin_and_host_csp_is_unchanged(framework_api):
    client, _, _ = framework_api
    for slug in (
        "gold",
        "dollar",
        "ainvest",
        "elnino",
        "ai-economy",
        "bond-framework",
        "fund-track-selection",
        "gold-cycle",
        "inference-chips-42",
        "memory-chips-60",
        "model-hardware-chain",
    ):
        response = client.get(f"/frameworks-embed/{slug}/")
        assert response.status_code == 200
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
        assert "https://" not in response.headers["content-security-policy"]
    host_csp = client.get("/").headers["content-security-policy"]
    assert "frame-ancestors 'none'" in host_csp
    assert "script-src 'self';" in host_csp


def test_framework_verify_retains_real_data_admission_gate(framework_api):
    client, native, _ = framework_api
    revision = client.get("/api/research/frameworks/gold/data").json()["snapshot"]["revision"]
    sid = client.post(
        "/api/research/frameworks/gold/sessions", json={"snapshot_revision": revision}
    ).json()["session"]["id"]
    before = len([call for call in native.calls if call[0] == "session.prompt"])
    response = client.post(
        f"/api/research/frameworks/gold/sessions/{sid}/verify",
        headers={"Idempotency-Key": "framework-unavailable-1"},
        json={"expected_snapshot_revision": revision, "question": "核验数据缺口"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "capability_data_unavailable"
    assert len([call for call in native.calls if call[0] == "session.prompt"]) == before


def test_gold_context_excludes_unconnected_allocation_without_mutating_snapshot():
    from app.research_web.frameworks.goldar.context import build_context

    snapshot = build_seed()
    before = snapshot.model_dump(mode="json")
    context = build_context(snapshot)
    assert context["allocation"]["availability"] == "not_connected"
    assert "correlations" not in context["allocation"]
    assert "scenarios" not in context["allocation"]
    assert snapshot.model_dump(mode="json") == before
    assert context["state"] == before["research_state"]


@pytest.mark.parametrize("status", ["complete", "partial", "proxy", "stale"])
def test_gold_context_preserves_sourced_last_good_allocation(status):
    from app.research_web.frameworks.base import SourceRecord
    from app.research_web.frameworks.goldar.context import build_context

    snapshot = build_seed()
    snapshot.allocation_context.status = status
    snapshot.allocation_context.sources = [
        SourceRecord(
            name="Audited study",
            url="https://research.example.org/study",
            observed_at="2026-10-01",
            unit="monthly total return",
            method="2016-2026 monthly observations; documented computation",
        )
    ]
    assert build_context(snapshot)["allocation"] == snapshot.allocation_context.model_dump(
        mode="json"
    )


@pytest.mark.parametrize("source_kind", ["none", "invalid", "fixture"])
def test_gold_context_rejects_allocation_without_real_provenance(source_kind):
    from app.research_web.frameworks.goldar.context import build_context

    snapshot = build_seed()
    snapshot.allocation_context.status = "complete"
    if source_kind == "none":
        snapshot.allocation_context.sources = []
    elif source_kind == "invalid":
        snapshot.allocation_context.sources[0].method = "documented observations"
    elif source_kind == "fixture":
        snapshot.allocation_context.sources[0].url = "https://research.example.org/study"
    assert "correlations" not in build_context(snapshot)["allocation"]
