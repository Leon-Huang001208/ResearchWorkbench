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

    store = SimpleNamespace(
        session=lambda _sid: {
            "source_scope": ["uploads", "datahub"],
            "purpose": "discovery_research",
        }
    )
    tools = qa_tools.TurnTools(
        SimpleNamespace(store=store, discovery=SimpleNamespace(trusted_context=lambda _sid: None)),
        "schema-proof",
        {"research_contract": {"requirements": []}, "delivery": {"required_formats": ["md"]}},
        [],
    )
    schema = next(
        tool["function"]["parameters"]
        for tool in tools.schemas()
        if tool["function"]["name"] == "write_research_report"
    )
    for tool in tools.schemas():
        if tool["function"]["name"] in {"read_frozen_dataset", "read_frozen_discovery"}:
            assert tool["function"]["parameters"]["properties"]["offset"] == {
                "type": "integer",
                "minimum": 0,
            }
    assert (
        "analysis" in schema["properties"]["plan"]["properties"]["sections"]["items"]["properties"]
    )
    assert {"summary", "calculations", "controls"} <= set(
        schema["properties"]["plan"]["properties"]
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


def test_qa_registered_feed_schema_exposes_metadata_plan_only():
    store = SimpleNamespace(
        session=lambda _sid: {
            "source_scope": ["uploads", "datahub"],
            "purpose": "discovery_research",
        }
    )
    discovery = SimpleNamespace(
        trusted_context=lambda _sid: {
            "source_kind": "registered_feed",
            "registered_feed_sources": {
                "notice-a": {"id": "file:notice-a"},
                "notice-b": {"id": "file:notice-b"},
            },
        }
    )
    tools = qa_tools.TurnTools(
        SimpleNamespace(store=store, discovery=discovery),
        "metadata-schema-proof",
        {"research_contract": {"requirements": []}, "delivery": {"required_formats": ["md"]}},
        [],
    )
    tool = next(
        tool["function"]
        for tool in tools.schemas()
        if tool["function"]["name"] == "write_research_report"
    )
    schema = tool["parameters"]["properties"]["plan"]
    assert set(schema["properties"]) == {"title", "sections", "missing"}
    section = schema["properties"]["sections"]["items"]
    assert set(section["properties"]) == {
        "id",
        "heading",
        "source_ids",
        "requirement_ids",
        "evidence_ids",
    }
    assert set(section["required"]) == set(section["properties"])
    assert section["properties"]["evidence_ids"]["maxItems"] == 0
    assert section["properties"]["source_ids"]["minItems"] == 1
    assert set(section["properties"]["source_ids"]["items"]["enum"]) == {
        "file:notice-a",
        "file:notice-b",
    }
    assert "聊天分析不进入正式摘要清单" in tool["description"]


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
@pytest.mark.asyncio
async def test_registered_feed_metadata_report_rejects_unavailable_fields_then_writes_native(
    tmp_path,
    monkeypatch,
):
    from uuid import uuid4

    from jsonschema import Draft202012Validator
    from test_discovery import Research

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result
    from app.research_web.delivery import Delivery
    from app.research_web.discovery import DiscoveryService, Prepare
    from app.research_web.research_quality import make_contract

    research = Research(tmp_path / "registered-report")
    research.discovery = DiscoveryService(research)
    research.delivery = Delivery(research.store)
    origin_sid = research.store.create("fingpt", "原始 Fed 快照")["id"]
    query = BusinessQuery(
        capability="external_data", source="ext_fed", parameters={"dataset": "news"}
    )
    raw = (
        b"<rss><channel><item><guid>report-item</guid><title>Board release</title>"
        b"<link>https://www.federalreserve.gov/newsevents/pressreleases/other20261120a.htm</link>"
        b"<pubDate>Fri, 20 Nov 2026 12:00:00 GMT</pubDate>"
        b"<description>Official RSS summary.</description></item>"
        b"<item><guid>report-followup</guid><title>Board followup</title>"
        b"<link>https://www.federalreserve.gov/newsevents/pressreleases/other20261121a.htm</link>"
        b"<pubDate>Sat, 21 Nov 2026 12:00:00 GMT</pubDate>"
        b"<description>Official followup summary.</description></item></channel></rss>"
    )
    snapshot = research.datahub.snapshots.publish(
        origin_sid,
        query,
        Result(
            rows=[{"title": "Board release"}, {"title": "Board followup"}],
            raw=[raw],
            status="snapshot",
            source_url="https://www.federalreserve.gov/feeds/press_all.xml",
            provider_id="ext_fed",
        ),
        request_query=query,
    )
    feed = await research.discovery.registered_feed(origin_sid, dataset_id=snapshot["dataset_id"])
    theme = feed["themes"][0]
    frozen = await research.discovery.prepare(
        Prepare(
            request_id=str(uuid4()),
            feed_id=feed["feed_id"],
            horizon="short",
            theme_id=theme["id"],
            material_ids=[item["id"] for item in theme["materials"]],
            target_mode="fingpt",
            question="核对官方摘要",
        )
    )
    sid = frozen["session_id"]
    record = research.store.data["discovery_handoffs"][frozen["handoff_id"]]
    assert research.discovery.trusted_context(sid)["source_kind"] == "registered_feed"
    research.store.session(sid).update(
        source_scope=["uploads", "datahub"], delivery_key="metadata-proof"
    )
    contract = make_contract("a" * 24, "核对官方摘要", ["公告来源与摘要"], "2026-11-23", "deep")
    receipt = {
        "research_contract": contract,
        "delivery": {"task_id": contract["task_id"], "required_formats": ["md"]},
    }
    research.store.data["receipts"][sid + ":metadata-proof"] = receipt
    research.store.save()
    tools = qa_tools.TurnTools(research, sid, receipt, record["attachment_ids"])
    native_runs = []
    native_run = qa_tools.sandbox.run_script

    def recorded_native_run(*args, **kwargs):
        native_runs.append(True)
        return native_run(*args, **kwargs)

    monkeypatch.setattr(qa_tools.sandbox, "run_script", recorded_native_run)
    schema = next(
        tool["function"]["parameters"]
        for tool in tools.schemas()
        if tool["function"]["name"] == "write_research_report"
    )
    validator = Draft202012Validator(schema)
    plan = {
        "title": "美联储公告摘要",
        "missing": [],
        "sections": [
            {
                "id": "summary_" + str(i),
                "heading": "公告摘要",
                "source_ids": [source["id"]],
                "evidence_ids": [],
                "requirement_ids": ["r1"],
            }
            for i, source in enumerate(record["registered_feed_sources"].values())
        ],
    }
    validator.validate({"plan": plan})
    for field in ("analysis", "summary", "calculations", "controls", "undeclared"):
        invalid = (
            {**plan, "sections": [{**plan["sections"][0], "analysis": "共20条公告"}]}
            if field == "analysis"
            else {**plan, field: []}
        )
        assert list(validator.iter_errors({"plan": invalid})), field
        response = await tools.call(
            {"name": "write_research_report", "arguments": {"plan": invalid}}, None
        )
        assert response["data"] == {
            "status": "unavailable",
            "code": "qa_report_metadata_plan_required",
        }
        assert "source_ids" in response["warnings"][0] and "analysis" in response["warnings"][0]
        assert (
            not tools.report_written
            and not (research.store.directory(sid) / "outputs/report.md").exists()
        )
    dataset_plan = {
        **plan,
        "sections": [{**plan["sections"][0], "source_ids": ["dataset:" + frozen["dataset_id"]]}],
    }
    assert list(validator.iter_errors({"plan": dataset_plan}))
    incomplete_plan = {**plan, "sections": plan["sections"][:1]}
    validator.validate({"plan": incomplete_plan})
    for invalid, code in (
        (dataset_plan, "qa_report_metadata_source_invalid"),
        (incomplete_plan, "qa_report_metadata_sources_incomplete"),
    ):
        response = await tools.call(
            {"name": "write_research_report", "arguments": {"plan": invalid}}, None
        )
        assert response["data"] == {"status": "unavailable", "code": code}
        assert "file:" in response["warnings"][0]
        assert not native_runs and not tools.report_written
    response = await tools.call(
        {"name": "write_research_report", "arguments": {"plan": plan}}, None
    )
    assert response["data"]["status"] == "generated", response
    markdown = (research.store.directory(sid) / "outputs/report.md").read_text()
    assert "Official RSS summary." in markdown and "Board release" in markdown
    assert "2026-11-20" in markdown and "other20261120a.htm" in markdown
    assert "Official followup summary." in markdown and len(native_runs) == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
@pytest.mark.parametrize("invalid_field", ["summary", "analysis"])
@pytest.mark.asyncio
async def test_qa_report_wrong_summary_type_then_valid_source_plan(tmp_path, invalid_field):
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
    invalid = (
        {**plan, "summary": "摘要"}
        if invalid_field == "summary"
        else {**plan, "sections": [{**plan["sections"][0], "analysis": "政策利率为3.5%。"}]}
    )
    rejected = await tools.call(
        {"name": "write_research_report", "arguments": {"plan": invalid}},
        None,
    )
    expected = (
        "research_report_plan_limit"
        if invalid_field == "summary"
        else "research_report_analysis_unbound"
    )
    assert rejected["data"] == {"status": "unavailable", "code": expected}
    assert "/" not in json.dumps(rejected) and "Traceback" not in json.dumps(rejected)
    assert not tools.report_written
    assert not (store.directory(sid) / "outputs/report.md").exists()
    result = await tools.call({"name": "write_research_report", "arguments": {"plan": plan}}, None)
    assert result["data"]["status"] == "generated", result
    markdown = (store.directory(sid) / "outputs/report.md").read_text()
    assert "2026-11-18" in markdown and "monetary20261118a.htm" in markdown
    assert "官方 RSS 摘要：Minutes of the Federal Open Market Committee" in markdown
    assert tools.report_written and tools.calls == 2


@pytest.mark.parametrize("discovery", [False, True])
@pytest.mark.asyncio
async def test_qa_frozen_pages_round_trip_below_worker_limit(tmp_path, discovery):
    from app.research_web.datahub import DataHub
    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "Frozen pagination proof")["id"]
    store.session(sid)["source_scope"] = ["datahub"]
    rows = [{"id": i, "description": ("统计公报😀\0" * 150)} for i in range(23)]
    assert len(json.dumps(rows, ensure_ascii=False).encode("utf-16-le")) // 2 > 24000
    datahub = DataHub(store)
    query = BusinessQuery(
        capability="external_data", source="ext_fed", parameters={"dataset": "news"}
    )
    manifest = datahub.snapshots.publish(
        sid,
        query,
        Result(rows=rows, status="snapshot", provider_id="ext_fed", as_of="2026-11-23"),
        request_query=query,
    )
    context = {
        "handoff_id": "pagination-proof",
        "dataset_id": manifest["dataset_id"],
        "dataset_manifest_sha256": manifest["manifest_sha256"],
        "cutoff": "2026-11-23T01:00:00+00:00",
    }
    if discovery:
        store.session(sid)["purpose"] = "discovery_research"
    service = SimpleNamespace(
        store=store,
        datahub=datahub,
        discovery=SimpleNamespace(trusted_context=lambda _sid: context),
    )
    tools = qa_tools.TurnTools(service, sid, {"delivery": {"task_id": "a" * 24}}, [])
    offset, pages, actual = 0, [], []
    while offset is not None:
        args = {"offset": offset, **({} if discovery else {"dataset_id": manifest["dataset_id"]})}
        response = await tools.call(
            {
                "name": "read_frozen_discovery" if discovery else "read_frozen_dataset",
                "arguments": args,
            },
            None,
        )
        page = response["data"]
        assert (
            len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-16-le"))
            // 2
            <= qa_tools.SOURCE_PAGE_JSON_LIMIT
        )
        assert page["offset"] == offset and page["total"] == len(rows)
        assert page["dataset_id"] == manifest["dataset_id"]
        assert page["manifest_sha256"] == manifest["manifest_sha256"]
        if discovery:
            assert page["cutoff"] == context["cutoff"]
        actual.extend(page["items"])
        pages.append(page)
        offset = page["next_offset"]
    assert len(pages) > 1 and actual == rows


@pytest.mark.asyncio
async def test_qa_report_unknown_error_keeps_generic_code_without_stderr(monkeypatch):
    from pathlib import Path

    store = SimpleNamespace(
        session=lambda _sid: {"source_scope": []}, directory=lambda _sid: Path("/")
    )
    receipt = {
        "research_contract": {
            "task_id": "a" * 24,
            "sha256": "b" * 64,
            "as_of": "2026-11-23",
            "requirements": [{"id": "r1"}],
        },
        "delivery": {"task_id": "a" * 24, "required_formats": ["md"]},
    }
    tools = qa_tools.TurnTools(
        SimpleNamespace(store=store, delivery=SimpleNamespace(config=None)),
        "error-proof",
        receipt,
        [],
    )
    monkeypatch.setattr(qa_tools, "write_business_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        qa_tools.sandbox,
        "run_script",
        lambda *_args: qa_tools.sandbox.ScriptResult(
            "failed",
            stderr="Traceback: /private/credential-file\nValueError: private-error-data\n",
            exit_code=1,
        ),
    )
    result = await tools.call({"name": "write_research_report", "arguments": {"plan": {}}}, None)
    assert result["data"] == {"status": "unavailable", "code": "qa_report_plan_failed"}
    assert "private" not in json.dumps(result) and "Traceback" not in json.dumps(result)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("source_kind", ["registered_feed", "event"])
async def test_send_freezes_discovery_requirements_for_actual_source_scope(
    tmp_path, monkeypatch, source_kind
):
    import asyncio
    from uuid import uuid4

    from test_discovery import ARTICLE, EVENT

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result
    from app.research_web.discovery import DiscoveryService, Prepare
    from app.research_web.discovery.fed import REPORT_REQUIREMENTS

    async def connection(_service, _row):
        return ("test", "test", None, "test")

    observed = []

    async def worker(request, _callbacks, _emit):
        observed.append(request)
        # Stop at the real worker boundary: no model call or report is simulated.

    async def reader(path, params=None):
        if path == "/radar":
            return {"industries": [], "stats": {}}
        if path == "/intelligence":
            return {
                "as_of": None,
                "cache_stale": True,
                "logics": [{"id": "technology", "name": "科技"}],
                "reading": [EVENT],
                "daily_reading": {"analysis_error": "ValueError"},
            }
        return {"event": EVENT, "articles": [ARTICLE], "revisions": [], "retrieved_at": None}

    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    monkeypatch.setattr(qa_model, "connection", connection)
    monkeypatch.setattr(qa_execution, "run_worker", worker)
    service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
    service.discovery = DiscoveryService(service, reader=reader)
    try:
        if source_kind == "registered_feed":
            origin_sid = service.store.create("fingpt", "原始 Fed 快照")["id"]
            query = BusinessQuery(
                capability="external_data", source="ext_fed", parameters={"dataset": "news"}
            )
            raw = (
                b"<rss><channel><item><guid>send-contract</guid><title>Board release</title>"
                b"<link>https://www.federalreserve.gov/newsevents/pressreleases/other20261120a.htm</link>"
                b"<pubDate>Fri, 20 Nov 2026 12:00:00 GMT</pubDate>"
                b"<description>Official RSS summary.</description></item></channel></rss>"
            )
            manifest = service.datahub.snapshots.publish(
                origin_sid,
                query,
                Result(
                    rows=[{"title": "Board release"}],
                    raw=[raw],
                    status="snapshot",
                    source_url="https://www.federalreserve.gov/feeds/press_all.xml",
                    provider_id="ext_fed",
                ),
                request_query=query,
            )
            feed = await service.discovery.registered_feed(
                origin_sid, dataset_id=manifest["dataset_id"]
            )
        else:
            feed = await service.discovery.feed(horizon="short")
        theme = feed["themes"][0]
        frozen = await service.discovery.prepare(
            Prepare(
                request_id=str(uuid4()),
                feed_id=feed["feed_id"],
                horizon="short",
                theme_id=theme["id"],
                material_ids=[item["id"] for item in theme["materials"]],
                target_mode="fingpt",
                question="核对本轮冻结资料",
            )
        )
        sid = frozen["session_id"]
        context = service.discovery.trusted_context(sid)
        assert context.get("source_kind", "event") == source_kind
        record = service.store.data["discovery_handoffs"][frozen["handoff_id"]]
        key = "source-scope-contract"
        result = await service.send(
            sid,
            "核对本轮冻结资料",
            key,
            attachments=record.get("attachment_ids", []),
            formats=["md"],
            research_requirements=["保留调用方范围"],
        )
        assert result == {"accepted": True}
        await asyncio.gather(*list(service.qa.tasks.values()))
        receipt = service.store.data["receipts"][sid + ":" + key]
        requirements = [row["text"] for row in receipt["research_contract"]["requirements"]]
        expected = (
            [REPORT_REQUIREMENTS]
            if source_kind == "registered_feed"
            else [
                "区分来源陈述、已核验事实与推断，引用固定资料版本。",
                "列明反方证据、失效条件和下一验证事项。",
                "保留陈旧资料、未知时间、来源与覆盖缺口，不将二手归档当网页全文。",
            ]
        )
        assert requirements == ["保留调用方范围", *expected]
        assert receipt["research_contract"]["as_of"] == context["cutoff"]
        assert len(observed) == 1
        assert service.qa.ledger(sid)["status"] == "failed"
        assert not (service.store.directory(sid) / "outputs/report.md").exists()
    finally:
        await service.close()


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
