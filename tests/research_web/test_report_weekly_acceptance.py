"""A synthetic report reaches the original gate without a mocked quality verdict.

SDK transport, refreshed Excel values and completed native events are explicit
fixtures. The private collector, data contract, original report plan, reviewed
sandbox renderer and original Host quality check execute their real code. No
live model, vendor or Office plugin is called.
"""

import asyncio
import copy
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from app.research_web.datahub.providers_wind_api import WindClientAPIProvider
from app.research_web.report_workflows.evidence import prepare_weekly_evidence
from app.research_web.report_workflows.models import ReportWorkflowManifest, WorkflowError
from app.research_web.report_workflows.weekly_data import (
    MAPPING_SHA256,
    assess_weekly_snapshot,
    build_weekly_data_contract,
    load_weekly_mapping,
    materialize_weekly_workbooks,
)
from app.research_web.report_workflows.weekly_quality import (
    POLICY_ID,
    freeze_weekly_production,
)
from app.research_web.research_quality_service import prepare_contract
from app.research_web.resources.research_report_plan import write_business_report_plan
from app.research_web.service import ResearchService
from app.research_web.store import Store


class QuietNative:
    async def rpc(self, method, _payload):
        if method == "subagent.list":
            return {"entries": []}
        if method == "session.list":
            return {"items": []}
        raise AssertionError("offline acceptance must not make a native model request: " + method)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SyntheticSDK:
    """Transport fixture only: the real adapter and collector parse its output."""

    def __init__(self):
        self.calls = []

    def isconnected(self):
        return True

    @staticmethod
    def days(start, end):
        current, last = date.fromisoformat(start), date.fromisoformat(end)
        result = []
        while current <= last:
            if current.weekday() < 5:
                result.append(current)
            current += timedelta(days=1)
        return result

    def tdays(self, start, end, options):
        self.calls.append(("tdays", start, end, options))
        return SimpleNamespace(
            ErrorCode=0,
            Codes=[],
            Fields=["date"],
            Times=[],
            Data=[[day.isoformat() for day in self.days(start, end)]],
        )

    def wsd(self, asset, field, start, end, options):
        self.calls.append(("wsd", asset, field, start, end, options))
        days = self.days(start, end)
        return SimpleNamespace(
            ErrorCode=0,
            Codes=[asset],
            Fields=[field.upper()],
            Times=[datetime.combine(day, datetime.min.time()) for day in days],
            Data=[[300 if field == "amt" else 100 for day in days]],
        )

    def edb(self, asset, start, end, options):
        self.calls.append(("edb", asset, start, end, options))
        days = self.days(start, end)
        return SimpleNamespace(
            ErrorCode=0,
            Codes=[asset],
            Fields=["VALUE"],
            Times=[datetime.combine(day, datetime.min.time()) for day in days],
            Data=[[100 for day in days]],
        )

    def wset(self, dataset, options):
        self.calls.append(("wset", dataset, options))
        parameters = dict(item.split("=", 1) for item in options.split(";"))
        return SimpleNamespace(
            ErrorCode=0,
            Codes=[],
            Fields=["date", "country", "indicator", "importance"],
            Times=[],
            Data=[[parameters["startdate"]], ["合成市场"], ["合成测试事件"], ["重要"]],
        )


@pytest.mark.parametrize("data_source", ["wind_client_api", "wind_excel"])
def test_original_quality_gate_can_finalize_a_fully_bound_weekly_report(
    tmp_path, monkeypatch, data_source
):
    if sys.platform != "darwin":
        pytest.skip("actual native sandbox projection is owned by the Mac acceptance task")
    # Share the explicit, vendor-shaped synthetic fixtures used by the independent
    # data and renderer regressions, rather than introduce a test-only pass flag.
    from test_report_weekly_data import WeeklyDataTests, synthetic_snapshot
    from test_report_weekly_rendering import projection

    cutoff = "2026-10-16T15:30:00+08:00"
    document, render_context, _template_root = projection.__wrapped__(tmp_path / "template")
    # The renderer unit fixture has one series per chart. The production gold
    # and oil charts each hold two distinct series, so preserve that real shape.
    from lxml import etree

    for relation in document.part.rels.values():
        if relation.is_external or str(relation.target_part.partname) not in {
            "/word/charts/chart2.xml",
            "/word/charts/chart3.xml",
        }:
            continue
        chart = etree.fromstring(relation.target_part.blob)
        series = chart.xpath("//*[local-name()='ser']")[0]
        series.addnext(copy.deepcopy(series))
        relation.target_part._blob = etree.tostring(chart)
    document.add_paragraph("{{市场}}")
    assets = tmp_path / "assets"
    (assets / "workbooks").mkdir(parents=True)
    WeeklyDataTests.make_workbooks(assets)
    template = assets / "template.docx"
    document.save(template)
    blocks = [
        *render_context["blocks"],
        {"id": "market", "title": "市场", "kind": "narrative", "required": True},
    ]
    manifest = ReportWorkflowManifest.model_validate(
        {
            "workflow_id": "huaan-etf-weekly",
            "name": "华安ETF周报",
            "version": 1,
            "blocks": blocks,
            "minimum_subagents": 0,
            "providers": [{"provider": "wind_excel", "required": True}],
            "workbook_policies": [
                {
                    "workbook": "workbooks/周报数据.xlsx",
                    "providers": [{"provider": "wind_excel", "required": True}],
                }
            ],
            "weekly_production": {"policy_id": POLICY_ID, "data_source": data_source},
            "delivery": {
                "formats": ["html", "docx", "xlsx"],
                "primary_workbook": "workbooks/周报数据.xlsx",
            },
        }
    )
    service = ResearchService(QuietNative(), Store(tmp_path / "product"))
    service.report_owner_authorizer = lambda: {"id": "owner", "role": "admin", "enabled": True}
    catalog = service.report_workflows.catalog
    catalog.create_draft(manifest)
    catalog.upload_resource(manifest.workflow_id, "templates/template.docx", template.read_bytes())
    mapping = load_weekly_mapping()
    source_contract = {
        "schema_version": 1,
        "mapping_sha256": MAPPING_SHA256,
        "verification": {
            "status": "reviewed",
            "evidence_sha256": _sha(b"explicit synthetic source contract"),
        },
        "calendars": {
            market: {
                "semantics_verified": True,
                "wind_calendar": f"SYNTHETIC{index}",
                "timezone": spec["timezone"],
                "close_time": "00:00",
                "session_overrides": {},
            }
            for index, (market, spec) in enumerate(mapping["calendars"].items())
        },
        "economic_calendar": {
            "method": "wset",
            "semantics_verified": True,
            "dataset": "synthetic_calendar",
            "start_parameter": "startdate",
            "end_parameter": "enddate",
            "fields": {name: name for name in ("date", "country", "indicator", "importance")},
            "static_options": {},
        },
    }
    if data_source == "wind_excel":
        from test_datahub_wind_excel_weekly import package

        input_root = tmp_path / "excel-inputs"
        _, source_contract, input_manifest, _ = package(input_root, cutoff)
        # Keep the existing catalog resource roots in the full published fixture.
        paths = {
            item["path"]: item["path"].replace("inputs/", "assets/weekly/")
            for item in input_manifest["resources"]
        }
        coverage = json.loads((input_root / "inputs/coverage.json").read_bytes())
        for window in coverage["windows"]:
            window["resource"] = paths[window["resource"]]
        coverage_raw = json.dumps(coverage).encode()
        source_contract["verification"]["evidence_path"] = paths[
            source_contract["verification"]["evidence_path"]
        ]
        for export in source_contract["excel_exports"].values():
            export["path"] = paths[export["path"]]
        economic = source_contract["excel_exports"]["economic_calendar"]
        economic["coverage_evidence_path"] = paths[economic["coverage_evidence_path"]]
        economic["coverage_evidence_sha256"] = _sha(coverage_raw)
        observation = json.loads((input_root / economic["observation_path"]).read_bytes())
        observation["export_path"] = economic["path"]
        observation_raw = json.dumps(observation).encode()
        economic["observation_path"] = paths[economic["observation_path"]]
        economic["observation_sha256"] = _sha(observation_raw)
        for item in input_manifest["resources"]:
            if item["path"] != "mappings/huaan-weekly-source-contract.json":
                catalog.upload_resource(
                    manifest.workflow_id,
                    paths[item["path"]],
                    (
                        coverage_raw
                        if item["path"] == "inputs/coverage.json"
                        else (
                            observation_raw
                            if item["path"] == "inputs/calendar-observation.json"
                            else (input_root / item["path"]).read_bytes()
                        )
                    ),
                )
    catalog.upload_resource(
        manifest.workflow_id,
        "mappings/huaan-weekly-source-contract.json",
        json.dumps(source_contract).encode(),
    )
    for book in (assets / "workbooks").glob("*.xlsx"):
        catalog.upload_resource(manifest.workflow_id, "workbooks/" + book.name, book.read_bytes())
    catalog.create_version(manifest.workflow_id)
    catalog.publish_version(manifest.workflow_id, 1)
    manifest = catalog.manifest(manifest.workflow_id, 1)
    workspace = catalog.create_run_workspace(manifest.workflow_id, 1)
    run_id = workspace["run_id"]
    run_root = catalog.run_path(run_id)
    data_contract = build_weekly_data_contract(cutoff)
    snapshot = synthetic_snapshot(data_contract)
    assert assess_weekly_snapshot(snapshot, data_contract)["status"] == "passed"
    (run_root / "snapshots").mkdir()
    raw = json.dumps(snapshot, ensure_ascii=False, indent=2).encode()
    (run_root / "snapshots" / "report-data.json").write_bytes(raw)
    projected_books = materialize_weekly_workbooks(snapshot, run_root, manifest)
    session = service.store.create("claw", "离线周报验收")
    sid = session["id"]
    session["created"] = True
    session["report_workflow"] = {
        "workflow_id": manifest.workflow_id,
        "version": 1,
        "run_id": run_id,
    }
    if data_source == "wind_excel":
        session["report_workflow"].update(weekly_data_source=data_source, owner_id="owner")
        service.report_workflows.runtime._update_run(
            run_id,
            id=run_id,
            workflow_id=manifest.workflow_id,
            version=1,
            weekly_data_source=data_source,
            owner_id="owner",
            session_id=sid,
        )
        with catalog._exclusive():
            catalog._row(manifest.workflow_id)["status"] = "enabled"
            catalog._save()
    refresh_root = run_root / "refresh-manifests"
    refresh_root.mkdir()
    calibration_calls = []

    async def prepare_excel():
        from app.research_web.report_workflows.weekly_sources import freeze_weekly_workbook_dates

        calibration_calls.append(data_contract["cutoff"])
        # These are explicit post-refresh Excel fixture values. The collector
        # independently opens and compares the actual files, not a pass boolean.
        freeze_weekly_workbook_dates(run_root, manifest, data_contract)
        for name in ("周报数据.xlsx", "周报图表.xlsx"):
            relative = "workbooks/" + name
            refresh = {
                "status": "ready",
                "provider": "wind_excel",
                "workbook": relative,
                "output_sha256": _sha((run_root / relative).read_bytes()),
            }
            (refresh_root / (_sha(relative.encode()) + ".json")).write_text(json.dumps(refresh))

    service.datahub.connections.statuses = lambda: {
        "wind": {
            "configured": True,
            "preferred_adapter": "client_api",
            "credential_store_available": True,
        }
    }
    service.datahub.source_configuration_digest = lambda _source: "a" * 64
    sdk = SyntheticSDK()
    provider = WindClientAPIProvider(
        sdk_factory=lambda: sdk,
        calendar_contracts=source_contract["calendars"],
        economic_contract=source_contract["economic_calendar"],
    )
    if data_source == "wind_excel":
        from test_datahub_wind_excel_weekly import Client

        from app.research_web.datahub import providers_wind_excel_weekly
        from app.research_web.datahub.providers_wind_excel_weekly import WindExcelWeeklyProvider

        monkeypatch.setattr(
            providers_wind_excel_weekly,
            "_host_now",
            lambda: datetime.fromisoformat(cutoff) + timedelta(minutes=30),
        )

        provider = WindExcelWeeklyProvider(
            run_root=run_root,
            manifest=manifest,
            source_contract=source_contract,
            client_factory=Client,
        )
    collected = asyncio.run(
        service.datahub.collect_report_weekly(
            sid,
            "full-acceptance-sdk",
            data_contract["cutoff"],
            provider=provider,
            run_root=run_root,
            manifest=manifest,
            prepare_excel=prepare_excel,
        )
    )
    assert collected["assessment"]["status"] == "passed", collected["snapshot"].get("limitations")
    if data_source == "wind_client_api":
        assert calibration_calls == [data_contract["cutoff"]]
        assert any(call[0] == "edb" for call in sdk.calls) and any(
            call[0] == "wsd" for call in sdk.calls
        )
    else:
        assert calibration_calls == [] and sdk.calls == []
        assert collected["snapshot"]["source"] == "wind_excel"
    snapshot = collected["snapshot"]
    raw = json.dumps(snapshot, ensure_ascii=False, indent=2).encode()
    (run_root / "snapshots" / "report-data.json").write_bytes(raw)
    projected_books = materialize_weekly_workbooks(snapshot, run_root, manifest)
    session["report_workflow"]["quality_policy"] = POLICY_ID
    frozen = freeze_weekly_production(manifest, data_contract)
    context = {
        "workflow_id": manifest.workflow_id,
        "version": 1,
        "run_id": run_id,
        "name": manifest.name,
        "blocks": blocks,
        "minimum_subagents": 0,
        "primary_workbook": manifest.delivery.primary_workbook,
        "dataset_snapshot": "snapshots/report-data.json",
        "dataset_snapshot_sha256": _sha(raw),
        "weekly_production": frozen,
        "workbook_projection": projected_books,
        "template_resources": [
            {"path": item.path, "sha256": item.sha256}
            for item in manifest.resources
            if item.path.startswith("templates/")
        ],
    }
    target = service.store.directory(sid) / "inputs" / "report-workflow"
    shutil.copytree(run_root, target)
    context_raw = json.dumps(context, ensure_ascii=False).encode()
    (target / "run-context.json").write_bytes(context_raw)
    runtime = service.report_workflows.runtime
    runtime._update_run(
        run_id,
        id=run_id,
        workflow_id=manifest.workflow_id,
        version=1,
        session_id=sid,
        owner_id="owner",
        trigger="manual",
        status="running",
        weekly_data_contract=data_contract,
        weekly_production=frozen,
        weekly_context_sha256=_sha(context_raw),
        dataset_snapshot_sha256=_sha(raw),
        refresh_manifests=[],
        subagents=[],
    )
    prepare_weekly_evidence(service, sid)
    key = "synthetic-weekly-acceptance"
    delivery = service.delivery.begin(sid, key, ["html", "docx", "xlsx"])
    assert service.store.reserve(sid, key, "synthetic", delivery)
    receipt = service.store.receipt(sid, key)
    contract = prepare_contract(
        service,
        sid,
        receipt,
        "核查周报事实，只生成HTML和DOCX。",
        [block["title"] for block in blocks],
        data_contract["cutoff"][:10],
        "deep",
    )
    service.store.receipt(sid, key, "accepted")
    evidence = json.loads(
        (service.store.directory(sid) / "resources" / "research_evidence.json").read_text()
    )
    observed = evidence["observations"]
    closes = [
        row
        for row in observed
        if row.get("metric") == "weekly_close" and row.get("heading") == "沪深300"
    ]
    closes.sort(key=lambda row: row["period"], reverse=True)
    assert len(closes) == 2
    histories = [row for row in observed if row.get("metric") == "weekly_history_count"]
    industry = next(
        row
        for row in observed
        if row.get("kind") == "business_quote" and "行业" in row.get("heading", "")
    )
    calendar = next(
        row
        for row in observed
        if row.get("kind") == "business_quote" and "日历" in row.get("heading", "")
    )
    recipes = [
        {
            "id": "market_return",
            "operation": "percent_change",
            "operands": [closes[0]["id"], closes[1]["id"]],
            "decimal_places": 4,
        }
    ]
    selections = [
        [industry["id"]],
        [histories[0]["id"]],
        [histories[-1]["id"]],
        [calendar["id"]],
        ["$market_return"],
    ]
    neutral_headings = ["行业图", "黄金图", "原油图", "经济日历", "市场"]
    plan = {
        "title": "华安ETF周报",
        "missing": [],
        "calculations": recipes,
        "sections": [
            {
                "id": block["id"],
                "heading": heading,
                "evidence_ids": ids,
                "requirement_ids": [contract["requirements"][index]["id"]],
            }
            for index, (block, heading, ids) in enumerate(
                zip(blocks, neutral_headings, selections, strict=True)
            )
        ],
    }
    report_context = {
        "task_id": contract["task_id"],
        "contract_sha256": contract["sha256"],
        "as_of": contract["as_of"],
        "requirement_ids": [row["id"] for row in contract["requirements"]],
        "formats": ["html", "docx"],
    }
    with monkeypatch.context() as scoped:
        scoped.chdir(service.store.directory(sid))
        write_business_report_plan(report_context, plan)
    entries = [
        {"event": {"seq": 1, "type": "user/message", "data": {"content": delivery["marker"]}}},
        {"event": {"seq": 2, "type": "turn/end", "data": {}}},
    ]
    service.connected = {"mux", "host"}
    service.loaded.add(sid)
    service.running[sid] = False
    service.events[sid] = {row["event"]["seq"]: row for row in entries}
    asyncio.run(asyncio.wait_for(runtime._wait_for_delivery(run_id), timeout=45))
    run = runtime._run(run_id)
    assert run["quality_status"] == "passed", run
    assert run["delivery_status"] == "complete", run
    assert run["finalization_status"] == "finalized", run
    assert run["finalization_binding"]["archive"]["quality_status"] == "passed"
    assert catalog._row(manifest.workflow_id)["last_finalized_run"] == run_id
    canonical = json.loads(
        (service.store.directory(sid) / "outputs" / "research-report.json").read_text()
    )
    assert run["finalization_binding"]["canonical_sha256"] == _sha(
        (service.store.directory(sid) / "outputs" / "research-report.json").read_bytes()
    )
    assert canonical["business_calculations"] == recipes
    with ZipFile(service.store.directory(sid) / "outputs" / "report.docx") as package:
        assert (
            len(
                [
                    name
                    for name in package.namelist()
                    if name.startswith("word/charts/chart") and name.endswith(".xml")
                ]
            )
            == 3
        )
        assert "OLD" not in package.read("word/document.xml").decode()
    assert runtime.public_run(run)["finalization_status"] == "finalized"
    if data_source == "wind_excel":
        from app.research_web.report_workflows.evidence import FACTS_PATH
        from app.research_web.report_workflows.weekly_quality import weekly_verified_evidence

        assert "实际采集开始" in (service.store.directory(sid) / FACTS_PATH).read_text()
        assert "实际冻结" in (service.store.directory(sid) / FACTS_PATH).read_text()
        snapshot_path = target / "snapshots" / "report-data.json"
        original_snapshot = snapshot_path.read_bytes()
        changed_snapshot = json.loads(original_snapshot)
        changed_snapshot["frozen_at"] = "2026-10-16T16:00:01+08:00"
        snapshot_path.write_text(json.dumps(changed_snapshot))
        with pytest.raises(WorkflowError):
            weekly_verified_evidence(service, sid)
        snapshot_path.write_bytes(original_snapshot)
    (service.store.directory(sid) / "outputs" / "report.docx").write_bytes(b"changed")
    assert runtime.public_run(run)["finalization_status"] == "invalidated"
    assert (
        catalog._row(manifest.workflow_id)["last_finalized"]["binding"]["archive"]["quality_status"]
        == "passed"
    )
