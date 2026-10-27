"""Real archived source bytes through current owned reader/seal/Native chain."""

import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import test_pack_execution_host as native_tests
import test_scenario_handoffs as scenario_fixtures

from app.research_web import research_web_sources as reader
from app.research_web.resources.research_report import source_id
from app.research_web.scenario_handoffs import resolve_reference
from app.research_web.scenario_pack_inputs import qualify_pack_materials
from app.research_web.store import StoreError

api = scenario_fixtures.api
FIXTURE = Path(__file__).parent / "fixtures/pack-owned-source-v1"


def captured_source(api, monkeypatch):
    client, service = api
    meta = json.loads((FIXTURE / "manifest.json").read_bytes())
    raw = (FIXTURE / "body.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["body_sha256"]
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    identifier = source_id(meta["origin"])

    async def fetch(url):
        assert url == meta["origin"]
        return {
            "content": raw.decode("utf-8"),
            "as_of": meta["publication_date"],
            "date_evidence": [
                {
                    "date": meta["publication_date"],
                    "kind": "publication_meta",
                    "text": meta["publication_date"],
                }
            ],
            "final_url": url,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(reader, "fetch_owned_document", fetch)
    actual = asyncio.run(
        reader.read_source(
            service,
            sid,
            "read",
            identifier,
            search_activities=[
                {
                    "id": "actual-source-search",
                    "title": "web_search",
                    "status": "completed",
                    "detail": json.dumps(
                        {"results": [{"title": meta["title"], "url": meta["origin"]}]}
                    ),
                }
            ],
        )
    )
    assert actual["source"]["sha256"] == meta["body_sha256"]
    metadata = resolve_reference(service, sid, {"type": "source", "id": identifier})[0]
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    values = {
        "subject": {"kind": "stock", "identity": "600600.SH"},
        "as_of": day,
        "question": "核对本人原文版本，保留未知角色与时点",
        "material_ids": [],
        "research_scope": {"cutoff_at": day + "T23:59:59+08:00"},
    }
    return client, service, sid, identifier, metadata, values, actual


@pytest.mark.parametrize("pack", ["research-prep", "global-opinion"])
def test_owned_capture_maps_real_bytes_without_inventing_source_semantics(api, monkeypatch, pack):
    _, service, sid, identifier, metadata, values, actual = captured_source(api, monkeypatch)
    result = qualify_pack_materials(service, pack, values, [metadata])
    assert result.status == "partial"
    record = result.input["records_by_kind"]["source-version"][0]
    assert record["content_sha256"] == metadata["sha256"]
    assert record["source_role"] == record["language"] == record["region"] == "unknown"
    assert record["origin"]["published_at"] is None
    assert record["event_at"] is None and record["parent_version_id"] is None
    assert record["full_text_available"] is True
    assert actual["truncated"] is True  # model preview != full saved capture
    assert record["origin"]["locator"]["resource_id"] == f"{sid}:{identifier}"
    assert not result.input["source_coverage"]
    assert {
        "source_language_unknown",
        "source_region_unknown",
        "source_publication_instant_unknown",
        "upstream_completeness_unverified",
    } <= {gap["code"] for gap in result.missing}


@pytest.mark.parametrize(
    "change",
    ["revoked", "changed", "foreign", "unknown_observation", "legacy_capture", "truncated_capture"],
)
def test_owned_source_authority_and_capture_gaps(api, monkeypatch, change):
    _, service, sid, identifier, metadata, values, _ = captured_source(api, monkeypatch)
    source = service.store.session(sid)["web_evidence"][identifier]
    if change == "revoked":
        service.store.session(sid)["source_scope"] = ["uploads", "datahub"]
    elif change == "changed":
        (service.store.directory(sid) / source["path"]).write_bytes(b"changed capture")
    elif change == "foreign":
        metadata["source_session_id"] = str(uuid4())
    elif change == "unknown_observation":
        source["fetched_at"] = None
        metadata = resolve_reference(service, sid, {"type": "source", "id": identifier})[0]
    elif change == "legacy_capture":
        source.pop("response_sha256")
    else:
        source["truncated"] = True
    if change in {"revoked", "changed", "foreign"}:
        with pytest.raises(StoreError):
            qualify_pack_materials(service, "research-prep", values, [metadata])
    else:
        result = qualify_pack_materials(service, "research-prep", values, [metadata])
        if change == "unknown_observation":
            assert result.status == "blocked"
            assert "source_observation_instant_unknown" in {gap["code"] for gap in result.missing}
        else:
            assert (
                result.input["records_by_kind"]["source-version"][0]["full_text_available"] is False
            )
            assert "source_capture_completeness_unknown" in {gap["code"] for gap in result.missing}


def source_handoff(api, monkeypatch, pack="research-prep", *, send=True):
    client, service, sid, identifier, metadata, values, _ = captured_source(api, monkeypatch)
    text = (FIXTURE / "body.txt").read_text()
    quote = text[:100]
    bundle = {
        "schema": "asset-research-workspace/v1",
        "subject": values["subject"]["identity"],
        "summaries": [
            {
                "id": "owned-capture",
                "title": "本人原文定位",
                "text": quote,
                "evidence": [
                    {
                        "source_session_id": sid,
                        "reference": {"type": "source", "id": identifier},
                        "sha256": metadata["sha256"],
                        "locator": {"kind": "text", "start": 0, "end": len(quote), "quote": quote},
                    }
                ],
            }
        ],
        "relations": [],
    }
    raw = json.dumps(bundle, ensure_ascii=False).encode()
    (service.store.directory(sid) / "inputs/owned-bundle.json").write_bytes(raw)
    file = next(item for item in service.store.files(sid) if item["name"] == "owned-bundle.json")
    body = {
        "source_session_id": sid,
        "target_mode": "fingpt",
        "section": "assets",
        "dataset_ids": [],
        "source_scope": ["datahub", "uploads", "web"],
        "workspace_material": {
            "source_session_id": sid,
            "file_id": file["id"],
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "scenario_id": "pack-" + pack,
        "scenario_inputs": {**values, "material_ids": ["file:" + file["id"]]},
    }
    preview = client.post("/api/research/scenarios/pack-" + pack + "/prepare", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["pack_qualification"]["status"] == "partial"
    response = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "actual-source-handoff"}
    )
    assert response.status_code == 201, response.text
    target, context = response.json()["session_id"], response.json()["scenario_context"]
    if not send:
        return client, service, target, context, sid
    original = service.client.rpc

    async def rpc(method, payload):
        if method == "skill.list":
            return {
                "skills": [
                    {"name": p.name} for p in service.capabilities.prepare_native_root().iterdir()
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    assert service._model_tools_verified(target)
    sent = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": "执行封印原件版本去重", "expected_formats": []},
        headers={"Idempotency-Key": "actual-source-send"},
    )
    assert sent.status_code == 202, sent.text
    from app.research_web.scenario_handoffs import fingerprint

    descriptor = {
        "capability_id": context["pack_seal"]["capability_id"],
        "version": context["pack_seal"]["version"],
        "context_sha256": fingerprint(context),
        "input_manifest_sha256": context["pack_seal"]["manifest_sha256"],
    }
    return (
        client,
        service,
        target,
        context,
        descriptor,
        {"X-Research-Data-Key": service.datahub.control["token"]},
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Native macOS sandbox")
@pytest.mark.parametrize("pack", ["research-prep", "global-opinion"])
def test_actual_owned_source_host_dsh_toolruntime_sandbox_and_readback(
    api, monkeypatch, tmp_path, pack
):
    captured = source_handoff(api, monkeypatch, pack)
    monkeypatch.setattr(native_tests, "admitted", lambda *_args: captured)
    native_tests.test_actual_dsh_skill_guard_toolruntime_host_and_sandbox(
        api, monkeypatch, tmp_path, False
    )
    client, service, sid, context, _, _ = captured
    receipt = service._task_capabilities(sid)[0]
    execution = receipt["pack_executions"][0]
    full = json.loads(
        (
            service.store.directory(sid) / execution["output_root"] / "v1/full-result.json"
        ).read_bytes()
    )
    component = full["components"][0]
    assert component["method_version"] == "1.1.0"
    assert component["metrics"]["versions"] == 1
    assert component["rows"][0]["versions"][0]["source_role"] == "unknown"
    assert component["research_quality"] == "NOT_RUN"
    assert {"source_role_unknown", "publication_unknown"} <= {
        gap["code"] for gap in component["missing"]
    }
    source = next(ref for ref in context["references"] if ref["reference"]["type"] == "source")
    service.store.session(source["source_session_id"])["source_scope"] = ["datahub", "uploads"]
    assert client.get(f"/api/research/sessions/{sid}").status_code == 403


def test_duplicate_reference_is_not_a_second_capture(api, monkeypatch):
    _, service, _, _, metadata, values, _ = captured_source(api, monkeypatch)
    result = qualify_pack_materials(service, "research-prep", values, [metadata, dict(metadata)])
    assert len(result.input["records_by_kind"]["source-version"]) == 1
    assert any(
        t["mapping"] == "owned-source-reference-deduplicate-v1" for t in result.transformations
    )


def test_same_hash_distinct_captures_keep_both_owned_locations(api, monkeypatch):
    first = captured_source(api, monkeypatch)
    second = captured_source(api, monkeypatch)
    _, service, _, _, one, values, _ = first
    two = second[4]
    result = qualify_pack_materials(service, "research-prep", values, [one, two])
    rows = result.input["records_by_kind"]["source-version"]
    assert len(rows) == 2 and rows[0]["version_id"] != rows[1]["version_id"]
    assert rows[0]["content_sha256"] == rows[1]["content_sha256"]
    assert rows[0]["origin"]["observed_at"] != rows[1]["origin"]["observed_at"]
    assert rows[0]["origin"]["locator"] != rows[1]["origin"]["locator"]
    from app.research_web.scenarios.packs import execute_pack_bundle

    bundle = execute_pack_bundle(
        "research-prep", result.input["records_by_kind"], result.input["parameters"]
    )
    full = json.loads(bundle.full_result.canonical_json)
    assert full["components"][0]["metrics"]["version_groups"] == 1
    assert full["components"][0]["metrics"]["versions"] == 2


def test_missing_source_materials_remain_blocked(api):
    from app.research_web.scenarios.packs import execute_pack_bundle

    _, service = api
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    result = qualify_pack_materials(
        service,
        "research-prep",
        {"as_of": day, "research_scope": {"cutoff_at": day + "T23:59:59+08:00"}},
        [],
    )
    assert result.status == "blocked"
    assert "required_kind_missing" in {gap["code"] for gap in result.missing}
    bundle = execute_pack_bundle(
        "research-prep", result.input["records_by_kind"], result.input["parameters"]
    )
    assert bundle.receipt["status"] == "insufficient_data"
    assert bundle.receipt["research_quality"] == "NOT_RUN"


@pytest.mark.parametrize("change", ["source_scope", "target_scope", "raw", "observed"])
def test_sealed_source_rechecks_each_owner_scope_and_original_bytes(api, monkeypatch, change):
    client, service, target, context, original = source_handoff(api, monkeypatch, send=False)
    source = next(ref for ref in context["references"] if ref["reference"]["type"] == "source")
    row = service.store.session(original)
    saved = row["web_evidence"][source["reference"]["id"]]
    if change == "source_scope":
        row["source_scope"] = ["datahub", "uploads"]
    elif change == "target_scope":
        service.store.session(target)["source_scope"] = ["datahub", "uploads"]
    elif change == "observed":
        saved["fetched_at"] = "2026-01-01T00:00:00Z"
    else:
        raw = b"replacement original cannot update old seal"
        (service.store.directory(original) / saved["path"]).write_bytes(raw)
        saved["sha256"] = hashlib.sha256(raw).hexdigest()
    from app.research_web.scenario_handoffs import trusted_context

    with pytest.raises(StoreError):
        trusted_context(service, target, check_capabilities=False)
    assert client.get(f"/api/research/sessions/{target}").status_code in {403, 409}


def test_actual_other_account_reference_cannot_become_local_source(api, monkeypatch, tmp_path):
    from app.research_web.store import Store

    _, service, _, _, metadata, values, _ = captured_source(api, monkeypatch)
    other = Store(tmp_path / "different-account")
    foreign = other.create("fingpt", "another account original")
    metadata["source_session_id"] = foreign["id"]
    with pytest.raises(StoreError):
        qualify_pack_materials(service, "research-prep", values, [metadata])


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Native macOS sandbox")
def test_actual_source_native_cancellation_retains_unknown_no_retry(api, monkeypatch, tmp_path):
    captured = source_handoff(api, monkeypatch)
    monkeypatch.setattr(native_tests, "admitted", lambda *_args: captured)
    native_tests.test_actual_dsh_skill_guard_toolruntime_host_and_sandbox(
        api, monkeypatch, tmp_path, True
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Native macOS sandbox")
def test_actual_failed_source_sandbox_does_not_certify_or_retry(api, monkeypatch):
    from dataclasses import asdict

    from app.research_web.sandbox import SandboxConfig, run_script

    client, service, sid, _context, descriptor, headers = source_handoff(api, monkeypatch)
    loaded = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "tool_name": "skill",
            "native_name": descriptor["capability_id"],
            "loaded": True,
        },
        headers=headers,
    )
    assert loaded.status_code == 200, loaded.text
    admission = {
        "session_id": sid,
        "tool_name": "research_run_script",
        "pack_execution": descriptor,
        "call_id": "source-failure",
        "pack_start": True,
    }
    response = client.post(
        "/api/research/internal/data/skill-preflight", json=admission, headers=headers
    )
    assert response.status_code == 200, response.text
    scope = response.json()
    session = service.store.directory(sid)
    # An actual approved sandbox process reaches the immutable writer, which
    # must refuse an already existing output directory rather than overwrite.
    (session / scope["output_root"] / "v1").mkdir()
    actual = run_script(
        SandboxConfig(service.store.root, Path(sys.executable)),
        session,
        scope["code"],
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
        file_bindings=scope["file_bindings"],
        output_root=scope["output_root"],
    )
    assert actual.status == "failed" and "output_exists" in actual.stderr
    completed = client.post(
        "/api/research/internal/data/pack-completion",
        json={
            "session_id": sid,
            "execution_id": scope["binding"]["execution_id"],
            "call_id": "source-failure",
            "result": asdict(actual),
        },
        headers=headers,
    )
    assert completed.status_code == 200
    assert service._task_capabilities(sid)[0]["pack_executions"][0]["state"] == "failed"
    assert service._task_capabilities(sid)[0]["pack_executions"][0]["state"] != "saved"
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**admission, "call_id": "cannot-retry-failed-source"},
        headers=headers,
    )
    assert retry.status_code == 409


def test_current_capture_cannot_certify_historical_pit(api, monkeypatch):
    _, service, _, _, metadata, values, _ = captured_source(api, monkeypatch)
    values["as_of"] = "2026-02-28"
    values["research_scope"]["cutoff_at"] = "2026-02-28T23:59:59+08:00"
    result = qualify_pack_materials(service, "research-prep", values, [metadata])
    assert result.status == "blocked"
    assert "source_observed_after_cutoff" in {gap["code"] for gap in result.missing}
