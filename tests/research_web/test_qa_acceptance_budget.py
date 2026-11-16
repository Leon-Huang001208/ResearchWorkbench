"""Exercise acceptance accounting through the actual model and source boundaries."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.research_web import intel_routes, qa_model, research_web_sources
from app.research_web.datahub import DataHub
from app.research_web.datahub.contracts import Query
from app.research_web.datahub.providers import Result
from app.research_web.multiuser.runtime import RuntimeConfig, RuntimePool
from app.research_web.store import Store, StoreError

CONNECTION = (
    "https://api.deepseek.com/chat/completions",
    "deepseek-flash",
    None,
    "deepseek-official",
)
PARAMS = {"messages": [{"role": "user", "content": "Fixture question"}], "maxTokens": 8192}
USAGE = {
    "prompt_tokens": 1_010,
    "prompt_cache_hit_tokens": 1_000,
    "prompt_cache_miss_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 1_030,
}


def acceptance_ledger(tmp_path, monkeypatch, *, calls=0, reserved=0):
    tmp_path.chmod(0o700)
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"version": 1, "calls": calls, "reserved_micro_cny": reserved}))
    ledger.chmod(0o600)
    monkeypatch.setenv("RWB_QA_ACCEPTANCE_ROOT", str(tmp_path))
    return ledger


def completion(ident, *, usage=USAGE, done=True):
    chunk = {
        "id": ident,
        "model": "deepseek-flash",
        "choices": [{"finish_reason": "stop", "delta": {"content": "Fixture answer"}}],
    }
    lines = ["data: " + json.dumps(chunk)]
    if usage is not None:
        lines.append("data: " + json.dumps({**chunk, "choices": [], "usage": usage}))
    if done:
        lines.append("data: [DONE]")
    return httpx.Response(200, text="\n\n".join(lines) + "\n\n")


async def ignore_delta(_delta):
    pass


@pytest.mark.asyncio
async def test_official_usage_releases_unused_hold_without_erasing_old_reservations(
    tmp_path, monkeypatch
):
    ledger = acceptance_ledger(tmp_path, monkeypatch, calls=1, reserved=2_065_536)
    seen = []

    def transport(request):
        assert json.loads(request.content)["stream_options"] == {"include_usage": True}
        seen.append(json.loads(ledger.read_text()))
        return completion("official-1")

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await qa_model.stream_model(client, CONNECTION, PARAMS, ignore_delta)

    assert result["content"] == "Fixture answer"
    assert seen[0]["legacy"] == {"version": 1, "calls": 1, "reserved_micro_cny": 2_065_536}
    assert seen[0]["reserved_micro_cny"] == 4_131_072
    assert next(iter(seen[0]["requests"].values()))["usage"] is None
    state = json.loads(ledger.read_text())
    assert state["calls"] == 2
    assert state["reserved_micro_cny"] == 2_065_756
    assert next(iter(state["requests"].values()))["usage"] == {
        "completion_id": "official-1",
        "prompt_cache_hit_tokens": 1_000,
        "prompt_cache_miss_tokens": 10,
        "completion_tokens": 20,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("usage", "done"),
    [(None, True), (USAGE, False), ({**USAGE, "total_tokens": 1}, True)],
)
async def test_unproven_usage_keeps_full_hold(tmp_path, monkeypatch, usage, done):
    ledger = acceptance_ledger(tmp_path, monkeypatch)
    transport = httpx.MockTransport(lambda _: completion("unverified", usage=usage, done=done))
    async with httpx.AsyncClient(transport=transport) as client:
        await qa_model.stream_model(client, CONNECTION, PARAMS, ignore_delta)
    state = json.loads(ledger.read_text())
    assert state["reserved_micro_cny"] == 2_065_536
    assert next(iter(state["requests"].values()))["usage"] is None


@pytest.mark.asyncio
async def test_repeated_completion_id_cannot_release_another_hold(tmp_path, monkeypatch):
    ledger = acceptance_ledger(tmp_path, monkeypatch)
    transport = httpx.MockTransport(lambda _: completion("same-provider-id"))
    async with httpx.AsyncClient(transport=transport) as client:
        await qa_model.stream_model(client, CONNECTION, PARAMS, ignore_delta)
        await qa_model.stream_model(client, CONNECTION, PARAMS, ignore_delta)
    state = json.loads(ledger.read_text())
    assert state["reserved_micro_cny"] == 2_065_756
    assert sum(record["usage"] is not None for record in state["requests"].values()) == 1


@pytest.mark.asyncio
async def test_existing_acceptance_reservations_prevent_further_dispatch(tmp_path, monkeypatch):
    ledger = acceptance_ledger(tmp_path, monkeypatch, calls=24, reserved=48_796_000)
    old = ledger.read_bytes()

    def forbidden(_request):
        pytest.fail("unfunded model request reached the transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        with pytest.raises(StoreError) as blocked:
            await qa_model.stream_model(client, CONNECTION, PARAMS, ignore_delta)
    assert blocked.value.code == "qa_acceptance_budget_exhausted"
    assert ledger.read_bytes() == old


@pytest.mark.asyncio
async def test_unpriced_external_sources_are_blocked_before_io(tmp_path, monkeypatch):
    acceptance_ledger(tmp_path, monkeypatch)

    def forbidden(*_args, **_kwargs):
        pytest.fail("unpriced source reached the network boundary")

    monkeypatch.setattr(intel_routes.httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(research_web_sources.asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(HTTPException) as intel:
        await intel_routes.read_upstream("/radar")
    assert intel.value.detail["code"] == "qa_acceptance_source_price_unknown"
    with pytest.raises(StoreError) as web:
        await research_web_sources.fetch_owned_document("https://example.com/research")
    assert web.value.code == "qa_acceptance_source_price_unknown"


@pytest.mark.asyncio
async def test_datahub_replays_owned_snapshot_but_refuses_new_provider_calls(tmp_path, monkeypatch):
    acceptance_ledger(tmp_path, monkeypatch)
    store = Store(tmp_path / "data")
    session = store.create("fingpt", "Frozen evidence")
    hub = DataHub(store)
    query = Query(source="fund_nav", code="000001")
    snapshot = hub.snapshots.publish(
        session["id"],
        query,
        Result(rows=[{"date": "2026-11-10", "nav": 12.5}], status="complete"),
    )
    hub.snapshots.receipt(
        session["id"],
        "owned",
        {
            "status": "completed",
            "fingerprint": query.fingerprint(include_refresh=True),
            "dataset_id": snapshot["dataset_id"],
            "cache_hit": False,
        },
    )

    async def forbidden(*_args, **_kwargs):
        pytest.fail("unpriced DataHub query started")

    monkeypatch.setattr(hub, "_query", forbidden)
    assert (await hub.query(session["id"], "owned", query))["dataset_id"] == snapshot["dataset_id"]
    with pytest.raises(StoreError) as blocked:
        await hub.query(session["id"], "unpriced", query)
    assert blocked.value.code == "qa_acceptance_source_price_unknown"
    assert hub.snapshots.receipt(session["id"], "unpriced") is None


@pytest.mark.asyncio
async def test_private_runtime_passes_shared_budget_path(tmp_path, monkeypatch):
    acceptance_ledger(tmp_path, monkeypatch)
    pool = RuntimePool(
        RuntimeConfig(
            root=tmp_path / "pool",
            project=Path(__file__).resolve().parents[2],
            source=None,
            python="/usr/bin/python3",
            node=None,
            service_only=True,
            alphadesk_qa=True,
        )
    )
    try:
        env = pool._environment(tmp_path / "tenant", tmp_path / "state", 18088, None)
        assert env["RWB_QA_ACCEPTANCE_ROOT"] == str(tmp_path)
    finally:
        await pool.close()
