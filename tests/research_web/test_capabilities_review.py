"""Regression evidence for the four scoped Task 2 review findings."""

import base64
import importlib.metadata
import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from test_capabilities import api as api_fixture
from test_capabilities import candidate, create
from test_capabilities_admission import discovery

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.packages import encode_file

api = api_fixture


@pytest.mark.parametrize("invalid", ["dependency", "workflow_binding"])
def test_automatic_discovery_checks_all_enabled_packages_before_send(api, monkeypatch, invalid):
    client, native, service = api
    value = candidate()
    if invalid == "dependency":
        value["metadata"]["dependencies"] = ["pydantic>=1"]
    cid = create(client, value)["id"]
    base = f"/api/research/capabilities/{cid}"
    assert client.post(base + "/publish").status_code == 200
    if invalid == "workflow_binding":
        flow = candidate(name="版本关联流程", slug="version-flow")
        flow.update(
            kind="workflow",
            instructions="",
            steps=[{"title": "研究", "instruction": "载入关联技能", "skill_id": cid, "tools": []}],
        )
        fid = create(client, flow)["id"]
        assert client.post(f"/api/research/capabilities/{fid}/publish").status_code == 200
        client.patch(base + "/draft", json=value)
        assert client.post(base + "/publish").status_code == 200
        expected = "linked_version_conflict"
    else:
        original = importlib.metadata.version

        def unavailable(name):
            if name == "pydantic":
                raise importlib.metadata.PackageNotFoundError(name)
            return original(name)

        monkeypatch.setattr(importlib.metadata, "version", unavailable)
        expected = "blocked_dependencies"
    discovery(native, service)
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "未选择具体能力的研究"},
        headers={"Idempotency-Key": "unselected-invalid-package"},
    )
    assert response.status_code in {400, 409, 422}, response.text
    assert response.json()["error"]["code"] == expected
    assert not any(method == "session.prompt" for method, _ in native.calls)
    assert not (service.store.directory(sid) / "resources/capabilities").exists()


@pytest.mark.parametrize("suffix", ["png", "jpg", "gif", "webp", "pdf", "svg"])
@pytest.mark.parametrize(
    "payload",
    [
        b"PK\x05\x06" + b"\x00" * 18,
        b"\xfe\xed\xfa\xce" + b"\x00" * 24,
        b"\xce\xfa\xed\xfe" + b"\x00" * 24,
        b"\xfd7zXZ\x00" + b"\x00" * 24,
        b"not an image or PDF",
    ],
)
def test_media_requires_matching_format_evidence(suffix, payload):
    with pytest.raises(CapabilityError):
        encode_file(f"reference.{suffix}", payload)


def test_disguised_resource_is_reported_by_zip_import_without_publication(api):
    client, _, service = api
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("SKILL.md", candidate()["instructions"])
        archive.writestr("capability.json", json.dumps(candidate()["metadata"]))
        archive.writestr("reference.png", b"PK\x05\x06" + b"\0" * 18)
    row = client.post(
        "/api/research/capabilities/import", files={"file": ("review.zip", blob.getvalue())}
    ).json()
    assert row["status"] == "invalid"
    assert any(issue["path"] == "reference.png" for issue in row["checks"]["issues"])
    assert client.post(f"/api/research/capabilities/{row['id']}/publish").status_code == 422
    assert not (service.capabilities.root / "versions" / row["id"]).exists()


@pytest.mark.parametrize(
    "paths",
    [
        ["note.md", "note.md/child.md"],
        ["note.md/child.md", "note.md"],
        ["NOTE.md", "note.md/child.md"],
        ["SKILL.md/child.md"],
        ["capability.json/child.md"],
    ],
)
def test_file_directory_prefix_conflicts_fail_draft_check(api, paths):
    client, _, _ = api
    value = candidate()
    value["files"] = [{"path": path, "content": "资源"} for path in paths]
    cid = create(client, value)["id"]
    base = f"/api/research/capabilities/{cid}"
    check = client.post(base + "/check").json()
    assert not check["valid"]
    assert any(issue["code"] == "path_conflict" for issue in check["issues"])
    assert client.post(base + "/publish").status_code == 422


@pytest.mark.parametrize("phase", ["write", "promote", "seal"])
def test_partial_version_write_retains_draft_and_retries_without_overwriting_history(
    api, monkeypatch, phase
):
    client, _, service = api
    cid = create(client)["id"]
    catalog = service.capabilities
    catalog.publish(cid)
    original = (catalog.version_path(cid, 1) / "SKILL.md").read_bytes()
    value = candidate()
    value["instructions"] += "\n第二版"
    client.patch(f"/api/research/capabilities/{cid}/draft", json=value)
    real_open = Path.open
    real_rename = os.rename
    real_chmod = Path.chmod

    def fail_resource_write(path, *args, **kwargs):
        if path.name == "report.md" and args and args[0] == "xb":
            raise OSError("injected bounded write failure")
        return real_open(path, *args, **kwargs)

    def fail_promote(source, destination):
        if destination.name == "2":
            raise OSError("injected promotion failure")
        return real_rename(source, destination)

    def fail_seal(path, mode, **kwargs):
        if path.name == "2" and mode == 0o555:
            raise OSError("injected immutable seal failure")
        return real_chmod(path, mode, **kwargs)

    with monkeypatch.context() as patch:
        if phase == "write":
            patch.setattr(Path, "open", fail_resource_write)
        elif phase == "promote":
            patch.setattr(os, "rename", fail_promote)
        else:
            patch.setattr(Path, "chmod", fail_seal)
        with pytest.raises(CapabilityError) as error:
            catalog.publish(cid)
        assert error.value.status == 503
    assert not (catalog.root / "versions" / cid / "2").exists()
    assert catalog.detail(cid)["has_draft"]
    assert catalog.detail(cid)["version"] == 1
    restored = CapabilityCatalog(service.store.root)
    assert restored.publish(cid)["version"] == 2
    assert (restored.version_path(cid, 1) / "SKILL.md").read_bytes() == original
    assert (restored.version_path(cid, 2) / "templates/report.md").read_text() == "# 研究报告"
    assert not restored.version_path(cid, 2).stat().st_mode & 0o222


@pytest.mark.parametrize("directory_first", [True, False])
def test_zip_empty_directory_conflicting_with_file_is_reported(api, directory_first):
    client, _, _ = api
    blob = io.BytesIO()
    entries = [("note.md/", ""), ("note.md", "资料")]
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("SKILL.md", candidate()["instructions"])
        archive.writestr("capability.json", json.dumps(candidate()["metadata"]))
        for name, content in entries if directory_first else reversed(entries):
            archive.writestr(name, content)
    row = client.post(
        "/api/research/capabilities/import", files={"file": ("review.zip", blob.getvalue())}
    ).json()
    assert row["status"] == "invalid"
    assert any(issue["code"] == "path_conflict" for issue in row["checks"]["issues"])


def test_media_header_alone_is_not_a_gif_or_pdf():
    for name, raw in (
        ("bad.gif", b"GIF89a\x01\x00\x01\x00" + b"\0" * 24 + b",\x00;"),
        ("bad.pdf", b"%PDF-1.7\nempty\n%%EOF"),
    ):
        with pytest.raises(CapabilityError):
            encode_file(name, raw)


@pytest.mark.parametrize("field", ["name", "slug"])
def test_rollback_rechecks_historical_name_uniqueness_without_switching(api, field):
    client, _, service = api
    cid = create(client)["id"]
    base = f"/api/research/capabilities/{cid}"
    client.post(base + "/publish")
    renamed = candidate(name="改名研究", slug="renamed-research")
    client.patch(base + "/draft", json=renamed)
    assert client.post(base + "/publish").json()["version"] == 2
    other = candidate(name="其他研究", slug="other-research")
    other["metadata"][field] = candidate()["metadata"][field]
    if field == "slug":
        other["instructions"] = candidate()["instructions"]
    create(client, other)
    before = set(service.capabilities.native_root.iterdir())
    response = client.post(base + "/rollback", json={"version": 1})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "name_conflict"
    assert client.get(base).json()["version"] == 2
    assert set(service.capabilities.native_root.iterdir()) == before
    assert CapabilityCatalog(service.store.root).detail(cid)["version"] == 2


def test_real_png_is_accepted_but_truncated_or_appended_data_is_not():
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
    )
    assert encode_file("reference.png", raw)["size"] == len(raw)
    for invalid in (raw[:16], raw + b"PK\x05\x06" + b"\0" * 18):
        with pytest.raises(CapabilityError):
            encode_file("reference.png", invalid)


@pytest.mark.parametrize(
    "suffix,encoded",
    [
        ("gif", "R0lGODdhAQABAIEAAP///wAAAAAAAAAAACwAAAAAAQABAAAIBAABBAQAOw=="),
        ("webp", "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAUAmJaQAA3AA/vz0AAA="),
        (
            "jpg",
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q==",
        ),
    ],
)
def test_real_media_samples_are_allowed_without_decoder_dependency(suffix, encoded):
    raw = base64.b64decode(encoded)
    assert encode_file(f"reference.{suffix}", raw)["size"] == len(raw)
    with pytest.raises(CapabilityError):
        encode_file(f"reference.{suffix}", raw[:16])


def test_real_svg_and_pdf_container_evidence():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1"/></svg>'
    assert encode_file("reference.svg", svg)["size"] == len(svg)
    header = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    page_offset = len(header)
    objects = header + b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    pdf = (
        objects
        + (
            "xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n"
            f"{page_offset:010d} 00000 n \ntrailer\n<< /Size 3 /Root 1 0 R >>\n"
            f"startxref\n{len(objects)}\n%%EOF\n"
        ).encode()
    )
    assert encode_file("reference.pdf", pdf)["size"] == len(pdf)
    with pytest.raises(CapabilityError):
        encode_file("reference.pdf", pdf.replace(b"startxref", b"invalidxx"))
    with pytest.raises(CapabilityError):
        encode_file("reference.svg", b'<!DOCTYPE svg [<!ENTITY x "nested">]><svg>&x;</svg>')
    with pytest.raises(CapabilityError):
        encode_file("reference.svg", b'<?xml version="1.0" encoding="unknown-encoding"?><svg/>')
