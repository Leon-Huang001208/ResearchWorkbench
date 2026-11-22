"""AlphaDesk admission and event replay through the existing Research Web API."""

import json
import sys
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web import qa_execution, qa_model, qa_tools
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store

BASE = "/api/research/sessions"


def test_qa_report_schema_accepts_sdk_plan_and_rejects_scalar_array_fields():
    from jsonschema import Draft202012Validator
    from test_bound_analysis import bound_plan

    from app.research_web.resources.research_report_plan import build_business_report_plan

    store = SimpleNamespace(session=lambda _sid: {"source_scope": ["uploads"]})
    tools = qa_tools.TurnTools(
        SimpleNamespace(store=store),
        "schema-proof",
        {"research_contract": {"requirements": []}, "delivery": {"required_formats": ["md"]}},
        [],
    )
    schema = next(
        tool["function"]["parameters"]
        for tool in tools.schemas()
        if tool["function"]["name"] == "write_research_report"
    )
    context, plan, bundle = bound_plan()
    plan["summary"] = [
        {
            "metric": "current_gdp",
            "observation_id": "gdp_current_price_preliminary@2025",
            "decimal_places": 0,
        }
    ]
    plan["controls"] = []
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    validator.validate({"plan": plan})
    assert build_business_report_plan(context, plan, bundle)["metrics"]["current_gdp"] > 0
    for field in ("sections", "missing", "summary"):
        invalid = {**plan, field: "误填的摘要文字"}
        errors = list(validator.iter_errors({"plan": invalid}))
        assert any(list(error.path) == ["plan", field] for error in errors), field


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
@pytest.mark.asyncio
async def test_qa_report_wrong_summary_type_then_valid_source_plan(tmp_path):
    from app.research_web.delivery import Delivery
    from app.research_web.research_quality import make_contract

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "Report tool schema proof")["id"]
    store.session(sid).update(source_scope=["uploads"], delivery_key="schema-proof")
    raw = (
        "Publisher: Federal Reserve Board\n"
        "Title: Minutes of the Federal Open Market Committee, October 27-28, 2026\n"
        "Published (UTC): 2026-11-18\n"
        "Original: https://www.federalreserve.gov/newsevents/pressreleases/monetary20261118a.htm\n"
        "Official RSS description: Minutes of the Federal Open Market Committee, October 27-28, 2026\n"
        "RSS SHA-256: 37dd749fb9a477a979204d94a5aa7fd6720d71e514e2fbfd03edd26bccb52680\n"
    )
    (store.directory(sid) / "inputs/fed-feed-entry.txt").write_text(raw)
    attachment = next(item for item in store.files(sid) if item["kind"] == "inputs")
    contract = make_contract("a" * 24, "核对官方摘要", ["公告来源与摘要"], "2026-11-19", "deep")
    receipt = {
        "research_contract": contract,
        "delivery": {"task_id": contract["task_id"], "required_formats": ["md"]},
    }
    store.data["receipts"][sid + ":schema-proof"] = receipt
    store.save()
    tools = qa_tools.TurnTools(
        SimpleNamespace(store=store, delivery=Delivery(store)), sid, receipt, [attachment["id"]]
    )
    plan = {
        "title": "美联储官方公告摘要跟踪",
        "sections": [
            {
                "id": "summary",
                "heading": "公告来源与摘要",
                "evidence_ids": [],
                "source_ids": ["file:" + attachment["id"]],
                "requirement_ids": ["r1"],
            }
        ],
        "missing": [],
    }
    rejected = await tools.call(
        {"name": "write_research_report", "arguments": {"plan": {**plan, "summary": "摘要"}}},
        None,
    )
    assert rejected["data"] == {"status": "unavailable", "code": "qa_report_plan_failed"}
    assert not tools.report_written
    assert not (store.directory(sid) / "outputs/report.md").exists()
    result = await tools.call({"name": "write_research_report", "arguments": {"plan": plan}}, None)
    assert result["data"]["status"] == "generated", result
    markdown = (store.directory(sid) / "outputs/report.md").read_text()
    assert "2026-11-18" in markdown and "monetary20261118a.htm" in markdown
    assert "官方 RSS 摘要：Minutes of the Federal Open Market Committee" in markdown
    assert tools.report_written and tools.calls == 2


@pytest.mark.asyncio
async def test_qa_source_pages_round_trip_below_worker_limit(monkeypatch):
    identifier = "dossier:" + "1" * 32 + ":" + "2" * 32 + ":1"
    content = ("统计公报😀\n" + "\0" * 4500) * 8
    source = {"id": "web:original", "title": "统计公报", "sha256": "f" * 64}
    store = SimpleNamespace(
        session=lambda _sid: {"source_scope": ["uploads"]},
        save=lambda: None,
    )
    tools = qa_tools.TurnTools(SimpleNamespace(store=store), "test", {}, [])

    async def execute(_service, _sid, _call, operation, bound_id, *, full):
        assert (operation, bound_id, full) == ("read", identifier, True)
        return {"content": content, "source": source}

    monkeypatch.setattr(qa_tools, "execute_source", execute)
    offset, pages = 0, []
    while offset is not None:
        page = (await tools.read(identifier, "call", offset=offset))["data"]
        assert page["offset"] == offset
        assert page["source"]["sha256"] == source["sha256"]
        assert len(json.dumps(page, ensure_ascii=False).encode("utf-16-le")) // 2 < 24000
        pages.append(page["content"])
        offset = page["next_offset"]
    assert len(pages) > 1
    assert "".join(pages) == content


@pytest.fixture(autouse=True)
def isolate_qa_runtime(monkeypatch):
    monkeypatch.delenv("RWB_ALPHADESK_QA", raising=False)
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")


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


def test_snapshot_observations_bind_repeated_values_to_their_own_rows():
    from app.research_web.datahub.security import json_bytes
    from app.research_web.qa_observations import snapshot_observations
    from app.research_web.resources.research_report_plan import _fact_text

    metadata = {
        "dataset_id": "c7f73585-8ae0-4363-93e0-c76a3a679706",
        "manifest_sha256": "b" * 64,
        "status": "complete",
        "fields": {"close": {"unit": "currency_per_share", "currency": "CNY"}},
    }
    rows = [{"date": date, "close": 12.5} for date in ("2026-11-09", "2026-11-10")]
    raw = json_bytes(rows).decode()
    first, second = snapshot_observations(metadata, rows, raw, "scope")
    assert [first["unit"], second["unit"]] == ["CNY/股", "CNY/股"]
    assert [first["period"], second["period"]] == ["2026-11-09", "2026-11-10"]
    assert first["proofs"][0]["spans"][0]["start"] < second["proofs"][0]["spans"][0]["start"]
    assert _fact_text(second) == "2026-11-10 收盘价为12.5 CNY/股"


def test_discovery_observation_quotes_the_selected_event_with_repeated_title():
    from app.research_web.datahub.security import json_bytes
    from app.research_web.qa_observations import snapshot_observations
    from app.research_web.resources.research_report_plan import _fact_text

    title = "市场供应预期出现变化"
    rows = [{"detail": {"articles": [{"title": title}], "event": {"title": title}}}]
    raw = json_bytes(rows).decode()
    metadata = {
        "dataset_id": "c7f73585-8ae0-4363-93e0-c76a3a679706",
        "manifest_sha256": "b" * 64,
        "snapshot_kind": "discovery_evidence",
        "as_of": "2026-11-10T12:00:00+08:00",
    }
    (quote,) = snapshot_observations(metadata, rows, raw, "scope")
    assert quote["proofs"][0]["spans"][0]["start"] == raw.rindex('"' + title + '"')
    assert title in _fact_text(quote)


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
