"""Offline historical acceptance keeps formal acquisition and file gates separate."""

import asyncio
from datetime import datetime

import pytest
from test_datahub_wind_excel_weekly import Client, package
from test_report_workflow_integration import isolated_keyring

from app.research_web.datahub import providers_wind_excel_weekly as excel_provider
from app.research_web.datahub.providers_wind_excel_weekly import WindExcelWeeklyProvider
from app.research_web.report_workflows.weekly_data import assess_weekly_snapshot

__all__ = ["isolated_keyring"]


def test_explicit_historical_provider_rechecks_without_formal_eligibility(tmp_path, monkeypatch):
    contract, source, manifest, _ = package(tmp_path)
    monkeypatch.setattr(
        excel_provider, "_host_now", lambda: datetime.fromisoformat("2026-10-17T16:00:00+08:00")
    )
    client = Client()
    result = asyncio.run(
        WindExcelWeeklyProvider(
            run_root=tmp_path,
            manifest=manifest,
            source_contract=source,
            client_factory=lambda: client,
            execution_purpose="historical_acceptance",
        ).collect(contract)
    )
    assert client.calls
    assert result["snapshot"]["acquisition_kind"] == "historical_recheck"
    assert result["assessment"]["status"] == "passed", result["assessment"]["issues"]
    ordinary = assess_weekly_snapshot(
        result["snapshot"],
        contract,
        require_excel_acquisition=True,
        run_root=tmp_path,
        manifest=manifest,
    )
    assert ordinary["status"] == "blocked_data"
    assert "weekly_excel_historical_recheck_not_formal" in ordinary["issues"]


def test_historical_failure_is_not_hidden_by_missing_economic_replay(tmp_path, monkeypatch):
    contract, source, manifest, _ = package(tmp_path)
    monkeypatch.setattr(
        excel_provider, "_host_now", lambda: datetime.fromisoformat("2026-10-17T16:00:00+08:00")
    )
    result = asyncio.run(
        WindExcelWeeklyProvider(
            run_root=tmp_path, manifest=manifest, source_contract=source, client_factory=Client
        ).collect(contract)
    )
    assessed = assess_weekly_snapshot(
        result["snapshot"],
        contract,
        require_excel_acquisition=True,
        run_root=tmp_path,
        manifest=manifest,
    )
    assert assessed["issues"][0] == "weekly_excel_historical_recheck_not_formal"


def test_historical_runtime_deduplicates_and_preserves_unknown_submission(tmp_path, monkeypatch):
    from test_report_weekly_quality import _runtime_fixture

    runtime, _owner, sent = _runtime_fixture(
        tmp_path, monkeypatch, data_source="wind_excel", unknown_send=True
    )

    async def check():
        first = await runtime.start_run(
            "huaan-etf-weekly", execution_purpose="historical_acceptance"
        )
        await runtime.tasks[first["id"]]
        run = runtime._run(first["id"])
        assert run["status"] == "needs_attention", run
        assert run["execution_purpose"] == "historical_acceptance"
        assert run["weekly_production"]["execution_purpose"] == "historical_acceptance"
        repeated = await runtime.start_run(
            "huaan-etf-weekly", execution_purpose="historical_acceptance"
        )
        retried = await runtime.retry(first["id"])
        assert first["id"] == repeated["id"] == retried["id"]
        assert retried["session_id"] == run["session_id"]
        assert retried["execution_purpose"] == "historical_acceptance"
        formal = await runtime.start_run("huaan-etf-weekly")
        assert formal["id"] != first["id"]
        assert formal["execution_purpose"] == "formal"
        assert formal["status"] == "skipped_overlap"
        with pytest.raises(Exception) as error:
            runtime._finish_run(first["id"], {"finalization_status": "finalized"})
        assert error.value.code == "weekly_historical_not_formal"

    asyncio.run(check())
    assert len(sent) == 1


def test_historical_runtime_rejects_api_policy_before_workspace_or_model(tmp_path, monkeypatch):
    from test_report_weekly_quality import _runtime_fixture

    runtime, _owner, sent = _runtime_fixture(tmp_path, monkeypatch)
    with pytest.raises(Exception) as error:
        asyncio.run(
            runtime.start_run("huaan-etf-weekly", execution_purpose="historical_acceptance")
        )
    assert error.value.code == "weekly_historical_policy_invalid"
    assert runtime.catalog.data["runs"] == {} and sent == []


def test_historical_revocation_after_passed_collection_cannot_send(tmp_path, monkeypatch):
    from test_report_weekly_quality import _runtime_fixture

    runtime, owner, sent = _runtime_fixture(
        tmp_path, monkeypatch, data_source="wind_excel", revoke_during_collection=True
    )

    async def check():
        first = await runtime.start_run(
            "huaan-etf-weekly", execution_purpose="historical_acceptance"
        )
        await runtime.tasks[first["id"]]
        run = runtime._run(first["id"])
        assert run["failure_code"] == "weekly_owner_denied", run
        assert run["execution_purpose"] == "historical_acceptance"
        assert not owner["enabled"]

    asyncio.run(check())
    assert sent == []


@pytest.mark.parametrize("changed", ["run", "session", "frozen"])
def test_purpose_tampering_never_authenticates_context(tmp_path, changed):
    from test_report_weekly_quality import _service

    from app.research_web.report_workflows.weekly_quality import trusted_weekly_context

    service, run, _context = _service(tmp_path)
    if changed == "run":
        run["execution_purpose"] = "historical_acceptance"
    elif changed == "session":
        service.store.session("s")["report_workflow"]["execution_purpose"] = "historical_acceptance"
    else:
        run["weekly_production"]["execution_purpose"] = "historical_acceptance"
    with pytest.raises(Exception) as error:
        trusted_weekly_context(service, "s")
    assert error.value.code == "weekly_context_invalid"


def _historical_html(label, *, banner=None, style=None):
    from app.research_web.report_render_script import REPORT_HTML_STYLE

    style = REPORT_HTML_STYLE if style is None else style
    banner = (
        f'<aside data-host-historical-acceptance="true">{label}</aside>'
        if banner is None
        else banner
    )
    return f'<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>test</title><style>{style}</style></head><body>{banner}</body></html>'.encode()


def test_model_text_is_not_a_host_historical_banner():
    from app.research_web.report_workflows.weekly_quality import _verify_historical_notice

    label = "历史验收稿（不得作为正式定稿）"
    with pytest.raises(Exception) as error:
        _verify_historical_notice("report.html", f"<body><p>{label}</p></body>".encode(), label)
    assert error.value.code == "weekly_historical_label_missing"
    _verify_historical_notice(
        "report.html",
        _historical_html(label),
        label,
    )


@pytest.mark.parametrize("revoke", [False, True])
def test_historical_startup_only_observes_accepted_work_and_rechecks_owner(
    tmp_path, monkeypatch, revoke
):
    import asyncio

    from test_report_weekly_quality import _runtime_fixture

    from app.research_web.report_workflows.catalog import ReportWorkflowService
    from app.research_web.report_workflows.runtime import ReportWorkflowRuntime

    runtime, owner, sent = _runtime_fixture(
        tmp_path, monkeypatch, data_source="wind_excel", native_accept=True
    )
    original_save = runtime.catalog._save
    failed = []

    def save():
        if not failed and any(
            row.get("research_started_at") for row in runtime.catalog.data["runs"].values()
        ):
            failed.append(True)
            raise OSError("crash after accepted RPC")
        return original_save()

    monkeypatch.setattr(runtime.catalog, "_save", save)
    monitored = []

    async def check():
        first = await runtime.start_run(
            "huaan-etf-weekly", execution_purpose="historical_acceptance"
        )
        await runtime.tasks[first["id"]]
        assert runtime._run(first["id"])["status"] == "needs_attention"
        owner["enabled"] = not revoke
        recovered = ReportWorkflowRuntime(
            runtime.service, ReportWorkflowService(runtime.catalog.root.parent), None
        )
        runtime.service.report_workflows.runtime = recovered

        async def observe(run_id):
            monitored.append(run_id)

        monkeypatch.setattr(recovered, "_resume_delivery", observe)
        await recovered.start()
        await asyncio.gather(*list(recovered.tasks.values()))
        await recovered.close()
        row = recovered._run(first["id"])
        assert row["execution_purpose"] == "historical_acceptance"
        assert row["weekly_production"]["execution_purpose"] == "historical_acceptance"
        assert monitored == ([] if revoke else [first["id"]])
        if revoke:
            assert row["failure_code"] == "weekly_owner_denied"

    asyncio.run(check())
    assert len(sent) == 1


def test_historical_api_is_explicit_and_ordinary_body_cannot_select_mode(tmp_path):
    from fastapi.testclient import TestClient
    from test_report_workflow_integration import NativeFixture

    from app.research_web.main import create_app
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    service = ResearchService(NativeFixture(), Store(tmp_path / "state"))
    calls = []

    async def start(workflow_id, **kwargs):
        calls.append((workflow_id, kwargs))
        return {"status": "queued"}

    service.report_workflows.runtime.start_run = start
    with TestClient(create_app(service)) as client:
        assert (
            client.post(
                "/api/research/report-workflows/huaan-etf-weekly/runs",
                json={"execution_purpose": "historical_acceptance"},
            ).status_code
            == 202
        )
        assert calls[-1] == ("huaan-etf-weekly", {})
        assert (
            client.post(
                "/api/research/report-workflows/huaan-etf-weekly/historical-acceptance-runs",
                json={"execution_purpose": "formal"},
            ).status_code
            == 202
        )
        assert calls[-1] == ("huaan-etf-weekly", {"execution_purpose": "historical_acceptance"})


@pytest.mark.parametrize(
    "variant",
    ["comment", "hidden", "display", "visibility", "opacity", "css", "removed", "changed"],
)
def test_historical_html_requires_a_visible_body_banner(variant):
    from app.research_web.report_workflows.weekly_quality import _verify_historical_notice

    label = "历史验收稿（不得作为正式定稿）"
    aside = f'<aside data-host-historical-acceptance="true">{label}</aside>'
    banner = {
        "comment": f"<!--{aside}-->",
        "hidden": aside.replace("<aside ", "<aside hidden "),
        "display": aside.replace("<aside ", '<aside style="display:none" '),
        "visibility": aside.replace("<aside ", '<aside style="visibility:hidden" '),
        "opacity": aside.replace("<aside ", '<aside style="opacity:0" '),
        "css": aside,
        "removed": "",
        "changed": aside.replace(label, "普通报告"),
    }[variant]
    with pytest.raises(Exception) as error:
        _verify_historical_notice(
            "report.html",
            _historical_html(
                label, banner=banner, style="aside { display:none }" if variant == "css" else None
            ),
            label,
        )
    assert error.value.code == "weekly_historical_label_missing"


@pytest.mark.parametrize("variant", ["vanish", "deleted", "removed", "changed"])
def test_historical_word_requires_a_visible_main_document_run(variant):
    from io import BytesIO

    from docx import Document
    from docx.oxml import OxmlElement
    from docx.shared import Pt, RGBColor

    from app.research_web.report_workflows.weekly_quality import _verify_historical_notice

    label = "历史验收稿（不得作为正式定稿）"
    document = Document()
    paragraph = document.add_paragraph(label)
    run = paragraph.runs[0]
    run.bold = True
    run.font.hidden = False
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0, 0, 0)
    valid = BytesIO()
    document.save(valid)
    _verify_historical_notice("report.docx", valid.getvalue(), label)
    if variant == "vanish":
        run.font.hidden = True
    elif variant == "deleted":
        paragraph._p.remove(run._r)
        deleted = OxmlElement("w:del")
        deleted.append(run._r)
        paragraph._p.append(deleted)
    elif variant == "removed":
        paragraph._p.remove(run._r)
    else:
        run.text = "普通报告"
    invalid = BytesIO()
    document.save(invalid)
    with pytest.raises(Exception) as error:
        _verify_historical_notice("report.docx", invalid.getvalue(), label)
    assert error.value.code == "weekly_historical_label_missing"


def test_public_historical_run_cannot_claim_finalized(tmp_path, monkeypatch):
    from test_report_weekly_quality import _runtime_fixture

    from app.research_web.report_workflows import weekly_quality

    runtime, _owner, _sent = _runtime_fixture(tmp_path, monkeypatch)
    binding = {
        "task_id": "task",
        "contract_sha256": "contract",
        "canonical_sha256": "canonical",
        "snapshot_sha256": "snapshot",
        "artifacts": [],
    }
    monkeypatch.setattr(weekly_quality, "historical_acceptance_binding", lambda *_args: binding)
    row = runtime.public_run(
        {
            "execution_purpose": "historical_acceptance",
            "finalization_status": "finalized",
            "quality_status": "passed",
            "session_id": "session",
            "finalization_binding": binding,
        }
    )
    assert row["finalization_status"] == "invalidated"
    assert row["quality_status"] == "invalid"


def test_historical_binding_names_acceptance_without_formal_timestamp(monkeypatch):
    from app.research_web.report_workflows import weekly_quality

    monkeypatch.setattr(
        weekly_quality,
        "trusted_weekly_context",
        lambda *_args: {"execution_purpose": "historical_acceptance"},
    )
    monkeypatch.setattr(
        weekly_quality, "_delivery_binding", lambda *_args: {"finalized_at": 123, "artifacts": []}
    )
    binding = weekly_quality.historical_acceptance_binding(None, "session")
    assert "finalized_at" not in binding
    assert binding["historical_accepted_at"] == 123
    assert binding["execution_purpose"] == "historical_acceptance"


@pytest.mark.parametrize(
    "variant",
    ["scale", "transparent", "decimal_zero", "external_css", "inline_style", "missing_style"],
)
def test_historical_html_rejects_every_deviation_from_renderer_styles(variant):
    from app.research_web.report_workflows.weekly_quality import _verify_historical_notice

    label = "历史验收稿（不得作为正式定稿）"
    from app.research_web.report_render_script import REPORT_HTML_STYLE

    css = {
        "scale": "aside{transform:scale(0)}",
        "transparent": "aside{color:transparent}",
        "decimal_zero": "aside{font-size:0.0px}",
    }.get(variant, "")
    raw = _historical_html(label, style=REPORT_HTML_STYLE + css)
    if variant == "external_css":
        raw = raw.replace(
            b"</head>", b'<link rel="stylesheet" href="https://example.invalid/hide.css"></head>'
        )
    elif variant == "inline_style":
        raw = raw.replace(b"<body>", b'<body style="transform:scale(0)">')
    elif variant == "missing_style":
        raw = raw.replace(("<style>" + REPORT_HTML_STYLE + "</style>").encode(), b"")
    with pytest.raises(Exception) as error:
        _verify_historical_notice("report.html", raw, label)
    assert error.value.code == "weekly_historical_label_missing"
