"""AlphaDesk admission and event replay through the existing Research Web API."""

import sys
import time

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web import qa_execution, qa_model
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store

BASE = "/api/research/sessions"


def test_qa_uses_owned_worker_and_replays_same_submission(tmp_path, monkeypatch):
    store = Store(tmp_path / "data")
    native = NativeFixture()
    seen = []

    async def connection(_service, _row):
        return ("test", "test", None, "test")

    async def worker(request, _callbacks, emit):
        seen.append(request)
        await emit("_qa", {"content": "草稿"})
        await emit("update", {"id": "_qa_retract"})
        await emit("_qa", {"content": "实际回答"})

    monkeypatch.setattr(qa_model, "connection", connection)
    monkeypatch.setattr(qa_execution, "run_worker", worker)
    service = ResearchService(native, store)
    with TestClient(create_app(service)) as client:
        legacy = client.post(BASE, json={"mode": "fingpt"}).json()["id"]
        specialist = client.post(
            BASE, json={"mode": "fingpt", "research_mode": "specialist"}
        ).json()["id"]
        monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
        assert client.get(f"{BASE}/{legacy}").status_code == 410
        assert client.get(f"{BASE}/{legacy}/files").status_code == 410
        assert client.get(f"{BASE}/{specialist}").status_code == 200
        session = client.post(BASE, json={"mode": "fingpt", "research_mode": "quick"})
        assert session.status_code == 201, session.text
        assert session.json()["execution_engine"] == "alphadesk"
        sid = session.json()["id"]
        body = {"text": "查询一", "expected_formats": []}
        headers = {"Idempotency-Key": "question-1"}
        sent = client.post(f"{BASE}/{sid}/messages", json=body, headers=headers)
        assert sent.status_code == 202, sent.text
        replay = client.post(f"{BASE}/{sid}/messages", json=body, headers=headers)
        assert replay.status_code == 202, replay.text
        for _ in range(50):
            detail = client.get(f"{BASE}/{sid}").json()
            if detail["status"] != "running":
                break
            time.sleep(0.01)
        assert detail["status"] == "completed", detail
        assert detail["messages"][-1]["text"] == "实际回答"
        assert detail["qa_events"][-1]["event"] == "task_end"
        assert len(seen) == 1
        assert legacy not in {row["id"] for row in client.get(BASE).json()["items"]}
    assert qa_execution.QuestionExecution(service).ledger(sid)["status"] == "completed"


@pytest.mark.asyncio
async def test_restart_exposes_interrupted_without_rerunning(tmp_path, monkeypatch):
    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    store = Store(tmp_path / "data")
    service = ResearchService(NativeFixture(), store)
    row = store.create("fingpt", "中断测试")
    qa_execution.bind(service, row, service.default_model)
    row["status"] = "running"
    store.save()
    service.qa.persist(
        row["id"], {"key": "original-key", "status": "running", "events": [], "messages": []}
    )
    recovered = ResearchService(NativeFixture(), Store(store.root))
    assert recovered.qa.status(row["id"]) == "interrupted"
    assert not recovered.qa.tasks


@pytest.mark.asyncio
async def test_worker_delivers_delta_before_model_finishes():
    import asyncio

    from app.research_web.qa_bridge import run_worker

    first_token = asyncio.Event()

    async def model(_params, emit):
        await emit("实时流式测试首段")
        await asyncio.wait_for(first_token.wait(), timeout=5)
        await emit("答案")
        return {"content": "实时流式测试首段答案", "toolCalls": []}

    async def tool(_params, _emit):
        pytest.fail("no tool is declared")

    async def event(name, payload):
        if name == "_qa" and payload["content"].startswith("实时"):
            first_token.set()

    await run_worker(
        {"mode": "quick", "question": "测试", "tools": []},
        {"model": model, "tool": tool},
        event,
    )


def test_owned_snapshot_observation_preserves_period_unit_and_bytes():
    from app.research_web.datahub.security import json_bytes
    from app.research_web.qa_observations import snapshot_observations

    metadata = {
        "dataset_id": "c7f73585-8ae0-4363-93e0-c76a3a679706",
        "manifest_sha256": "b" * 64,
        "status": "complete",
        "fields": {"close": {"unit": "元"}, "unknown_unit": {}},
    }
    rows = [{"date": "2026-11-10", "close": 12.5, "unknown_unit": 19}]
    raw = json_bytes(rows).decode()
    observed = snapshot_observations(metadata, rows, raw, "tenant:session:turn")
    assert len(observed) == 1
    item = observed[0]
    assert (item["metric"], item["period"], item["value"], item["unit"]) == (
        "close",
        "2026-11-10",
        "12.5",
        "元",
    )
    proof = item["proofs"][0]
    span = proof["spans"][0]
    assert proof["sha256"] == metadata["manifest_sha256"]
    assert raw[span["start"] : span["end"]] == '"close": 12.5'
    assert snapshot_observations(metadata, rows, raw.replace("12.5", "12.6"), "same") == []
    declined = {**metadata, "provider_metadata": {"quality_accepted": False}}
    assert snapshot_observations(declined, rows, raw, "same") == []


def test_acceptance_budget_reserves_before_model_dispatch(tmp_path, monkeypatch):
    import json

    from app.research_web.qa_acceptance import reserve
    from app.research_web.store import StoreError

    root = tmp_path / "budget"
    root.mkdir(mode=0o700)
    ledger = root / "ledger.json"
    ledger.write_text('{"version":1,"reserved_micro_cny":0,"calls":0}')
    ledger.chmod(0o600)
    monkeypatch.setenv("RWB_QA_ACCEPTANCE_ROOT", str(root))
    connection = (
        "https://api.deepseek.com/chat/completions",
        "deepseek-flash",
        None,
        "deepseek-official",
    )
    for _ in range(24):
        reserve(connection, 8192)
    value = json.loads(ledger.read_text())
    assert value["calls"] == 24
    assert value["reserved_micro_cny"] == 49_572_864
    with pytest.raises(StoreError, match="费用上限"):
        reserve(connection, 8192)
    assert json.loads(ledger.read_text()) == value
    with pytest.raises(StoreError, match="费用无法核算"):
        reserve((*connection[:3], "openai-compatible"), 8192)


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
@pytest.mark.parametrize("with_snapshot", [False, True])
def test_qa_worker_report_uses_bound_native_delivery(tmp_path, monkeypatch, with_snapshot):
    async def connection(_service, _row):
        return ("test", "test", None, "test")

    async def worker(request, callbacks, emit):
        assert request["mode"] == "deep"
        if with_snapshot:
            fetched = await callbacks["tool"](
                {
                    "name": "read_frozen_dataset",
                    "arguments": {"dataset_id": snapshot["dataset_id"]},
                },
                None,
            )
            assert fetched["data"]["items"][0]["close"] == 12.5
        index = await callbacks["tool"](
            {"name": "list_research_observations", "arguments": {}}, None
        )
        requirements = index["data"]["requirements"]
        observations = index["data"]["observations"]
        plan = {
            "title": "证据不足报告",
            "sections": [
                {
                    "id": "missing",
                    "heading": "收盘价" if with_snapshot else "资料缺口",
                    "evidence_ids": [observations[0]["id"]] if with_snapshot else [],
                    "requirement_ids": [item["id"] for item in requirements],
                    **({} if with_snapshot else {"analysis": "暂时缺少可独立核验的资料。"}),
                }
            ],
            "missing": [] if with_snapshot else ["证据未取得"],
        }
        result = await callbacks["tool"](
            {"name": "write_research_report", "arguments": {"plan": plan}}, None
        )
        assert result["data"]["status"] == "generated", result
        await emit("_qa", {"content": "已输出带来源的报告。"})

    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    monkeypatch.setattr(qa_model, "connection", connection)
    monkeypatch.setattr(qa_execution, "run_worker", worker)
    service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
    with TestClient(create_app(service)) as client:
        sid = client.post(
            BASE,
            json={
                "research_mode": "deep",
                "source_scope": ["datahub"] if with_snapshot else ["uploads"],
            },
        ).json()["id"]
        if with_snapshot:
            from app.research_web.datahub.contracts import BusinessQuery
            from app.research_web.datahub.providers import Result

            query = BusinessQuery(capability="market_bars")
            snapshot = service.datahub.snapshots.publish(
                sid,
                query,
                Result(
                    rows=[{"date": "2026-11-10", "close": 12.5}],
                    status="complete",
                    fields={"close": {"unit": "元"}},
                    as_of="2026-11-10",
                    provider_id="eastmoney",
                ),
            )
        submitted = client.post(
            f"{BASE}/{sid}/messages",
            json={
                "text": "核对收盘价。" if with_snapshot else "核对给定材料的事实。",
                "expected_formats": ["md"],
            },
            headers={"Idempotency-Key": "report-0001"},
        )
        assert submitted.status_code == 202, submitted.text
        for _ in range(150):
            detail = client.get(f"{BASE}/{sid}").json()
            if detail["status"] != "running":
                break
            time.sleep(0.04)
        assert detail["status"] == "completed", detail
        assert detail["research_quality"]["status"] == (
            "passed" if with_snapshot else "incomplete"
        ), detail["research_quality"]["issues"]
        assert detail["research_report_delivery"]["status"] == "bound", detail[
            "research_report_delivery"
        ]
        file = next(item for item in detail["files"] if item["name"] == "report.md")
        download = client.get(f"{BASE}/{sid}/files/{file['id']}/download")
        assert download.status_code == 200
        assert ("12.5" if with_snapshot else "资料缺口") in download.text
        if with_snapshot:
            from test_discovery_tracking import setup as tracking_fixture

            tracking, _, _ = tracking_fixture(tmp_path / "tracking")
            tracking.research = service
            tracking.store = service.store
            key = service.store.session(sid)["delivery_key"]
            service.store.data.setdefault("discovery_handoffs", {})["qa-report-test"] = {
                "session_id": sid,
                "delivery_key": key,
            }
            run = {
                "session_id": sid,
                "discovery_handoff_id": "qa-report-test",
                "discovery_fingerprint": "acquired-snapshot",
            }
            track = {}
            client.portal.call(tracking._monitor, run, track)
            assert run["discovery_accepted"] is True
            assert run["discovery_notification"] == "meaningful_change"
            assert track["last_accepted_fingerprint"] == "acquired-snapshot"
