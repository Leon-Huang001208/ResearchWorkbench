"""Actual financial dates and imported-summary/source-quality separation."""

import hashlib
import json

import pytest
import test_workbench_operations as fixtures
from test_api import isolated_keyring  # noqa: F401
from test_asset_research_workspace import seed
from test_scenario_handoffs import scenario_body

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result

api = fixtures.api


@pytest.mark.parametrize("field", ["report_period", "publication_date", "published_at"])
def test_known_actual_financial_dates_after_cutoff_rejected(api, field):
    client, service = api
    _, sid, _ = seed(client, service, "600600.SH")
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600600.SH"}
    )
    row = {
        "asset": "600600.SH",
        "report_period": "2026-06-30",
        "publication_date": "2026-08-01",
        "revenue": 100,
        field: "2026-12-31",
        "is_forecast": True,
    }
    dataset = service.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[row], raw=[b"offline actual financial"], status="snapshot", as_of="2026-06-30"
        ),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
    )
    body = scenario_body()
    body.update(source_session_id=sid, dataset_ids=[dataset["dataset_id"]])
    body["scenario_inputs"]["material_ids"] = body["dataset_ids"]
    before = len(service.store.data["sessions"])
    response = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "known-financial-" + field}
    )
    assert response.status_code == 409, response.text
    assert len(service.store.data["sessions"]) == before


def test_unknown_financial_dates_remain_gaps_and_future_forecast_horizon_is_not_actual_period(api):
    client, service = api
    _, sid, _ = seed(client, service, "600600.SH")
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600600.SH"}
    )
    for key, row, expected in [
        (
            "unknown",
            {"asset": "600600.SH", "revenue": 100, "forecast_period": "2027-12-31"},
            {"financial_report_period_unknown", "financial_publication_date_unknown"},
        ),
        (
            "actual",
            {
                "asset": "600600.SH",
                "report_period": "2026-06-30",
                "publication_date": "2026-08-01",
                "revenue": 100,
                "forecast_period": "2027-12-31",
            },
            set(),
        ),
    ]:
        dataset = service.datahub.snapshots.publish(
            sid,
            query,
            Result(rows=[row], raw=[b"offline reported financial"], status="snapshot"),
            request_query=query,
            authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
        )
        body = scenario_body()
        body.update(source_session_id=sid, dataset_ids=[dataset["dataset_id"]])
        body["scenario_inputs"]["material_ids"] = body["dataset_ids"]
        response = client.post(
            "/api/research/handoffs",
            json=body,
            headers={"Idempotency-Key": "financial-date-" + key},
        )
        assert response.status_code == 201, response.text
        missing = {
            item["code"]
            for item in response.json()["scenario_context"]["scenario"]["missing"]
            if item["code"].startswith("financial_")
        }
        assert missing == expected


def test_arbitrary_summary_does_not_inherit_mixed_real_source_report_quality(api, monkeypatch):
    from test_research_quality import example

    from app.research_web.resources.research_report import write_research_report

    client, service = api
    oid, _, _ = seed(client, service, "600600.SH")
    histories = {}
    original_history = service.client.history

    async def history(sid):
        return histories[sid] if sid in histories else await original_history(sid)

    monkeypatch.setattr(service.client, "history", history)
    proofs, expected = [], {}
    for status in ["passed", "incomplete"]:
        sid = client.post("/api/research/sessions", json={"source_scope": ["uploads"]}).json()["id"]
        (service.store.directory(sid) / "inputs/source.txt").write_text("存在经营不确定性。")
        source = next(item for item in service.store.files(sid) if item["name"] == "source.txt")
        sent = client.post(
            f"/api/research/sessions/{sid}/messages",
            json={
                "text": "核查风险",
                "research_requirements": ["风险"],
                "research_as_of": "2026-10-26",
                "expected_formats": ["html"],
            },
            headers={"Idempotency-Key": "source-quality-" + status},
        )
        assert sent.status_code == 202, sent.text
        receipt = service.store.receipt(sid, "source-quality-" + status)
        contract = receipt["research_contract"]
        _, report, _ = example()
        report.update(task_id=contract["task_id"], as_of=contract["as_of"])
        source_id = "file:" + source["id"]
        report["sources"] = [{"id": source_id, "title": "source.txt"}]
        report["sections"][0]["citations"] = [source_id]
        report["notes"][0]["citations"] = [source_id]
        if status == "incomplete":
            report["coverage"] = []
        write_research_report(service.store.directory(sid) / "outputs", report, formats=["html"])
        histories[sid] = [
            {
                "event": {
                    "seq": 1,
                    "type": "user/message",
                    "data": {"content": receipt["delivery"]["marker"]},
                }
            },
            {"event": {"seq": 2, "type": "turn/end", "data": {}}},
        ]

        async def native_frames(_channel, current_sid=sid):
            for entry in histories[current_sid]:
                yield {
                    "payload": {
                        "type": "session/event",
                        "sessionId": current_sid,
                        "event": entry["event"],
                    }
                }

        monkeypatch.setattr(service.client, "frames", native_frames)
        client.portal.call(service._consume, "fixture")
        detail = client.get(f"/api/research/sessions/{sid}").json()
        assert detail["research_quality"]["status"] == status, detail["research_quality"]
        path = service.store.directory(sid) / "outputs/research-report.json"
        raw = path.read_bytes()
        text = raw.decode()
        quote = "存在经营不确定性。"
        start = text.index(quote)
        proofs.append(
            {
                "source_session_id": sid,
                "reference": {"type": "file", "id": "outputs/research-report.json"},
                "sha256": hashlib.sha256(raw).hexdigest(),
                "locator": {
                    "kind": "text",
                    "start": start,
                    "end": start + len(quote),
                    "quote": quote,
                },
            }
        )
        expected[sid] = (status, contract["sha256"], hashlib.sha256(raw).hexdigest())
    for order in [proofs[:1], proofs, list(reversed(proofs))]:
        value = {
            "schema": "asset-research-workspace/v1",
            "subject": "600600.SH",
            "summaries": [
                {
                    "id": "new-summary",
                    "title": "未经评估的改写",
                    "text": "任意改写：保证翻倍且没有风险。",
                    "evidence": order,
                }
            ],
            "relations": [],
        }
        imported = client.post(
            f"/api/research/assets/research/import/{oid}",
            files={
                "file": (
                    "summary.json",
                    json.dumps(value, ensure_ascii=False).encode(),
                    "application/json",
                )
            },
        )
        assert imported.status_code == 201, imported.text
        response = client.post(
            "/api/research/assets/research/preview",
            json={"observation_id": oid, "material": imported.json()["material"]},
        )
        assert response.status_code == 200, response.text
        summary = response.json()["summaries"][0]
        assert summary["quality"] == "not_assessed"
        assert "quality_contract" not in summary
        for proof in summary["evidence"]:
            assert (
                proof["source_quality"],
                proof["source_contract"],
                proof["source_report_sha256"],
            ) == expected[proof["source_session_id"]]
