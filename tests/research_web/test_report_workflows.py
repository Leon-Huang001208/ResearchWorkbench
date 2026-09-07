"""Report Workflow package and Excel refresh contract regressions."""

from __future__ import annotations

import hashlib
import importlib
import json
import multiprocessing
import os
import signal
import threading
import time
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

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
    WorkbookRefreshResult,
    WorkbookRefreshService,
    WorkflowError,
    WorkflowSchedule,
    scan_workbook_formulas,
)
from app.research_web.report_workflows import catalog as catalog_module
from app.research_web.report_workflows import workbook as workbook_module
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


def _manifest(
    *requirements: WorkbookProviderRequirement, workflow_id: str = "weekly-fund"
) -> ReportWorkflowManifest:
    return ReportWorkflowManifest(
        workflow_id=workflow_id,
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
    with pytest.raises(ValidationError):
        ReportWorkflowManifest(
            workflow_id="weekly-fund",
            name="基金周报",
            version=1,
            excluded_workbooks=["../outside.xlsx"],
            delivery=DeliveryContract(formats=["xlsx"]),
        )
    with pytest.raises(ValidationError):
        WorkbookRefreshResult(status="ready", manifest_path="/private/manifest.json")


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


def test_catalog_lock_reloads_before_multi_instance_writes(tmp_path: Path):
    first = ReportWorkflowService(tmp_path)
    second = ReportWorkflowService(tmp_path)
    barrier = threading.Barrier(2)
    errors = []

    def create(service, workflow_id):
        try:
            barrier.wait()
            service.create_draft(_manifest(workflow_id=workflow_id))
        except Exception as exc:  # noqa: BLE001 - assertions report worker failures.
            errors.append(exc)

    threads = [
        threading.Thread(target=create, args=(first, "weekly-one")),
        threading.Thread(target=create, args=(second, "weekly-two")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    reloaded = ReportWorkflowService(tmp_path)
    assert set(reloaded.data["workflows"]) == {"weekly-one", "weekly-two"}


def test_catalog_run_reads_reload_cross_instance_state(tmp_path: Path):
    stale = ReportWorkflowService(tmp_path)
    writer = ReportWorkflowService(tmp_path)
    writer.create_draft(_manifest())
    writer.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "ready")})
    )
    writer.create_version("weekly-fund")
    writer.publish_version("weekly-fund", 1)
    run = writer.create_run_workspace("weekly-fund", 1)

    assert stale.run_path(run["run_id"]) == Path(run["path"])
    assert (
        stale.refresh_workbook(run["run_id"], "workbooks/model.xlsx").status == "ready"
    )


@pytest.mark.parametrize(
    ("formulas", "expected"),
    [
        (['WSD("600000.SH","close")'], WorkbookFormulaProvider.WIND),
        (['s_info_name("600000.SH")'], WorkbookFormulaProvider.WIND),
        (['s_wq_pctchange("600000.SH")'], WorkbookFormulaProvider.WIND),
        (['THS_HQ("600000.SH","close")'], WorkbookFormulaProvider.IFIND),
        (['thsiFinD("000001.OF","ths_fund_nav")'], WorkbookFormulaProvider.IFIND),
        (
            ['WSS("600000.SH","sec_name")', 'THS_BD("600000.SH")'],
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


def test_xlsx_parser_rejects_high_ratio_zip_bomb(tmp_path: Path):
    workbook = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (2 * 1024 * 1024))
    with pytest.raises(WorkflowError) as error:
        scan_workbook_formulas(workbook)
    assert error.value.code == "unsafe_workbook_archive"


def test_preflight_requires_declared_providers_for_mixed_workbook(tmp_path: Path):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    service.upload_resource(
        "weekly-fund",
        "workbooks/model.xlsx",
        _xlsx({"A1": ('WSD("x")', 1), "B1": ('THS_HQ("x")', 1)}),
    )
    service.create_version("weekly-fund")
    result = service.preflight("weekly-fund", 1)
    assert result["status"] == "blocked_data"
    assert result["code"] == "provider_declaration_missing"
    assert result["missing_providers"] == ["ifind_excel"]


def test_preflight_blocks_external_formula_workbook_without_refresh_policy(
    tmp_path: Path,
):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": ('WSD("x")', 1)})
    )
    service.upload_resource(
        "weekly-fund", "workbooks/undeclared.xlsx", _xlsx({"A1": ('WSD("y")', 2)})
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


def test_create_run_rejects_unpublished_explicit_version(tmp_path: Path):
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest())
    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "ready")})
    )
    service.create_version("weekly-fund")
    with pytest.raises(WorkflowError) as error:
        service.create_run_workspace("weekly-fund", 1)
    assert error.value.code == "version_not_published"


def test_rollback_preserves_current_version_when_preflight_is_blocked(tmp_path: Path):
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest())
    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "one")})
    )
    service.create_version("weekly-fund")
    service.publish_version("weekly-fund", 1)
    service.upload_resource(
        "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "two")})
    )
    service.create_version("weekly-fund")
    service.publish_version("weekly-fund", 2)
    old = service.root / "weekly-fund/versions/1/workbooks/model.xlsx"
    old.chmod(0o600)
    old.write_bytes(b"tampered")

    with pytest.raises(WorkflowError) as error:
        service.rollback_version("weekly-fund", 1)

    assert error.value.code == "resource_hash_mismatch"
    assert (
        ReportWorkflowService(tmp_path).data["workflows"]["weekly-fund"][
            "current_version"
        ]
        == 2
    )


class FakeProvider:
    bounded_calls = True

    def __init__(
        self,
        provider_id="wind_excel",
        ready=True,
        values=None,
        replacement=None,
        *,
        event_path=None,
        mapping_path=None,
        pid_path=None,
        block_seconds=0,
    ):
        self.provider_id = provider_id
        self.ready = ready
        self.values = values or {"Sheet1!A1": "ready"}
        self.replacement = replacement
        self.calls = []
        self.fallback_mappings = None
        self.event_path = event_path
        self.mapping_path = mapping_path
        self.pid_path = pid_path
        self.block_seconds = block_seconds

    def readiness(self):
        return {"ready": self.ready, "code": None if self.ready else "plugin_not_ready"}

    def open_workbook(self, path):
        self.calls.append("open")
        return path

    def refresh_all(self, handle):
        self.calls.append("refresh")
        if self.pid_path:
            Path(self.pid_path).write_text(str(os.getpid()))
        if self.event_path:
            with Path(self.event_path).open("a") as stream:
                stream.write(f"start {os.getpid()}\n")
                stream.flush()
                os.fsync(stream.fileno())
        if self.block_seconds:
            time.sleep(self.block_seconds)
        if self.event_path:
            time.sleep(0.15)
            with Path(self.event_path).open("a") as stream:
                stream.write(f"end {os.getpid()}\n")
                stream.flush()
                os.fsync(stream.fileno())

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

    def configure_fallback(self, mappings):
        self.fallback_mappings = mappings
        if self.mapping_path:
            Path(self.mapping_path).write_text(json.dumps(mappings, sort_keys=True))


class SlowBoundaryRefreshService(WorkbookRefreshService):
    def __init__(self, event_path):
        super().__init__()
        self.event_path = Path(event_path)

    def _refresh_locked(self, *args, **kwargs):
        with self.event_path.open("a") as stream:
            stream.write(f"start {os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())
        time.sleep(0.15)
        result = super()._refresh_locked(*args, **kwargs)
        with self.event_path.open("a") as stream:
            stream.write(f"end {os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())
        return result


def _multiprocess_target_refresh(source, run_directory, event_path, result_queue):
    policy = WorkbookRefreshPolicy(workbook="workbooks/model.xlsx")
    result = SlowBoundaryRefreshService(event_path).refresh(
        Path(source), Path(run_directory), policy
    )
    result_queue.put(result.status.value)


def _multiprocess_excel_refresh(source, run_directory, event_path, result_queue):
    source_path = Path(source)
    provider = FakeProvider(
        replacement=source_path.read_bytes(),
        event_path=event_path,
    )
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        poll_interval_seconds=0,
    )
    result = WorkbookRefreshService(providers={"wind_excel": provider}).refresh(
        source_path, Path(run_directory), policy
    )
    result_queue.put(result.status.value)


def _hold_posix_file_lock(lock_path, ready, release):
    import fcntl

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        ready.set()
        release.wait(10)


def _run_two_processes(target, args_one, args_two):
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(target=target, args=(*args_one, result_queue)),
        context.Process(target=target, args=(*args_two, result_queue)),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
    statuses = [result_queue.get(timeout=2) for _ in processes]
    result_queue.close()
    assert all(process.exitcode == 0 for process in processes)
    return statuses


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


def test_official_excel_provider_blocks_windows_without_starting_worker(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(workbook_module.sys, "platform", "win32")

    def unexpected_import(*args, **kwargs):
        pytest.fail("unsupported platforms must not import xlwings")

    monkeypatch.setattr(workbook_module.importlib, "import_module", unexpected_import)
    assert WindExcelProvider().readiness() == {
        "ready": False,
        "code": "unsupported_platform",
    }

    def unexpected_worker(*args, **kwargs):
        pytest.fail("unsupported platforms must not start an Excel worker")

    monkeypatch.setattr(workbook_module, "_run_provider_readiness", unexpected_worker)
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    result = WorkbookRefreshService().refresh(
        source,
        tmp_path / "run",
        WorkbookRefreshPolicy(
            workbook="workbooks/model.xlsx",
            providers=[WorkbookProviderRequirement(provider="wind_excel")],
        ),
    )

    assert result.code == "unsupported_platform"
    assert not (tmp_path / "run/workbooks/model.xlsx").exists()


def test_xlwings_open_failure_quits_hidden_excel_instance():
    class Books:
        def open(self, *args, **kwargs):
            raise OSError("secret workbook path")

    class App:
        def __init__(self):
            self.books = Books()
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    app = App()
    provider = WindExcelProvider()
    provider._xlwings = SimpleNamespace(App=lambda **kwargs: app)
    with pytest.raises(OSError):
        provider.open_workbook(Path("ignored.xlsx"))
    assert app.quit_called is True


def test_xlwings_mac_uses_appscript_refresh_and_full_rebuild(monkeypatch):
    calls = []

    class API:
        def refresh_all(self):
            calls.append("refresh")

    class AppAPI:
        def calculate_full_rebuild(self):
            calls.append("calculate")

    provider = WindExcelProvider()
    handle = SimpleNamespace(
        api=API(),
        app=SimpleNamespace(api=AppAPI(), calculate=lambda: calls.append("fallback")),
    )
    monkeypatch.setattr(workbook_module.sys, "platform", "darwin")

    provider.refresh_all(handle)
    provider.calculate_full(handle)

    assert calls == ["refresh", "calculate"]


def test_provider_worker_reports_safe_refresh_phase_code(tmp_path: Path, monkeypatch):
    class FailingProvider(FakeProvider):
        def refresh_all(self, handle):
            raise OSError("secret formula and account details")

    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
    )

    messages = []
    monkeypatch.setattr(workbook_module, "_isolate_worker_process", lambda: None)
    workbook_module._provider_refresh_worker(
        {"kind": "injected", "provider": FailingProvider()},
        str(source),
        json.loads(policy.model_dump_json()),
        {},
        SimpleNamespace(put=messages.append),
    )
    result = messages[-1]

    assert result == {"status": "blocked", "code": "plugin_refresh_failed"}
    assert "secret" not in json.dumps(result)


def test_injected_provider_executes_in_killable_worker(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    pid_path = tmp_path / "provider.pid"
    refreshed = _xlsx({"A1": ('WSD("x")', "ready")})
    source.write_bytes(refreshed)
    provider = FakeProvider(replacement=refreshed, pid_path=pid_path)
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        poll_interval_seconds=0,
    )

    result = WorkbookRefreshService(providers={"wind_excel": provider}).refresh(
        source, tmp_path / "run", policy
    )

    assert result.status == "ready"
    assert int(pid_path.read_text()) != os.getpid()


def test_refresh_cancellation_kills_worker_and_prevents_output_promotion(
    tmp_path: Path,
):
    source = tmp_path / "source.xlsx"
    pid_path = tmp_path / "provider.pid"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    provider = FakeProvider(
        replacement=source.read_bytes(),
        pid_path=pid_path,
        block_seconds=10,
    )
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        timeout_seconds=15,
        poll_interval_seconds=0,
    )
    cancellation = threading.Event()
    results = []
    thread = threading.Thread(
        target=lambda: results.append(
            WorkbookRefreshService(providers={"wind_excel": provider}).refresh(
                source,
                tmp_path / "run",
                policy,
                cancellation_event=cancellation,
            )
        )
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not pid_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert pid_path.exists()
    worker_pid = int(pid_path.read_text())

    cancellation.set()
    thread.join(5)

    assert not thread.is_alive()
    assert results[0].code == "refresh_cancelled"
    assert not workbook_module._process_exists(worker_pid)
    assert not (tmp_path / "run/workbooks/model.xlsx").exists()
    assert not list((tmp_path / "run/refresh-manifests").glob("*.json"))


def test_refresh_cancellation_interrupts_target_lock_wait_without_output(
    tmp_path: Path,
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))
    run_directory = tmp_path / "run"
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        timeout_seconds=5,
    )
    manifest_name = hashlib.sha256(policy.workbook.encode()).hexdigest() + ".json"
    lock_path = run_directory / ".refresh-locks" / f"{manifest_name}.lock"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(
        target=_hold_posix_file_lock,
        args=(str(lock_path), ready, release),
    )
    holder.start()
    assert ready.wait(5)
    cancellation = threading.Event()
    results = []
    thread = threading.Thread(
        target=lambda: results.append(
            WorkbookRefreshService().refresh(
                source,
                run_directory,
                policy,
                cancellation_event=cancellation,
            )
        )
    )
    try:
        thread.start()
        time.sleep(0.15)
        cancellation.set()
        thread.join(1)
        still_waiting = thread.is_alive()
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)
        thread.join(5)

    assert still_waiting is False
    assert results[0].code == "refresh_cancelled"
    assert not (run_directory / "workbooks/model.xlsx").exists()
    assert not list((run_directory / "refresh-manifests").glob("*.json"))


def test_refresh_lock_timeout_is_sanitized_and_writes_no_output(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))
    run_directory = tmp_path / "run"
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        timeout_seconds=0.1,
    )
    manifest_name = hashlib.sha256(policy.workbook.encode()).hexdigest() + ".json"
    lock_path = run_directory / ".refresh-locks" / f"{manifest_name}.lock"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(
        target=_hold_posix_file_lock,
        args=(str(lock_path), ready, release),
    )
    holder.start()
    assert ready.wait(5)
    try:
        started = time.monotonic()
        result = WorkbookRefreshService().refresh(source, run_directory, policy)
        elapsed = time.monotonic() - started
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)

    assert elapsed < 1
    assert result.code == "refresh_lock_timeout"
    assert not (run_directory / "workbooks/model.xlsx").exists()
    assert not list((run_directory / "refresh-manifests").glob("*.json"))


def test_refresh_lock_open_error_is_sanitized(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))

    monkeypatch.setattr(
        workbook_module.os,
        "open",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secret path")),
    )

    result = WorkbookRefreshService().refresh(
        source,
        tmp_path / "run",
        WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
    )

    assert result.code == "refresh_lock_unavailable"
    assert "secret" not in result.model_dump_json()


def test_missing_refresh_source_returns_safe_blocked_result(tmp_path: Path):
    result = WorkbookRefreshService().refresh(
        tmp_path / "missing.xlsx",
        tmp_path / "run",
        WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
    )

    assert result.status == "blocked_data"
    assert result.code == "workbook_unreadable"


def test_run_directory_setup_error_returns_safe_blocked_result(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))
    run_directory = tmp_path / "run"
    real_mkdir = Path.mkdir

    def fail_run_mkdir(path, *args, **kwargs):
        if path == run_directory:
            raise OSError("secret directory")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_run_mkdir)
    result = WorkbookRefreshService().refresh(
        source,
        run_directory,
        WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
    )

    assert result.code == "unsafe_run_directory"
    assert "secret" not in result.model_dump_json()


def test_refresh_cleanup_error_does_not_escape_or_replace_validation_code(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, None)}))
    real_unlink = Path.unlink

    def fail_staging_cleanup(path, *args, **kwargs):
        if path.name.endswith(".refreshing.xlsx"):
            raise OSError("secret cleanup path")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_staging_cleanup)
    result = WorkbookRefreshService().refresh(
        source,
        tmp_path / "run",
        WorkbookRefreshPolicy(
            workbook="workbooks/model.xlsx",
            required_cells=["Sheet1!A1"],
        ),
    )

    assert result.code == "required_cell_empty"
    assert "secret" not in result.model_dump_json()


def test_target_and_excel_locks_serialize_across_processes(tmp_path: Path):
    plain = tmp_path / "plain.xlsx"
    external = tmp_path / "external.xlsx"
    plain.write_bytes(_xlsx({"A1": (None, "ready")}))
    external.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))

    target_events = tmp_path / "target-events.txt"
    target_statuses = _run_two_processes(
        _multiprocess_target_refresh,
        (str(plain), str(tmp_path / "same-run"), str(target_events)),
        (str(plain), str(tmp_path / "same-run"), str(target_events)),
    )
    excel_events = tmp_path / "excel-events.txt"
    excel_statuses = _run_two_processes(
        _multiprocess_excel_refresh,
        (str(external), str(tmp_path / "run-one"), str(excel_events)),
        (str(external), str(tmp_path / "run-two"), str(excel_events)),
    )

    assert target_statuses == ["ready", "ready"]
    assert excel_statuses == ["ready", "ready"]
    assert [line.split()[0] for line in target_events.read_text().splitlines()] == [
        "start",
        "end",
        "start",
        "end",
    ]
    assert [line.split()[0] for line in excel_events.read_text().splitlines()] == [
        "start",
        "end",
        "start",
        "end",
    ]


def test_provider_bounded_flag_is_ignored_in_favor_of_worker_isolation(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    provider = FakeProvider()
    provider.bounded_calls = False
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
    )
    result = WorkbookRefreshService(providers={"wind_excel": provider}).refresh(
        source, tmp_path / "run", policy
    )
    assert result.status == "ready"
    assert provider.calls == []


def test_refresh_timeout_budget_is_shared_across_provider_phases(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(
        _xlsx({"A1": ('WSD("x")', "ready"), "B1": ('THS_HQ("x")', "ready")})
    )
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[
            WorkbookProviderRequirement(provider="wind_excel"),
            WorkbookProviderRequirement(provider="ifind_excel"),
        ],
        timeout_seconds=0.5,
        poll_interval_seconds=0,
    )
    observed: list[float] = []

    def readiness(provider, timeout_seconds, cancellation_event=None):
        observed.append(timeout_seconds)
        time.sleep(0.05)
        return {"status": "ready"}

    def refresh(provider, path, policy, mappings, cancellation_event=None, **kwargs):
        observed.append(kwargs.get("timeout_seconds", policy.timeout_seconds))
        return {"status": "ready"}

    monkeypatch.setattr(workbook_module, "_run_provider_readiness", readiness)
    monkeypatch.setattr(workbook_module, "_run_provider_refresh", refresh)
    result = WorkbookRefreshService(
        providers={
            "wind_excel": FakeProvider(),
            "ifind_excel": FakeProvider("ifind_excel"),
        }
    ).refresh(source, tmp_path / "run", policy)

    assert result.status == "ready"
    assert len(observed) == 3
    assert observed[0] > observed[1] > observed[2] > 0


def test_refresh_timeout_fails_closed_before_next_provider_phase(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(
        _xlsx({"A1": ('WSD("x")', "ready"), "B1": ('THS_HQ("x")', "ready")})
    )
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[
            WorkbookProviderRequirement(provider="wind_excel"),
            WorkbookProviderRequirement(provider="ifind_excel"),
        ],
        timeout_seconds=0.05,
    )
    calls = []

    def readiness(*args, **kwargs):
        calls.append("readiness")
        time.sleep(0.06)
        return {"status": "ready"}

    monkeypatch.setattr(workbook_module, "_run_provider_readiness", readiness)
    result = WorkbookRefreshService(
        providers={
            "wind_excel": FakeProvider(),
            "ifind_excel": FakeProvider("ifind_excel"),
        }
    ).refresh(source, tmp_path / "run", policy)

    assert result.code == "provider_timeout"
    assert calls == ["readiness"]
    assert not (tmp_path / "run/workbooks/model.xlsx").exists()


def test_official_provider_timeout_terminates_process_group_and_rechecks(
    monkeypatch, tmp_path: Path
):
    state = {
        "child_alive": True,
        "child_signals": [],
        "killed": False,
        "joined": [],
        "signals": [],
    }

    class Queue:
        sent = False

        def get(self, timeout):
            if not self.sent:
                self.sent = True
                return {"status": "started", "child_pids": [54321]}
            raise workbook_module.queue.Empty

        def close(self):
            return None

    class Process:
        pid = 43210

        def start(self):
            return None

        def join(self, timeout):
            state["joined"].append(timeout)

        def is_alive(self):
            return not state["killed"]

        def terminate(self):
            state["killed"] = True

        def kill(self):
            state["killed"] = True

    context = SimpleNamespace(
        Queue=lambda **kwargs: Queue(), Process=lambda **kwargs: Process()
    )
    monkeypatch.setattr(
        workbook_module.multiprocessing, "get_context", lambda mode: context
    )
    monkeypatch.setattr(workbook_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        workbook_module.os,
        "killpg",
        lambda pid, requested_signal: state["signals"].append(requested_signal),
    )

    def kill_child(pid, requested_signal):
        assert pid == 54321
        if requested_signal == 0:
            if state["child_alive"]:
                return
            raise ProcessLookupError
        state["child_signals"].append(requested_signal)
        if requested_signal == signal.SIGKILL:
            state["child_alive"] = False

    monkeypatch.setattr(workbook_module.os, "kill", kill_child)
    provider = WindExcelProvider()
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx", timeout_seconds=0.01
    )
    assert (
        provider.refresh_with_timeout(tmp_path / "model.xlsx", policy)
        == "provider_timeout"
    )
    assert state["killed"] is True
    assert state["signals"] == [signal.SIGTERM, signal.SIGKILL]
    assert state["child_signals"] == [signal.SIGTERM, signal.SIGKILL]
    assert state["joined"] == [0.01, 2, 2]


def test_non_ready_worker_exit_cleans_registered_excel_process(monkeypatch):
    messages = iter(
        [
            {"status": "started", "child_pids": [54321]},
            {"status": "blocked", "code": "plugin_not_ready"},
        ]
    )

    class Queue:
        def get(self, timeout):
            try:
                return next(messages)
            except StopIteration as exc:
                raise workbook_module.queue.Empty from exc

        def close(self):
            return None

    class Process:
        pid = 43210

        def start(self):
            return None

        def join(self, timeout):
            return None

        def is_alive(self):
            return False

    cleaned = []
    context = SimpleNamespace(
        Queue=lambda **kwargs: Queue(), Process=lambda **kwargs: Process()
    )
    monkeypatch.setattr(
        workbook_module.multiprocessing, "get_context", lambda mode: context
    )
    monkeypatch.setattr(
        workbook_module,
        "_terminate_child_processes",
        lambda pids: cleaned.append(pids) or True,
    )

    result = workbook_module._run_provider_worker(lambda: None, (), 1)

    assert result == {"status": "blocked", "code": "plugin_not_ready"}
    assert cleaned == [{54321}]


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


def test_refresh_blocks_date_older_than_dynamic_max_age(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "2026-09-03")}))
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        required_date_cell="Sheet1!A1",
        max_age_days=1,
    )
    result = WorkbookRefreshService().refresh(
        source, tmp_path / "run", policy, refresh_date=date(2026, 9, 6)
    )
    assert result.status == "blocked_data"
    assert result.code == "required_date_stale"


def test_refresh_worker_writes_hashed_manifest(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    refreshed = _xlsx({"A1": ('WSD("x")', "ready")})
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "old")}))

    provider = FakeProvider(replacement=refreshed)
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        required_cells=["Sheet1!A1"],
        poll_interval_seconds=0,
        timeout_seconds=90,
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

    assert all(result.status == "ready" for result in results)
    assert provider.calls == []
    for index, result in enumerate(results):
        manifest = json.loads(
            (tmp_path / f"run-{index}" / result.manifest_path).read_text()
        )
        assert manifest["output_sha256"] == result.resource.sha256


def test_same_run_workbook_lock_covers_copy_through_manifest(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[WorkbookProviderRequirement(provider="wind_excel")],
        required_cells=["Sheet1!A1"],
        poll_interval_seconds=0,
        timeout_seconds=90,
    )
    provider = FakeProvider(replacement=source.read_bytes())
    service = WorkbookRefreshService(providers={"wind_excel": provider})
    real_copy = workbook_module.shutil.copy2
    active = 0
    peak = 0
    guard = threading.Lock()

    def slow_copy(source_path, destination_path):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        result = real_copy(source_path, destination_path)
        with guard:
            active -= 1
        return result

    monkeypatch.setattr(workbook_module.shutil, "copy2", slow_copy)
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(
                service.refresh(source, tmp_path / "same-run", policy)
            )
        )
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == 1
    assert all(result.status == "ready" for result in results)
    assert len({result.manifest_path for result in results}) == 1


def test_run_workspace_refreshes_writable_copy_without_mutating_master(tmp_path: Path):
    wind = WorkbookProviderRequirement(provider="wind_excel")
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(wind))
    original = _xlsx({"A1": ('WSD("x")', "old")})
    refreshed = _xlsx({"A1": ('WSD("x")', "ready")})
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
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    unavailable = FakeProvider(ready=False)
    mapping_path = tmp_path / "mapping.json"
    datahub = FakeProvider(
        provider_id="datahub",
        replacement=source.read_bytes(),
        mapping_path=mapping_path,
    )
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
    mapping = {"mappings/wind-equivalent.yaml": {"fields": {"close": "close"}}}
    ready = refresh.refresh(
        source, tmp_path / "explicit", explicit, fallback_mappings=mapping
    )
    assert ready.status == "ready"
    assert ready.provider == "datahub"
    assert datahub.fallback_mappings is None
    assert json.loads(mapping_path.read_text()) == mapping


def test_datahub_fallback_rejects_missing_mapping_bytes(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": ('WSD("x")', "ready")}))
    policy = WorkbookRefreshPolicy(
        workbook="workbooks/model.xlsx",
        providers=[
            WorkbookProviderRequirement(
                provider="wind_excel",
                equivalent_datahub_mapping="mappings/wind.yaml",
            )
        ],
    )
    refresh = WorkbookRefreshService(
        providers={
            "wind_excel": FakeProvider(ready=False),
            "datahub": FakeProvider(provider_id="datahub"),
        }
    )
    result = refresh.refresh(source, tmp_path / "run", policy)
    assert result.status == "blocked_data"
    assert result.code == "fallback_mapping_missing"


def test_catalog_reads_versioned_mapping_before_datahub_fallback(tmp_path: Path):
    requirement = WorkbookProviderRequirement(
        provider="wind_excel",
        equivalent_datahub_mapping="mappings/wind.yaml",
    )
    service = ReportWorkflowService(tmp_path)
    service.create_draft(_manifest(requirement))
    source = _xlsx({"A1": ('WSD("x")', "ready")})
    service.upload_resource("weekly-fund", "workbooks/model.xlsx", source)
    service.upload_resource(
        "weekly-fund", "mappings/wind.yaml", b"fields:\n  close: close\n"
    )
    service.create_version("weekly-fund")
    service.publish_version("weekly-fund", 1)
    run = service.create_run_workspace("weekly-fund", 1)
    mapping_path = tmp_path / "catalog-mapping.json"
    datahub = FakeProvider(
        provider_id="datahub",
        replacement=source,
        mapping_path=mapping_path,
    )
    result = service.refresh_workbook(
        run["run_id"],
        "workbooks/model.xlsx",
        refresh_service=WorkbookRefreshService(
            providers={"wind_excel": FakeProvider(ready=False), "datahub": datahub}
        ),
    )
    assert result.status == "ready"
    assert datahub.fallback_mappings is None
    assert json.loads(mapping_path.read_text()) == {
        "mappings/wind.yaml": {"fields": {"close": "close"}}
    }


def test_each_workbook_gets_an_independent_refresh_manifest(tmp_path: Path):
    source_one = tmp_path / "one.xlsx"
    source_two = tmp_path / "two.xlsx"
    source_one.write_bytes(_xlsx({"A1": (None, "one")}))
    source_two.write_bytes(_xlsx({"A1": (None, "two")}))
    refresh = WorkbookRefreshService()
    one = refresh.refresh(
        source_one,
        tmp_path / "run",
        WorkbookRefreshPolicy(workbook="workbooks/one.xlsx"),
    )
    two = refresh.refresh(
        source_two,
        tmp_path / "run",
        WorkbookRefreshPolicy(workbook="workbooks/two.xlsx"),
    )
    assert one.manifest_path != two.manifest_path
    assert (
        json.loads((tmp_path / "run" / one.manifest_path).read_text())["workbook"]
        == "workbooks/one.xlsx"
    )
    assert (
        json.loads((tmp_path / "run" / two.manifest_path).read_text())["workbook"]
        == "workbooks/two.xlsx"
    )


def test_refresh_result_exposes_relative_manifest_reference(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))
    run_directory = tmp_path / "run"
    result = WorkbookRefreshService().refresh(
        source,
        run_directory,
        WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
    )

    expected = (
        "refresh-manifests/"
        + hashlib.sha256(b"workbooks/model.xlsx").hexdigest()
        + ".json"
    )
    assert result.manifest_path == expected
    assert (run_directory / expected).is_file()


def test_failed_manifest_promotion_does_not_leave_untracked_workbook(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source.xlsx"
    source.write_bytes(_xlsx({"A1": (None, "ready")}))
    real_replace = workbook_module.os.replace

    def fail_manifest_replace(source_path, destination_path):
        if Path(destination_path).suffix == ".json":
            raise OSError("manifest unavailable")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(workbook_module.os, "replace", fail_manifest_replace)
    result = WorkbookRefreshService().refresh(
        source,
        tmp_path / "run",
        WorkbookRefreshPolicy(workbook="workbooks/model.xlsx"),
    )
    assert result.status == "blocked_data"
    assert not (tmp_path / "run/workbooks/model.xlsx").exists()


def test_failed_refresh_keeps_previous_workbook_and_manifest_pair(
    tmp_path: Path, monkeypatch
):
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    first.write_bytes(_xlsx({"A1": (None, "first")}))
    second.write_bytes(_xlsx({"A1": (None, "second")}))
    service = WorkbookRefreshService()
    policy = WorkbookRefreshPolicy(workbook="workbooks/model.xlsx")
    ready = service.refresh(first, tmp_path / "run", policy)
    destination = tmp_path / "run/workbooks/model.xlsx"
    previous_workbook = destination.read_bytes()
    manifest_path = tmp_path / "run" / ready.manifest_path
    previous_manifest = manifest_path.read_bytes()
    real_replace = workbook_module.os.replace

    def fail_new_manifest(source_path, destination_path):
        if Path(destination_path) == manifest_path:
            raise OSError("manifest unavailable")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(workbook_module.os, "replace", fail_new_manifest)
    blocked = service.refresh(second, tmp_path / "run", policy)

    assert blocked.status == "blocked_data"
    assert destination.read_bytes() == previous_workbook
    assert manifest_path.read_bytes() == previous_manifest


@pytest.mark.parametrize("operation", ["draft", "version", "run"])
def test_catalog_save_failure_does_not_leave_unindexed_directory(
    tmp_path: Path, monkeypatch, operation: str
):
    service = ReportWorkflowService(tmp_path)
    if operation != "draft":
        service.create_draft(_manifest())
        service.upload_resource(
            "weekly-fund", "workbooks/model.xlsx", _xlsx({"A1": (None, "ready")})
        )
    if operation == "run":
        service.create_version("weekly-fund")
        service.publish_version("weekly-fund", 1)

    def fail_save(*args, **kwargs):
        raise WorkflowError("save failed", "catalog_unavailable", 503)

    monkeypatch.setattr(catalog_module, "_atomic_json", fail_save)
    if operation == "draft":
        with pytest.raises(WorkflowError):
            service.create_draft(_manifest())
        assert not (service.root / "weekly-fund").exists()
    elif operation == "version":
        with pytest.raises(WorkflowError):
            service.create_version("weekly-fund")
        assert not (service.root / "weekly-fund/versions/1").exists()
    else:
        before = set((service.root / "runs").iterdir())
        with pytest.raises(WorkflowError):
            service.create_run_workspace("weekly-fund", 1)
        assert set((service.root / "runs").iterdir()) == before
