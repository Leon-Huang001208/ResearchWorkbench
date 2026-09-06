"""Report Workflow package and Excel refresh contract regressions."""

from __future__ import annotations

import importlib
import json
import threading
import time
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research_web.report_workflows import (
    DeliveryContract,
    ReportBlock,
    ReportWorkflowManifest,
    ReportWorkflowService,
    WorkbookFormulaProvider,
    WorkbookProviderRequirement,
    WorkbookRefreshPolicy,
    WorkbookRefreshService,
    WorkflowError,
    WorkflowSchedule,
    scan_workbook_formulas,
)
from app.research_web.report_workflows.workbook import WindExcelProvider


def _xlsx(cells: dict[str, tuple[str | None, object | None]]) -> bytes:
    rows = []
    for ref, (formula, value) in cells.items():
        attributes = ' t="str"' if isinstance(value, str) else ""
        formula_xml = f"<f>{formula}</f>" if formula is not None else ""
        value_xml = "" if value is None else f"<v>{value}</v>"
        rows.append(f'<c r="{ref}"{attributes}>{formula_xml}{value_xml}</c>')
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" '
            'r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships"><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheetData><row r="1">'
            + "".join(rows)
            + "</row></sheetData></worksheet>",
        )
    return stream.getvalue()


def _manifest(*requirements: WorkbookProviderRequirement) -> ReportWorkflowManifest:
    return ReportWorkflowManifest(
        workflow_id="weekly-fund",
        name="基金周报",
        version=1,
        providers=list(requirements),
        workbook_policies=[
            WorkbookRefreshPolicy(
                workbook="workbooks/model.xlsx",
                providers=list(requirements),
                required_cells=["Sheet1!A1"],
            )
        ],
        blocks=[ReportBlock(id="summary", title="摘要", kind="narrative")],
        delivery=DeliveryContract(formats=["xlsx", "html"]),
        schedule=WorkflowSchedule(),
    )


def test_models_forbid_unknown_enums_and_extra_fields():
    with pytest.raises(ValidationError):
        ReportBlock(id="summary", title="摘要", kind="unknown")
    with pytest.raises(ValidationError):
        DeliveryContract(formats=["exe"])
    with pytest.raises(ValidationError):
        WorkflowSchedule(kind="cron")
    with pytest.raises(ValidationError):
        WorkbookRefreshPolicy(workbook="workbooks/a.xlsx", unexpected=True)


def test_version_package_is_immutable_hashed_and_copied_to_isolated_run(tmp_path: Path):
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest())
    raw = _xlsx({"A1": (None, "ready")})
    uploaded = service.upload_resource("weekly-fund", "workbooks/model.xlsx", raw)
    assert uploaded.sha256

    version = service.create_version("weekly-fund")
    package = tmp_path / "report-workflows/weekly-fund/versions/1"
    assert {item.name for item in package.iterdir()} == {
        "manifest.yaml",
        "workflow.yaml",
        "templates",
        "workbooks",
        "assets",
        "mappings",
        "validation.yaml",
    }
    assert service.preflight("weekly-fund", 1)["status"] == "ready"
    service.publish_version("weekly-fund", 1)

    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "changed")})
    )
    assert (package / "workbooks/model.xlsx").read_bytes() == raw
    with pytest.raises(WorkflowError, match="不可变"):
        service.upload_resource("weekly-fund", "versions/1/workbooks/model.xlsx", raw)

    run = service.create_run_workspace("weekly-fund", 1)
    copied = Path(run["path"])
    assert copied != package
    assert (copied / "workbooks/model.xlsx").read_bytes() == raw
    assert version.resources
    assert service.list_resources("weekly-fund", 1)[0].sha256


def test_resource_paths_reject_traversal_and_symlink(tmp_path: Path):
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest())
    with pytest.raises(WorkflowError):
        service.upload_resource("weekly-fund", "../outside.xlsx", b"bad")
    (service.root / "weekly-fund" / "draft" / "assets").rmdir()
    (service.root / "weekly-fund" / "draft" / "assets").symlink_to(tmp_path)
    with pytest.raises(WorkflowError):
        service.upload_resource("weekly-fund", "assets/escape.txt", b"bad")


@pytest.mark.parametrize(
    ("formulas", "expected"),
    [
        (["WSD(\"600000.SH\",\"close\")"], WorkbookFormulaProvider.WIND),
        (["THS_HQ(\"600000.SH\",\"close\")"], WorkbookFormulaProvider.IFIND),
        (
            ["WSS(\"600000.SH\",\"sec_name\")", "THS_BD(\"600000.SH\")"],
            WorkbookFormulaProvider.MIXED,
        ),
        (["SUM(1,2)"], WorkbookFormulaProvider.NONE),
    ],
)
def test_excel_formula_provider_detection(tmp_path: Path, formulas, expected):
    workbook = tmp_path / "formula.xlsx"
    workbook.write_bytes(
        _xlsx({f"A{index}": (formula, 1) for index, formula in enumerate(formulas, 1)})
    )
    assert scan_workbook_formulas(workbook).provider is expected


def test_preflight_requires_declared_providers_for_mixed_workbook(tmp_path: Path):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    service.upload_resource(
        "weekly-fund",
        "workbooks/model.xlsx",
        _xlsx({"A1": ("WSD(\"x\")", 1), "B1": ("THS_HQ(\"x\")", 1)}),
    )
    service.create_version("weekly-fund")
    result = service.preflight("weekly-fund", 1)
    assert result["status"] == "blocked_data"
    assert result["code"] == "provider_declaration_missing"
    assert result["missing_providers"] == ["ifind_excel"]
    with pytest.raises(WorkflowError, match="预检"):
        service.create_run_workspace("weekly-fund", 1)


def test_preflight_blocks_external_formula_workbook_without_refresh_policy(tmp_path: Path):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": ("WSD(\"x\")", 1)})
    )
    service.upload_resource(
        "weekly-fund", "workbooks/undeclared.xlsx", _xlsx({"A1": ("WSD(\"y\")", 2)})
    )
    service.create_version("weekly-fund")

    result = service.preflight("weekly-fund", 1)

    assert result == {
        "status": "blocked_data",
        "code": "refresh_policy_missing",
        "path": "workbooks/undeclared.xlsx",
    }
    with pytest.raises(WorkflowError) as error:
        service.publish_version("weekly-fund", 1)
    assert error.value.code == "refresh_policy_missing"


class FakeProvider:
    def __init__(self, provider_id="wind_excel", ready=True, values=None, replacement=None):
        self.provider_id = provider_id
        self.ready = ready
        self.values = values or {"Sheet1!A1": "ready"}
        self.replacement = replacement
        self.calls = []

    def readiness(self):
        return {"ready": self.ready, "code": None if self.ready else "plugin_not_ready"}

    def open_workbook(self, path):
        self.calls.append("open")
        return path

    def refresh_all(self, handle):
        self.calls.append("refresh")

    def calculate_full(self, handle):
        self.calls.append("calculate")

    def read_cells(self, handle, references):
        self.calls.append("read")
        return {reference: self.values.get(reference) for reference in references}

    def save(self, handle):
        self.calls.append("save")
        if self.replacement is not None:
            Path(handle).write_bytes(self.replacement)

    def close(self, handle):
        self.calls.append("close")


def test_xlwings_missing_is_safe_and_does_not_expose_import_message(monkeypatch):
    real_import = importlib.import_module

    def missing(name, *args, **kwargs):
        if name == "xlwings":
            raise ModuleNotFoundError("secret path and plugin details")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", missing)
    result = WindExcelProvider().readiness()
    assert result == {"ready": False, "code": "xlwings_missing"}
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    ("cells", "policy", "code"),
    [
        (
            {"A1": (None, None)},
            WorkbookRefreshPolicy(
                workbook="workbooks/model.xlsx", required_cells=["Sheet1!A1"]
            ),
            "required_cell_empty",
        ),
        (
            {"A1": (None, "2026-09-05")},
            WorkbookRefreshPolicy(
                workbook="workbooks/model.xlsx",
                required_date_cell="Sheet1!A1",
                required_date=date(2026, 9, 6),
            ),
            "required_date_stale",
        ),
        (
            {"A1": ("1/0", "#DIV/0!")},
            WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
            "formula_error",
        ),
        (
            {"A1": (None, 0)},
            WorkbookRefreshPolicy(
                workbook="workbooks/model.xlsx", reject_zero_cells=["Sheet1!A1"]
            ),
            "unexpected_zero",
        ),
    ],
)
def test_refresh_blocks_invalid_cached_data(tmp_path: Path, cells, policy, code):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx(cells))
    result = WorkbookRefreshService().refresh(source, tmp_path / "run", policy)
    assert result.status == "blocked_data"
    assert result.code == code
    assert result.resource is None
    assert result.manifest_path is None


def test_refresh_order_manifest_and_global_excel_lock(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    refreshed = _xlsx({"A1": ("WSD(\"x\")", "ready")})
    source.write_bytes(_xlsx({"A1": ("WSD(\"x\")", "old")}))

    active = 0
    peak = 0
    guard = threading.Lock()

    class LockedProvider(FakeProvider):
        def refresh_all(self, handle):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with guard:
                active -= 1
            super().refresh_all(handle)

    provider = LockedProvider(replacement=refreshed)
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        required_cells=["Sheet1!A1"],
        poll_interval_seconds=0,
    )
    service = WorkbookRefreshService(providers={"wind_excel": provider})
    results = []
    threads = [
        threading.Thread(
            target=lambda index=i: results.append(
                service.refresh(source, tmp_path / f"run-{index}", policy)
            )
        )
        for i in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == 1
    assert all(result.status == "ready" for result in results)
    assert provider.calls[:6] == ["open", "refresh", "calculate", "read", "read", "save"]
    for result in results:
        manifest = json.loads(Path(result.manifest_path).read_text())
        assert manifest["output_sha256"] == result.resource.sha256


def test_run_workspace_refreshes_writable_copy_without_mutating_master(tmp_path: Path):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    original = _xlsx({"A1": ("WSD(\"x\")", "old")})
    refreshed = _xlsx({"A1": ("WSD(\"x\")", "ready")})
    service.upload_resource("weekly-fund", "workbooks/model.xlsx", original)
    service.create_version("weekly-fund")
    service.publish_version("weekly-fund", 1)
    run = service.create_run_workspace("weekly-fund", 1)
    run_root = Path(run["path"])
    run_workbook = run_root / "workbooks/model.xlsx"
    assert run_workbook.stat().st_mode & 0o200

    provider = FakeProvider(replacement=refreshed)
    result = service.refresh_workbook(
        run["run_id"],
        "workbooks/model.xlsx",
        refresh_service=WorkbookRefreshService(providers={"wind_excel": provider}),
    )

    master = service.root / "weekly-fund/versions/1/workbooks/model.xlsx"
    assert result.status == "ready"
    assert result.resource.path == "workbooks/model.xlsx"
    assert master.read_bytes() == original
    assert run_workbook.read_bytes() == refreshed
    manifest = service.read_refresh_manifest(run["run_id"])
    assert manifest["workbook"] == "workbooks/model.xlsx"
    assert manifest["output_sha256"] == result.resource.sha256


def test_datahub_fallback_must_be_explicitly_equivalent(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ("WSD(\"x\")", "ready")}))
    unavailable = FakeProvider(ready=False)
    datahub = FakeProvider(provider_id="datahub", replacement=source.read_bytes())
    refresh = WorkbookRefreshService(
        providers={"wind_excel": unavailable, "datahub": datahub}
    )
    implicit = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        required_cells=["Sheet1!A1"],
        poll_interval_seconds=0,
    )
    blocked = refresh.refresh(source, tmp_path / "implicit", implicit)
    assert blocked.status == "blocked_data"
    assert blocked.code == "provider_not_ready"
    assert datahub.calls == []

    explicit = implicit.model_copy(
        update={
            "providers": [
                WorkbookProviderRequirement(
                    provider="wind_excel",
                    equivalent_datahub_mapping="mappings/wind-equivalent.yaml",
                )
            ]
        }
    )
    ready = refresh.refresh(source, tmp_path / "explicit", explicit)
    assert ready.status == "ready"
    assert ready.provider == "datahub"
