"""Single-runtime FinGPT ingress and durable quality contracts, without models."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


def test_host_web_input_retains_provenance_scope_and_cutoff(fusion_api, monkeypatch):
    import json

    from test_research_business_evidence import CPI

    from app.research_web import research_web_sources as reader
    from app.research_web.research_quality import assess_quality, make_contract
    from app.research_web.research_quality_service import (
        business_prompt_index,
        observations,
        source_context,
        write_business_snapshot,
    )
    from app.research_web.resources.research_report import source_id

    client, _, service = fusion_api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    row = service.store.session(sid)
    row["source_scope"] = ["uploads", "web"]
    url = "https://example.org/future-source"
    wid = source_id(url)
    row["web_search_sources"] = [
        {
            "id": wid,
            "title": "Actual future web source",
            "url": url,
            "state": "search_summary",
            "as_of": "2030-01-01",
        }
    ]
    service.store.save()

    async def fetch(_url):
        return {
            "content": "存在经营不确定性。\n" + CPI,
            "as_of": "2030-01-01",
            "date_evidence": [
                {"date": "2030-01-01", "kind": "publication_meta", "text": "2030-01-01"}
            ],
            "final_url": url,
            "response_sha256": "a" * 64,
        }

    monkeypatch.setattr(reader, "fetch_owned_document", fetch)
    value = client.portal.call(reader.read_source, service, sid, "read", wid)
    web = value["source"]
    alias = "file:" + web["file_id"]
    detail = client.get(f"/api/research/sessions/{sid}").json()
    assert alias not in {s["id"] for s in detail["research_sources"]}
    assert next(s for s in detail["research_sources"] if s["id"] == wid)["as_of"] == "2030-01-01"
    upload_response = client.post(
        f"/api/research/sessions/{sid}/uploads",
        files={"files": ("web-" + "0" * 24 + ".md", b"Actual user upload", "text/markdown")},
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded = upload_response.json()["items"][0]
    row["source_scope"] = ["uploads"]
    service.store.save()
    files = service.store.files(sid)
    contract = make_contract("a" * 24, "Risk", ["Risk"], "2026-10-19", "quick")
    actual = observations(
        service, sid, files, [web], task_id=contract["task_id"], contract_sha=contract["sha256"]
    )
    assert not any(o["source_id"] in {alias, wid} for o in actual)
    context = source_context(service, sid, files)
    assert alias not in {s["id"] for s in context["sources"]}
    assert "file:" + uploaded["id"] in {s["id"] for s in context["sources"]}
    assert wid not in {s["id"] for s in source_context(service, sid, files, [web])["sources"]}
    assert business_prompt_index(service, sid, contract)["observations"] == []
    write_business_snapshot(service, sid, contract)
    snapshot = json.loads(
        (service.store.directory(sid) / "resources/research_evidence.json").read_bytes()
    )
    assert snapshot["observations"] == [] and alias not in {s["id"] for s in snapshot["sources"]}
    payload = {
        "task_id": contract["task_id"],
        "title": "Risk",
        "as_of": contract["as_of"],
        "sources": [
            {"id": alias, "title": next(f["name"] for f in files if f["id"] == web["file_id"])}
        ],
        "sections": [
            {"id": "s", "heading": "Risk", "text": "存在经营不确定性。", "citations": [alias]}
        ],
        "notes": [{"stage_id": "s", "text": "存在经营不确定性。", "citations": [alias]}],
        "coverage": [
            {"requirement_id": "r1", "section_ids": ["s"], "excerpt": "存在经营不确定性。"}
        ],
    }
    assert assess_quality(contract, payload, context["sources"], actual)["status"] != "passed"
    row["source_scope"] = ["uploads", "web"]
    actual = observations(
        service, sid, files, [web], task_id=contract["task_id"], contract_sha=contract["sha256"]
    )
    assert any(o["source_id"] == wid for o in actual) and not any(
        o["source_id"] == alias for o in actual
    )
    payload["sources"] = [{k: web[k] for k in ["id", "title", "url", "as_of"]}]
    payload["sections"][0]["citations"] = [wid]
    payload["notes"][0]["citations"] = [wid]
    assessed = assess_quality(contract, payload, [*context["sources"], web], actual)
    assert assessed["status"] == "incomplete" and "source_after_cutoff:" + wid in assessed["issues"]


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    """Fixture transport never reads or writes the host system credential store."""
    import keyring

    values = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, account: values.get((service, account))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, account, value: values.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, account: values.pop((service, account), None)
    )


@pytest.fixture
def fusion_api(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "data"))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def test_script_report_context_comes_from_current_valid_frozen_contract(fusion_api, monkeypatch):
    client, _, service = fusion_api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid: True)
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={
            "text": "Compare actual CPI",
            "expected_formats": [],
            "research_requirements": ["Compare actual values"],
        },
        headers={"Idempotency-Key": "report-plan-binding"},
    )
    assert response.status_code == 202
    receipt, _ = service._task_capabilities(sid)
    contract = receipt["research_contract"]
    context = service.native_admission(sid, tool_name="research_run_script")["report_context"]
    assert context == {
        "task_id": contract["task_id"],
        "contract_sha256": contract["sha256"],
        "as_of": contract["as_of"],
        "requirement_ids": [r["id"] for r in contract["requirements"]],
        "formats": ["html", "docx", "pdf"],
    }
    contract["sha256"] = "0" * 64
    assert "report_context" not in service.native_admission(sid, tool_name="research_run_script")
    contract.pop("requirements")
    scope = service.native_admission(sid, tool_name="research_run_script")
    assert scope["admitted"] is True and "report_context" not in scope


@pytest.mark.parametrize("explicit", [None, ["html"]])
def test_frozen_formats_match_actual_native_delivery_and_checked_archive(
    fusion_api, monkeypatch, explicit
):
    """Exercise real file inspection instead of manufacturing valid=True receipts."""
    import json
    import sys
    from functools import partial

    from app.research_web.research_quality_service import check_quality
    from app.research_web.resources.research_report_plan import write_business_report_plan

    if sys.platform != "darwin":
        pytest.skip("actual file inspection belongs to the native Mac task")
    client, native, service = fusion_api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid: True)
    payload = {
        "text": "离线核验，只生成HTML和DOCX，不发送到外部。",
        "research_mode": "deep",
        "research_as_of": "2026-10-16",
    }
    if explicit is not None:
        payload["expected_formats"] = explicit
    headers = {"Idempotency-Key": "actual-two-format-delivery"}
    response = client.post(f"/api/research/sessions/{sid}/messages", json=payload, headers=headers)
    assert response.status_code == 202, response.text
    receipt, _ = service._task_capabilities(sid)
    expected = explicit if explicit is not None else ["html", "docx"]
    assert receipt["delivery"]["required_formats"] == expected
    context = service.native_admission(sid, tool_name="research_run_script")["report_context"]
    assert context["formats"] == expected
    plan = {
        "title": "有缺口的可用报告",
        "sections": [
            {
                "id": "gap",
                "heading": "缺口",
                "evidence_ids": [],
                "requirement_ids": context["requirement_ids"],
                "analysis": "所需事实证据尚未取得。",
            }
        ],
        "missing": ["证据不足，不作事实结论。"],
    }
    with monkeypatch.context() as scoped:
        scoped.chdir(service.store.directory(sid))
        written = write_business_report_plan(context, plan)
        assert set(written["written"]) == {"json", "md", "audit", *expected}
    entries = [
        {
            "event": {
                "seq": 1,
                "type": "user/message",
                "data": {"content": receipt["delivery"]["marker"]},
            }
        },
        {"event": {"seq": 2, "type": "turn/end", "data": {}}},
    ]
    checked = client.portal.call(
        partial(service.delivery.refresh, sid, entries, busy=False, connected=True)
    )
    assert checked["status"] == "completed", checked
    assert checked["missing_formats"] == []
    assert set(expected) <= {f["format"] for f in checked["files"] if f["valid"]}
    assert "pdf" not in {f["format"] for f in checked["files"]}
    quality = client.portal.call(check_quality, service, sid)
    assert quality["status"] == "incomplete"  # Missing evidence is never waived by valid files.
    assert quality["report_delivery"]["status"] == "bound"
    assert not any(i.startswith("report_artifact") for i in quality["issues"])
    assert (
        client.post(
            f"/api/research/sessions/{sid}/messages", json=payload, headers=headers
        ).status_code
        == 202
    )
    assert sum(method == "session.prompt" for method, _ in native.calls) == 1
    manifest = json.loads(
        (service.store.directory(sid) / "outputs/research-report.json").read_text()
    )
    assert manifest["report_formats"] == expected


@pytest.mark.parametrize("status", ["accepted", "pending", "unknown"])
def test_format_default_upgrade_replays_frozen_request_without_resubmission(
    fusion_api, monkeypatch, status
):
    from app.research_web.resources import research_report

    client, native, service = fusion_api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid: True)
    payload = {
        "text": "离线核验，只生成HTML和DOCX，不发送到外部。",
        "research_mode": "deep",
        "research_as_of": "2026-10-16",
        "research_requirements": ["核验全部数字"],
    }
    headers = {"Idempotency-Key": "before-format-upgrade"}
    path = f"/api/research/sessions/{sid}/messages"
    actual = research_report.required_report_formats
    with monkeypatch.context() as old_version:
        old_version.setattr(
            research_report,
            "required_report_formats",
            lambda value, delivery=None: (
                ("html", "docx", "pdf") if isinstance(value, str) else actual(value, delivery)
            ),
        )
        initial = client.post(path, json=payload, headers=headers)
    assert initial.status_code == 202, initial.text
    receipt = service.store.receipt(sid, "before-format-upgrade")
    digest = receipt["digest"]
    receipt["status"] = status
    service.store.save()
    retry = client.post(path, json=payload, headers=headers)
    if status == "accepted":
        assert retry.status_code == 202, retry.text
    else:
        assert retry.status_code == 503 and retry.json()["error"]["code"] == "admission_unknown"
    assert receipt["digest"] == digest and receipt["status"] == status
    assert receipt["delivery"]["required_formats"] == ["html", "docx", "pdf"]
    assert sum(method == "session.prompt" for method, _ in native.calls) == 1
    for changes in (
        {"text": payload["text"] + "不同问题"},
        {"research_requirements": ["减少要求"]},
        {"research_as_of": "2026-10-17"},
        {"research_mode": "agent"},
        {"expected_formats": ["html", "docx"]},
    ):
        changed = client.post(path, json={**payload, **changes}, headers=headers)
        assert changed.status_code == 400 and changed.json()["error"]["code"] == "invalid_resource"
    frozen = receipt["delivery"]
    for invalid in (
        None,
        {**frozen, "task_id": "0" * 24},
        {**frozen, "required_formats": ["html", "html"]},
    ):
        receipt["delivery"] = invalid
        damaged = client.post(path, json=payload, headers=headers)
        assert damaged.status_code == 503 and damaged.json()["error"]["code"] == "admission_unknown"
    receipt["delivery"] = frozen
    assert sum(method == "session.prompt" for method, _ in native.calls) == 1


@pytest.mark.parametrize("mode,depth", [("quick", "instant"), ("deep", "deep"), ("agent", "deep")])
def test_three_modes_still_create_owned_dsh_sessions(tmp_path, mode, depth):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "data"))
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        made = client.post("/api/research/sessions", json={"research_mode": mode})
        assert made.status_code == 201
        assert made.json()["research_mode"] == mode
        assert made.json()["research_depth"] == depth
        assert any(method == "session.create" for method, _ in native.calls)
        assert not (service.store.directory(made.json()["id"]) / "fingpt.json").exists()


def test_quality_ingress_authentication_and_contract_is_host_owned(tmp_path):
    from app.research_web.research_quality_service import prepare_contract, quality_result

    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "data"))
    sid = service.store.create("fingpt", "研究")["id"]
    row = service.store.session(sid)
    row.update(created=True, delivery_key="request-key")
    receipt = {"delivery": service.delivery.begin(sid, "request-key", []), "status": "accepted"}
    service.store.data["receipts"][f"{sid}:request-key"] = receipt
    prepare_contract(service, sid, receipt, "原始研究要求", ["利润", "风险"], "2026-10-16", "deep")
    contract = receipt["research_contract"]
    assert [r["text"] for r in contract["requirements"]] == ["利润", "风险"]
    result = quality_result(service, sid, receipt, [], [])
    assert result["status"] == "incomplete"
    assert "report_missing" in result["issues"]
    # Loading a view does not consume a supplementary research opportunity.
    assert result["repair_count"] == 0
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        path = "/api/research/internal/data/research-quality"
        assert client.post(path, json={"session_id": sid, "operation": "check"}).status_code == 403
        response = client.post(
            path,
            json={"session_id": sid, "operation": "check"},
            headers={"X-Research-Data-Key": service.datahub.control["token"]},
        )
        assert response.status_code == 200
        assert response.json()["repair_count"] == 1
        again = client.post(
            path,
            json={"session_id": sid, "operation": "check"},
            headers={"X-Research-Data-Key": service.datahub.control["token"]},
        )
        assert again.json() == response.json()
        assert not any(method == "session.prompt" for method, _ in native.calls)


def test_unknown_mode_does_not_register_a_session(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "data"))
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        assert (
            client.post("/api/research/sessions", json={"research_mode": "unbounded"}).status_code
            == 422
        )
    assert not service.store.data["sessions"]


def test_source_reader_callback_requires_private_auth_and_cannot_take_a_url(fusion_api):
    client, native, service = fusion_api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    path = "/api/research/internal/data/research-source"
    body = {"session_id": sid, "call_id": "native:read", "operation": "list"}
    assert client.post(path, json=body).status_code == 403
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200 and response.json() == {"sources": []}
    activity = {
        "id": "native:search",
        "title": "web_search",
        "status": "completed",
        "detail": "External web content follows.\n\nSources:\n- [Exact native title](https://example.org/report#1)",
    }
    response = client.post(
        path,
        json={**body, "call_id": "native:list2", "search_activities": [activity]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["sources"][0]["title"] == "Exact native title"
    assert response.json()["sources"][0]["state"] == "search_summary"
    assert (
        client.post(path, json={**body, "url": "https://example.org/"}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            path + "/cancel", json={"session_id": sid, "call_id": "native:read"}
        ).status_code
        == 403
    )
    assert not any(method == "session.prompt" for method, _ in native.calls)


def test_contract_preflight_failure_does_not_reserve_unsent_request(fusion_api, monkeypatch):
    client, native, service = fusion_api
    sid = client.post("/api/research/sessions", json={}).json()["id"]

    def reject(*args, **kwargs):
        raise ValueError("unsafe archive")

    monkeypatch.setattr("app.research_web.service.prepare_contract", reject)
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "研究风险"},
        headers={"Idempotency-Key": "preflight-fail"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "research_contract_preflight_failed"
    assert f"{sid}:preflight-fail" not in service.store.data["receipts"]
    assert not any(method == "session.prompt" for method, _ in native.calls)


def test_followup_adds_user_request_without_dropping_original(tmp_path):
    from app.research_web.research_quality_service import prepare_contract

    service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
    sid = service.store.create("fingpt", "研究")["id"]
    first = {"delivery": {"task_id": "a" * 24}}
    service.store.data["receipts"][f"{sid}:first"] = first
    prepare_contract(service, sid, first, "分析风险", None, "2026-10-16", "quick")
    second = {"delivery": {"task_id": "b" * 24}}
    prepare_contract(service, sid, second, "再增加估值分析", None, None, "agent")
    assert [r["text"] for r in second["research_contract"]["requirements"]] == [
        "分析风险",
        "再增加估值分析",
    ]
    assert second["research_contract"]["previous_task_id"] == "a" * 24


def test_quality_queue_binds_receipt_after_acquiring_lock(tmp_path):
    from app.research_web.research_quality_service import check_quality, prepare_contract

    async def run():
        service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
        sid = service.store.create("fingpt", "研究")["id"]
        old, new = [{"delivery": {"task_id": char * 24}} for char in ("a", "b")]
        service.store.data["receipts"].update({f"{sid}:old": old, f"{sid}:new": new})
        prepare_contract(service, sid, old, "原要求", None, "2026-10-16", "quick")
        prepare_contract(service, sid, new, "新增要求", None, None, "quick")
        service.store.session(sid)["delivery_key"] = "old"

        async def detail(_sid):
            return {
                "research_quality": {
                    "status": "incomplete",
                    "issues": ["report_missing"],
                    "contract": new["research_contract"],
                },
                "research_report": None,
            }

        service.detail = detail
        await service.lock.acquire()
        task = asyncio.create_task(check_quality(service, sid))
        await asyncio.sleep(0)
        service.store.session(sid)["delivery_key"] = "new"
        service.lock.release()
        result = await task
        assert result["contract"]["task_id"] == "b" * 24
        assert new["quality_repair_count"] == 1
        assert old["quality_repair_count"] == 0

    asyncio.run(run())


def test_history_display_limit_is_not_a_missing_archive(tmp_path, monkeypatch):
    from app.research_web.research_quality_service import quality_versions

    service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
    sid = service.store.create("fingpt", "研究")["id"]
    versions = []
    for index in range(21):
        task = f"{index:024x}"
        version = {
            "task_id": task,
            "version_id": task,
            "directory": "report-versions/" + task,
            "files": [],
        }
        (service.store.directory(sid) / "outputs" / version["directory"]).mkdir(parents=True)
        service.store.data["receipts"][f"{sid}:{index}"] = {
            "research_contract": {"task_id": task},
            "quality_archive": version,
        }
        versions.append(version)
    monkeypatch.setattr(
        "app.research_web.research_quality_service.list_report_versions", lambda *_: versions[-20:]
    )
    assert len(quality_versions(service, sid)) == 20


def test_quality_cannot_use_upload_excluded_by_source_scope(tmp_path):
    from app.research_web.research_quality_service import prepare_contract, quality_result
    from app.research_web.resources.research_report import write_research_report

    service = ResearchService(NativeFixture(), Store(tmp_path / "data"))
    sid = service.store.create("fingpt", "研究")["id"]
    service.store.session(sid)["source_scope"] = ["web"]
    (service.store.directory(sid) / "inputs" / "risk.txt").write_text("存在经营不确定性。")
    fid = next(f["id"] for f in service.store.files(sid) if f["kind"] == "inputs")
    receipt = {"delivery": {"task_id": "a" * 24}}
    prepare_contract(service, sid, receipt, "风险", None, "2026-10-16", "quick")
    source = {"id": "file:" + fid, "title": "risk.txt"}
    write_research_report(
        service.store.directory(sid) / "outputs",
        {
            "task_id": "a" * 24,
            "title": "风险",
            "as_of": "2026-10-16",
            "sections": [
                {
                    "id": "risk",
                    "heading": "风险",
                    "text": "存在经营不确定性。",
                    "citations": [source["id"]],
                }
            ],
            "sources": [source],
            "notes": [
                {"stage_id": "risk", "text": "存在经营不确定性。", "citations": [source["id"]]}
            ],
            "coverage": [
                {"requirement_id": "r1", "section_ids": ["risk"], "excerpt": "存在经营不确定性。"}
            ],
        },
    )
    result = quality_result(service, sid, receipt, service.store.files(sid), [source])
    assert result["status"] != "passed"
    assert any(issue.startswith("source_unverified:") for issue in result["issues"])


@pytest.mark.parametrize("business", ["numeric", "quote", "empty"])
def test_actual_business_input_gets_one_consistent_report_route(fusion_api, monkeypatch, business):
    """Real uploaded CPI previously received plan guidance and contradictory legacy instructions."""
    from test_research_business_evidence import CPI

    client, native, service = fusion_api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid: True)
    attachment_ids = []
    if business != "empty":
        response = client.post(
            f"/api/research/sessions/{sid}/uploads",
            files={
                "files": (
                    "actual-evidence.md",
                    (
                        CPI
                        if business == "numeric"
                        else "AI RMF\n\nGovernance is a cross-cutting function that enables organizations to manage risks."
                    ).encode(),
                    "text/markdown",
                )
            },
        )
        assert response.status_code == 200
        attachment_ids = [response.json()["items"][0]["id"]]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={
            "text": "Compare CPI and preserve every requested Summary metric name.",
            "research_requirements": ["Compare inflation"],
            "expected_formats": ["md", "xlsx"],
            "attachment_ids": attachment_ids,
        },
        headers={"Idempotency-Key": "consistent-business-route"},
    )
    assert response.status_code == 202, response.text
    sent = next(payload for method, payload in native.calls if method == "session.prompt")
    prompt = sent["content"] if isinstance(sent.get("content"), str) else str(sent)
    assert "arithmetic_checks只检查算术" in prompt
    assert "report_delivery.files" in prompt
    if business in {"numeric", "quote", "empty"}:
        assert "report_plan" in prompt
        assert "numeric_claims逐项声明" not in prompt
        assert "coverage填写" not in prompt
        assert "payload 必须包含" not in prompt
        assert "from research_report import write_research_report, source_id" not in prompt
        assert "工作簿键" in prompt and "missing" in prompt and "最多进行一次补查" in prompt
        assert "起初索引为空不切回手写payload" in prompt

    receipt, _ = service._task_capabilities(sid)
    from app.research_web.research_quality_service import business_prompt_index

    observed = business_prompt_index(service, sid, receipt["research_contract"])["observations"]
    if business == "quote":
        assert observed and all(row["kind"] == "business_quote" for row in observed)
        assert "规范文件直接调用research_run_script(report_plan" in prompt
