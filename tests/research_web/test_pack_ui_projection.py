"""Public detail reads retain real Host qualification and artifact boundaries."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import test_pack_execution_host as native_fixtures

from app.research_web.sandbox import SandboxConfig, run_script

api = native_fixtures.api
admitted = native_fixtures.admitted


def test_catalog_form_schema_projects_only_research_parameters(api):
    client, service = api
    before = set(service.store.data["sessions"])
    rows = client.get("/api/research/scenarios").json()["items"]
    packs = [row for row in rows if row.get("pack_id")]
    assert len(packs) == 9
    assert set(service.store.data["sessions"]) == before
    for row in packs:
        assert row["ui_methods"]
        for method in row["ui_methods"]:
            assert not {"category_coverage", "owner", "rights", "records", "passed"} & {
                field["name"] for field in method["fields"]
            }


def test_foreign_store_session_does_not_expose_result_files(api, tmp_path):
    from app.research_web.store import Store

    client, _service = api
    foreign = Store(tmp_path / "other-account")
    row = foreign.create("fingpt", "private foreign pack")
    private = foreign.directory(row["id"]) / "outputs" / "full-result.json"
    private.write_text('{"private":"FOREIGN_BODY_MUST_NOT_LEAK"}')
    file = foreign.files(row["id"])[0]
    for url, status in ((f'/api/research/sessions/{row["id"]}', 400), (file["url"], 409)):
        response = client.get(url)
        assert response.status_code == status
        assert "FOREIGN_BODY_MUST_NOT_LEAK" not in response.text
        assert "research_pack" not in response.json()


@pytest.mark.skipif(sys.platform != "darwin", reason="Real macOS Native sandbox")
def test_real_detail_projection_saved_unknown_corrupt_and_revoked(api, monkeypatch):
    client, service, sid, context, descriptor, headers = admitted(api, monkeypatch)
    empty = client.get(f"/api/research/sessions/{sid}")
    assert empty.status_code == 200, empty.text
    assert empty.json()["research_pack"]["executions"] == []
    loaded = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "tool_name": "skill",
            "native_name": "research-pack-event-review",
            "loaded": True,
        },
        headers=headers,
    )
    assert loaded.status_code == 200, loaded.text
    response = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "tool_name": "research_run_script",
            "pack_execution": descriptor,
            "call_id": "ui-real-call",
            "pack_start": True,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    scope = response.json()
    unknown = client.get(f"/api/research/sessions/{sid}")
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["research_pack"]["executions"] == [{"state": "unknown", "files": []}]
    root = service.store.root
    native = run_script(
        SandboxConfig(root, Path(sys.executable)),
        root / "sessions" / sid,
        scope["code"],
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
        file_bindings=scope["file_bindings"],
        output_root=scope["output_root"],
    )
    assert native.status == "completed", (native.stderr, native.error)
    saved = client.post(
        "/api/research/internal/data/pack-completion",
        json={
            "session_id": sid,
            "execution_id": scope["binding"]["execution_id"],
            "call_id": "ui-real-call",
            "result": asdict(native),
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    detail = client.get(f"/api/research/sessions/{sid}")
    assert detail.status_code == 200, detail.text
    public = detail.json()["research_pack"]["executions"][0]
    assert public["state"] == "saved"
    assert public["computation_status"] != "complete"
    assert {file["name"] for file in public["files"]} == {
        "receipt.json",
        "manifest.json",
        "full-result.json",
    }
    assert all(
        file in detail.json()["files"]
        or any(
            file["id"] == indexed["id"] and file["url"] == indexed["url"]
            for indexed in detail.json()["files"]
        )
        for file in public["files"]
    )
    assert all(client.get(file["url"]).status_code == 200 for file in public["files"])
    assert not {"binding", "scope", "code", "output_root", "native_result"} & set(public)
    output = root / "sessions" / sid / scope["output_root"] / "v1" / "receipt.json"
    original = output.read_bytes()
    output.chmod(0o600)
    output.write_text(json.dumps({"status": "complete"}))
    invalid = client.get(f"/api/research/sessions/{sid}")
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["research_pack"]["executions"] == [{"state": "invalid", "files": []}]
    output.write_bytes(original)
    output.chmod(0o400)
    source = context["references"][0]["source_session_id"]
    service.store.session(source)["source_scope"] = ["web"]
    service.store.save()
    revoked = client.get(f"/api/research/sessions/{sid}")
    assert revoked.status_code == 403, revoked.text
    assert "research_pack" not in revoked.json()
    assert client.get(public["files"][0]["url"]).status_code == 403
    missing = client.get("/api/research/sessions/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 400
    assert "research_pack" not in missing.json()
