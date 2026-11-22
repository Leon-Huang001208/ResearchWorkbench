"""Final research links must refer to exact Host-checked immutable bytes."""

import hashlib
import json
from types import SimpleNamespace

from app.research_web.research_quality_service import quality_versions, report_delivery
from app.research_web.resources.research_report import archive_report_version
from app.research_web.store import Store


def fixture(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "links")["id"]
    output = store.directory(sid) / "outputs"
    payload = {
        "task_id": "a" * 24,
        "title": "报告",
        "sections": [{"id": "s", "heading": "结论", "text": "有限结论。", "citations": []}],
        "sources": [],
        "artifacts": [],
    }
    for fmt in ("html", "docx"):
        data = ("checked-" + fmt).encode()
        (output / ("research-report-test." + fmt)).write_bytes(data)
        payload["artifacts"].append(
            {"name": "research-report-test." + fmt, "sha256": hashlib.sha256(data).hexdigest()}
        )
    (output / "research-report.json").write_text(json.dumps(payload))
    digest = hashlib.sha256((output / "research-report.json").read_bytes()).hexdigest()
    anchor = archive_report_version(output, "a" * 24)
    receipt = {
        "research_contract": {"task_id": "a" * 24},
        "quality_checks": {"check": {"status": "incomplete", "report_content_sha256": digest}},
        "quality_archives": {anchor["version_id"]: {"anchor": anchor, "check_id": "check"}},
    }
    return SimpleNamespace(store=store), sid, output, receipt, digest


def test_only_matching_aliases_resolve_to_checked_archive(tmp_path):
    service, sid, output, receipt, digest = fixture(tmp_path)
    (output / "报告.html").write_bytes(b"stale-html")
    (output / "copy.docx").write_bytes(b"checked-docx")
    result = report_delivery(service, sid, receipt, digest)
    assert result["status"] == "bound"
    assert "outputs/报告.html" not in result["aliases"]
    assert "outputs/copy.docx" in result["aliases"]
    assert all("report-versions" in f["path"] for f in result["files"])
    assert all(f["sha256"] for f in result["files"])


def test_unchecked_changed_and_tampered_reports_have_no_delivery_links(tmp_path):
    service, sid, output, receipt, digest = fixture(tmp_path)
    assert report_delivery(service, sid, {}, digest)["files"] == []
    (output / "research-report.json").write_text("{}")
    assert report_delivery(service, sid, receipt, digest)["files"] == []


def test_tampered_archive_cannot_supply_links(tmp_path):
    service, sid, output, receipt, digest = fixture(tmp_path)
    anchor = next(iter(receipt["quality_archives"].values()))["anchor"]
    item = next(f for f in anchor["files"] if f["name"].endswith(".html"))
    path = output / anchor["directory"] / item["stored_name"]
    path.chmod(0o600)
    path.write_bytes(b"changed")
    assert report_delivery(service, sid, receipt, digest)["files"] == []


def test_version_list_includes_current_and_unbound_invalid_previous_draft(tmp_path):
    service, sid, output, receipt, _digest = fixture(tmp_path)
    old = next(iter(receipt["quality_archives"].values()))["anchor"]
    receipt["quality_archives"] = {}
    receipt["quality_checks"]["check"]["status"] = "invalid"
    current = json.loads((output / "research-report.json").read_text())
    current["title"] = "修订报告"
    (output / "research-report.json").write_text(json.dumps(current))
    new_digest = hashlib.sha256((output / "research-report.json").read_bytes()).hexdigest()
    new = archive_report_version(output, "a" * 24)
    receipt["quality_checks"]["new"] = {"status": "incomplete", "report_content_sha256": new_digest}
    receipt["quality_archives"][new["version_id"]] = {"anchor": new, "check_id": "new"}
    service.store.data["receipts"][sid + ":turn"] = receipt
    service.store.files(sid)
    versions = quality_versions(service, sid)
    assert len(versions) == 2
    prior = next(v for v in versions if v["version_id"] == old["version_id"])
    assert prior["quality_binding"] == "unbound" and not prior["is_current"]
    assert prior["quality"]["status"] == "invalid"
    assert "report_version_quality_unbound" in prior["quality"]["issues"]
    assert next(v for v in versions if v["is_current"])["quality"]["status"] == "incomplete"


def test_old_alias_volume_does_not_hide_verified_current_archive(tmp_path):
    service, sid, output, receipt, digest = fixture(tmp_path)
    for i in range(70):
        (output / f"old-{i}.html").write_text("old")
    result = report_delivery(service, sid, receipt, digest)
    assert result["status"] == "bound"
    assert all(result["aliases"][f["url"]] == f["url"] for f in result["files"])


def test_removed_optional_alias_does_not_hide_checked_files(tmp_path):
    service, sid, output, receipt, digest = fixture(tmp_path)
    stale = output / "removed.html"
    stale.write_text("old")
    service.store.files(sid)
    stale.unlink()
    assert report_delivery(service, sid, receipt, digest)["status"] == "bound"


def test_current_archive_is_not_limited_by_history_display_window(tmp_path, monkeypatch):
    from app.research_web import research_quality_service

    service, sid, _output, receipt, digest = fixture(tmp_path)
    # The history API may legally omit the current version from its 20-row page.
    monkeypatch.setattr(research_quality_service, "list_report_versions", lambda *a: [])
    assert report_delivery(service, sid, receipt, digest)["status"] == "bound"
