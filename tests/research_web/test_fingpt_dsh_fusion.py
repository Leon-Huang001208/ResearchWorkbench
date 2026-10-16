"""Single-runtime FinGPT ingress and durable quality contracts, without models."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


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
