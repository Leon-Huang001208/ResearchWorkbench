"""Report revision must work inside the original kernel sandbox and retain lineage."""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest
from test_research_quality import example, saved_report

from app.research_web.research_evidence import report_projection
from app.research_web.resources.research_report import archive_report_version, write_research_report
from app.research_web.store import Store


def test_relative_archive_does_not_require_getcwd(tmp_path, monkeypatch):
    output = tmp_path / "outputs"
    output.mkdir()
    saved_report(output)
    monkeypatch.chdir(tmp_path)

    def denied():
        raise PermissionError("getcwd is denied by the original native sandbox")

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "getcwd", denied)
        version = archive_report_version(Path("outputs"))
    assert len(version["files"]) == 4
    for row in version["files"]:
        path = output / version["directory"] / row["stored_name"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert not list((output / "report-versions").glob(".pending-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="requires the original macOS kernel sandbox")
def test_second_write_archives_actual_report_in_original_native_sandbox(tmp_path):
    from app.research_web.sandbox import SandboxConfig, run_script

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "native revision")["id"]
    directory = store.directory(sid)
    resources = Path(__file__).parents[2] / "app/research_web/resources"
    shutil.copytree(resources, directory / "resources", dirs_exist_ok=True)
    _, payload, _ = example()
    code = (
        "import json\n"
        "from research_report import write_research_report, list_report_versions\n"
        f"payload = {payload!r}\n"
        "first = write_research_report('outputs', payload)\n"
        "original = first['json'].read_bytes()\n"
        "payload['title'] = '修订后的风险说明'\n"
        "second = write_research_report('outputs', payload)\n"
        "versions = list_report_versions('outputs')\n"
        "assert len(versions) == 1\n"
        "assert versions[0]['report']['title'] == '风险说明'\n"
        "assert json.loads(second['json'].read_text())['title'] == '修订后的风险说明'\n"
        "print('NATIVE_REPORT_REVISION_OK')\n"
    )
    result = run_script(SandboxConfig(store.root, Path(sys.executable)), directory, code)
    assert result.status == "completed", result.stderr
    assert "NATIVE_REPORT_REVISION_OK" in result.stdout
    assert not list((directory / "outputs/report-versions").glob(".pending-*"))


def projection_case(tmp_path):
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "canonical report")["id"]
    contract, payload, sources = example()
    output = store.directory(sid) / "outputs"
    paths = write_research_report(output, payload)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**row, "valid": True} for row in manifest["artifacts"]]}
    backup = output / "diagnostic-backup"
    backup.mkdir()
    shutil.copyfile(paths["json"], backup / "research-report.json")
    return store, sid, contract, sources, delivery, paths


def project(store, sid, contract, sources, delivery, files=None):
    return report_projection(
        store,
        sid,
        store.files(sid) if files is None else files,
        sources,
        contract["task_id"],
        delivery,
        contract=contract,
    )


def test_backup_report_name_cannot_make_current_canonical_report_ambiguous(tmp_path):
    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    result = project(store, sid, contract, sources, delivery)
    assert result["quality"] == "passed", result


def test_nested_report_without_current_canonical_report_remains_invalid(tmp_path):
    store, sid, contract, sources, delivery, paths = projection_case(tmp_path)
    paths["json"].unlink()
    result = project(store, sid, contract, sources, delivery)
    assert result["quality"] == "invalid"
    assert "report_identity_noncanonical" in result["issues"]


def test_duplicate_canonical_identity_still_fails_closed(tmp_path):
    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    files = store.files(sid)
    canonical = next(
        file
        for file in files
        if store.session(sid)["files"][file["id"]] == str(Path("outputs") / "research-report.json")
    )
    result = project(store, sid, contract, sources, delivery, [*files, canonical])
    assert result["quality"] == "invalid"
    assert "report_identity_ambiguous" in result["issues"]


@pytest.mark.parametrize(
    "relative,status",
    [
        ("outputs\\research-report.json", "passed"),
        ("outputs\\..\\outputs\\research-report.json", "invalid"),
    ],
)
def test_windows_path_selector_requires_exact_native_mapping(
    tmp_path, monkeypatch, relative, status
):
    import app.research_web.research_evidence as evidence

    store, sid, contract, sources, delivery, _ = projection_case(tmp_path)
    files = store.files(sid)
    row = store.session(sid)
    mapped = {fid: path.replace("/", "\\") for fid, path in row["files"].items()}
    canonical = next(fid for fid, path in mapped.items() if path == "outputs\\research-report.json")
    mapped[canonical] = relative
    windows_store = SimpleNamespace(
        session=lambda requested: {**store.session(requested), "files": mapped},
        open_file=store.open_file,
    )
    monkeypatch.setattr(evidence, "Path", PureWindowsPath)
    result = project(windows_store, sid, contract, sources, delivery, files)
    assert result["quality"] == status
