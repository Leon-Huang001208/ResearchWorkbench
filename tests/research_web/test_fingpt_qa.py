"""FinGPT Host integration: real bounded Node subprocesses, no paid models."""

import asyncio
from types import SimpleNamespace

import pytest

from app.research_web.fingpt.routes import Ask
from app.research_web.fingpt.service import ENGINE, FinGPTQA
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


@pytest.fixture
def engine(tmp_path):
    entry = tmp_path / "entry.mjs"
    entry.write_text("""
import {readFileSync} from 'node:fs';
const input=JSON.parse(readFileSync(0,'utf8'));
const emit=(event,data)=>process.stdout.write(JSON.stringify({event,data})+'\\n');
if(input.operation==='tiers')emit('tiers',{tiers:Object.fromEntries(['lite','ultra','frontier','kimi'].map(k=>[k,{label:k,configured:true}]))});
else if(input.msg==='wait')setInterval(()=>{},1000);
else {
 emit('setup',{content:'fixture',mode:input.mode,tier:input.tier});
 emit('start_of_agent',{agent_name:'fixture'});
 emit('tool_call',{tool_call_id:'c1',tool_name:'quote',title:'行情',group:'金融数据库',args:{},display:'测试行情'});
 emit('tool_call_result',{tool_call_id:'c1',ok:true,sources:[{id:'S1',title:'测试来源',provider:'Fixture'}],source_ids:['S1']});
 if(input.mode==='agent')for(let i=1;i<=3;i++)emit('update',{id:'work_note',sub_id:i,content:{title:`笔记${i}.md`,body:'依据[S1]'}});
 emit('_qa',{content:'# 测试报告\\n## 一、核心结论\\n有来源[S1]\\n## 二、风险\\n待核验'});
 emit('answer_source',{content:[{id:'S1',title:'测试来源'}]});
 emit('update',{id:'_final',content:{elapsed_ms:1}});
}
""")
    service = SimpleNamespace(
        store=Store(tmp_path / "data"),
        summary=ResearchService.summary,
        datahub=SimpleNamespace(summaries=lambda sid: []),
        running={},
        listeners=set(),
    )
    return FinGPTQA(service, entry=entry)


def run(coro):
    return asyncio.run(coro)


def test_tiers_are_private_and_project_scope_is_checked(engine):
    result = run(engine.tiers())
    assert set(result["tiers"]) == {"lite", "ultra", "frontier", "kimi"}
    assert all(set(v) == {"label", "configured"} for v in result["tiers"].values())
    with pytest.raises(StoreError):
        engine.create(project_id="unknown")
    assert not engine.store.data["sessions"]


@pytest.mark.parametrize("mode", ["quick", "deep", "agent"])
def test_modes_finish_and_materialize_report_in_owned_session(engine, mode):
    async def check():
        row = engine.create("真实子进程测试")
        sid = row["id"]
        rid = await engine.submit(sid, Ask(msg="测试", mode=mode), "fixture-key")
        await engine.running[sid]
        detail = engine.detail(sid)
        assert detail["engine"] == ENGINE
        assert detail["status"] == "completed"
        assert "[S1]" in detail["messages"][-1]["text"]
        assert detail["qa_rounds"][0]["id"] == rid
        assert detail["qa_rounds"][0]["events"][-1]["data"]["id"] == "_final"
        files = engine.store.files(sid)
        assert any(f["name"].startswith("report-") for f in files)
        if mode == "agent":
            assert len([f for f in files if f["name"].startswith("note-")]) == 3
        assert not engine.research.running[sid]

    run(check())


def test_retry_same_key_never_submits_twice_and_conflict_rejected(engine):
    async def check():
        sid = engine.create()["id"]
        first, second = await asyncio.gather(
            *[engine.submit(sid, Ask(msg="测试"), "fixture-same-key") for _ in range(2)]
        )
        assert first == second
        await engine.running[sid]
        assert len(engine._read(sid)["rounds"]) == 1
        with pytest.raises(StoreError):
            await engine.submit(sid, Ask(msg="不同问题"), "fixture-same-key")

    run(check())


def test_stop_terminates_owned_child_and_keeps_partial_receipt(engine):
    async def check():
        sid = engine.create()["id"]
        await engine.submit(sid, Ask(msg="wait"), "fixture-stop")
        for _ in range(100):
            if sid in engine.processes:
                break
            await asyncio.sleep(0.01)
        proc = engine.processes[sid]
        await engine.cancel(sid)
        assert proc.returncode is not None
        assert engine.detail(sid)["status"] == "interrupted"
        assert sid not in engine.running

    run(check())


def test_foreign_attachment_and_legacy_engine_are_not_adopted(engine):
    one = engine.create()["id"]
    two = engine.create()["id"]
    path = engine.store.directory(two) / "inputs" / "only-two.md"
    path.write_text("only belongs to second")
    fid = next(f["id"] for f in engine.store.files(two) if f["name"] == path.name)
    with pytest.raises(StoreError):
        engine._context(one, [fid])
    engine.store.session(one)["engine"] = "dsh"
    with pytest.raises(StoreError):
        run(engine.submit(one, Ask(msg="测试"), "fixture-legacy"))


def test_owned_text_attachment_is_available_as_grounded_context(engine):
    sid = engine.create()["id"]
    path = engine.store.directory(sid) / "inputs" / "evidence.md"
    path.write_text("明确的用户资料")
    fid = next(f["id"] for f in engine.store.files(sid) if f["name"] == path.name)
    assert engine._context(sid, [fid])["files"][0]["text"] == "明确的用户资料"


def test_http_ingress_session_history_sse_and_claw_separation(engine, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from test_api import NativeFixture

    from app.research_web import main
    from app.research_web.main import create_app

    native = NativeFixture()
    research = ResearchService(native, Store(tmp_path / "http-data"))
    monkeypatch.setattr(main, "FinGPTQA", lambda active: FinGPTQA(active, entry=engine.entry))
    with TestClient(create_app(research), base_url="http://127.0.0.1") as client:
        native_create = client.post(
            "/api/research/sessions", json={"mode": "fingpt", "title": "原入口"}
        )
        assert native_create.status_code == 201
        assert native_create.json()["engine"] == ENGINE
        made = client.post("/api/research/fingpt/sessions", json={"title": "新版研究"})
        assert made.status_code == 201
        sid = made.json()["id"]
        accepted = client.post(
            f"/api/research/fingpt/sessions/{sid}/ask",
            json={"msg": "测试"},
            headers={"Idempotency-Key": "http-fixture-key"},
        )
        assert accepted.status_code == 202
        rid = accepted.json()["round_id"]
        stream = client.get(f"/api/research/fingpt/sessions/{sid}/rounds/{rid}/events")
        assert "event: _qa" in stream.text
        assert "event: round_end" in stream.text
        assert "event: answer_source" in stream.text
        assert client.get(f"/api/research/sessions/{sid}").json()["engine"] == ENGINE
        assert any(
            item["id"] == sid for item in client.get("/api/research/sessions").json()["items"]
        )
        assert (
            client.patch(f"/api/research/sessions/{sid}", json={"title": "重命名研究"}).status_code
            == 200
        )
        assert client.delete(f"/api/research/sessions/{sid}").status_code == 200
        assert not any(method == "session.prompt" for method, _ in native.calls)
        assert (
            client.post(
                "/api/research/fingpt/sessions", json={}, headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/research/fingpt/sessions", json={"title": "非法", "project_id": "absent"}
            ).status_code
            == 404
        )
        invalid = client.post(
            f"/api/research/fingpt/sessions/{sid}/ask",
            json={"msg": "测试", "mode": "task"},
            headers={"Idempotency-Key": "http-fixture-key2"},
        )
        assert invalid.status_code == 422
