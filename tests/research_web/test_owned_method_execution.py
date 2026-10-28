"""Real source capture, Host freeze, sandbox and private completion; model NOT_RUN."""

import asyncio
import copy
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import test_scenario_handoffs as scenario_fixtures
from source_capture_fixture import fixed_response, offline_http
from test_api import isolated_keyring  # noqa: F401

from app.research_web import research_web_sources as reader
from app.research_web.resources.research_report import source_id
from app.research_web.sandbox import SandboxConfig, run_script
from app.research_web.scenario_handoffs import fingerprint, resolve_reference
from app.research_web.scenario_method_sources import quality_issues
from app.research_web.store import StoreError

api = scenario_fixtures.api
FIXTURES = Path(__file__).parent / "fixtures" / "business-evidence"


def prepared(
    api, monkeypatch, cid="owned-news-evidence", *, cutoff=False, preset=None, transform=None
):
    client, service = api
    filename = {
        "owned-news-evidence": "fomc-september.txt",
        "owned-company-evidence": "msft-income.txt",
        "owned-research-prep": "msft-cashflows.txt",
    }[cid]
    meta = next(
        row
        for row in json.loads((FIXTURES / "sources.json").read_bytes())["inputs"]
        if row["file"] == filename
    )
    raw = (FIXTURES / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
    if transform is not None:
        raw = transform(raw)
    captured_sha256 = hashlib.sha256(raw).hexdigest()
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    identifier = source_id(meta["origin"])
    offline_http(monkeypatch, fixed_response(raw))
    actual = asyncio.run(
        reader.read_source(
            service,
            sid,
            "read",
            identifier,
            search_activities=[
                {
                    "id": "method-source-search",
                    "title": "web_search",
                    "status": "completed",
                    "detail": json.dumps({"results": [{"title": filename, "url": meta["origin"]}]}),
                }
            ],
        )
    )
    assert actual["source"]["sha256"] == captured_sha256
    metadata = resolve_reference(service, sid, {"type": "source", "id": identifier})[0]
    day = (
        datetime.fromisoformat(metadata["acquired_at"])
        .astimezone(ZoneInfo("Asia/Shanghai"))
        .date()
        .isoformat()
    )
    body = {
        "handoff": {
            "source_session_id": sid,
            "target_mode": "fingpt",
            "section": "documents",
            "source_scope": ["datahub", "uploads", "web"],
            "scenario_id": cid,
            "scenario_inputs": {
                "subject": {"kind": "stock", "identity": "MSFT.US"},
                "as_of": day,
                "question": "核验已取得原件与缺口",
                "material_ids": [],
                **({"cutoff_at": metadata["acquired_at"]} if cutoff else {}),
                **(
                    {"question_preset": preset, "preset_query": "核验已取得原件与缺口"}
                    if preset
                    else {}
                ),
            },
        },
        "sources": [{"source_session_id": sid, "id": identifier, "sha256": metadata["sha256"]}],
    }
    preview = client.post("/api/research/source-selections/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["qualification"]["kind"] == "owned-method"
    frozen = client.post(
        "/api/research/source-selections/freeze",
        json={**body, "preview_sha256": preview.json()["preview_sha256"]},
        headers={"Idempotency-Key": "method-source-freeze"},
    )
    assert frozen.status_code == 200, frozen.text
    target, context = frozen.json()["session_id"], frozen.json()["scenario_context"]
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
    sent = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": "执行已选方法", "expected_formats": []},
        headers={"Idempotency-Key": "owned-method-send"},
    )
    assert sent.status_code == 202, sent.text
    descriptor = {"capability_id": cid, "version": 1, "context_sha256": fingerprint(context)}
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    return client, service, target, context, descriptor, headers, (sid, identifier)


def start(client, target, descriptor, headers):
    load = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": target,
            "native_name": descriptor["capability_id"],
            "tool_name": "skill",
            "loaded": True,
        },
        headers=headers,
    )
    assert load.status_code == 200, load.text
    admission = {
        "session_id": target,
        "tool_name": "research_run_script",
        "method_execution": descriptor,
        "call_id": "actual-owned-method",
        "pack_start": True,
    }
    response = client.post(
        "/api/research/internal/data/skill-preflight", json=admission, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json(), admission


@pytest.mark.skipif(sys.platform != "darwin", reason="real macOS sandbox evidence")
@pytest.mark.parametrize(
    "cid", ["owned-company-evidence", "owned-news-evidence", "owned-research-prep"]
)
def test_real_source_action_native_sandbox_completion_and_quality_gap(api, monkeypatch, cid):
    client, service, sid, _context, descriptor, headers, _source = prepared(api, monkeypatch, cid)
    receipt, _ = service._task_capabilities(sid)
    assert quality_issues(service, sid, receipt) == ["method_execution_not_verified:" + cid]
    scope, admission = start(client, sid, descriptor, headers)
    root = service.store.root
    result = run_script(
        SandboxConfig(root, Path(sys.executable)),
        root / "sessions" / sid,
        scope["code"],
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
        file_bindings=scope["file_bindings"],
        output_root=scope["output_root"],
    )
    assert result.status == "completed", (result.stderr, result.error)
    completion = {
        "kind": "owned-method",
        "session_id": sid,
        "execution_id": scope["binding"]["execution_id"],
        "call_id": "actual-owned-method",
        "result": asdict(result),
    }
    assert (
        client.post("/api/research/internal/data/pack-completion", json=completion).status_code
        == 403
    )
    saved = client.post(
        "/api/research/internal/data/pack-completion", json=completion, headers=headers
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["state"] == "saved"
    assert saved.json()["research_quality"] == "NOT_RUN"
    assert not receipt.get("pack_executions")
    actual = receipt["method_executions"][0]
    assert actual["counts"]["checked_sources"] == 1
    assert actual["analysis_status"] == "incomplete"
    assert quality_issues(service, sid, receipt) == ["method_source_incomplete:" + cid]
    assert (
        client.post(
            "/api/research/internal/data/skill-preflight",
            json={**admission, "call_id": "new-call-no-retry"},
            headers=headers,
        ).status_code
        == 409
    )
    ledger = root / "sessions" / sid / actual["artifact"]["path"]
    ledger.chmod(0o600)
    ledger.write_text("{}")
    with pytest.raises(Exception, match="方法来源"):
        quality_issues(service, sid, receipt)


def test_portable_closed_descriptor_and_selection_are_required(api, monkeypatch):
    client, service, sid, _context, descriptor, headers, _source = prepared(api, monkeypatch)
    load = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "native_name": descriptor["capability_id"],
            "tool_name": "skill",
            "loaded": True,
        },
        headers=headers,
    )
    assert load.status_code == 200, load.text
    for override in [
        {"code": "pass"},
        {"path": "inputs/other.txt"},
        {"provider": "trusted"},
        {"rights": True},
        {"version": True},
    ]:
        response = client.post(
            "/api/research/internal/data/skill-preflight",
            json={
                "session_id": sid,
                "tool_name": "research_run_script",
                "method_execution": {**descriptor, **override},
                "call_id": "bad-descriptor",
                "pack_start": True,
            },
            headers=headers,
        )
        assert response.status_code == 409, response.text
    assert not service._task_capabilities(sid)[0].get("method_executions")


def test_method_internal_source_cannot_become_dossier_upload_alias(api, monkeypatch):
    client, service, sid, _context, descriptor, headers, source = prepared(api, monkeypatch)
    scope, _admission = start(client, sid, descriptor, headers)
    relative = next(
        item["path"] for item in scope["file_bindings"] if item["path"].endswith(".source")
    )
    if sys.platform == "darwin":
        config = SandboxConfig(service.store.root, Path(sys.executable))
        private_read = run_script(
            config, service.store.directory(sid), f"print(open({relative!r}).read())"
        )
        assert private_read.status == "failed" and "PermissionError" in private_read.stderr
        private_write = run_script(
            config,
            service.store.directory(sid),
            f"open({(scope['output_root'] + '/forged.json')!r},'w').write('{{}}')",
        )
        assert private_write.status == "failed" and "PermissionError" in private_write.stderr
    assert all(item.get("path") != relative for item in service.store.files(sid))
    fid = hashlib.sha256(relative.encode()).hexdigest()[:24]
    assert client.get(f"/api/research/sessions/{sid}/files/{fid}/preview").status_code in {400, 404}
    # Simulate an older cached FileInfo identity: path authority still rejects.
    service.store.session(sid)["files"][fid] = relative
    for action in ("preview", "download"):
        response = client.get(f"/api/research/sessions/{sid}/files/{fid}/{action}")
        assert response.status_code == 403, response.text
    with pytest.raises(StoreError) as rejected:
        service.dossiers._resolve(sid, {"type": "file", "id": relative})
    assert rejected.value.code == "dossier_evidence_alias_denied"
    dossier = client.post(
        "/api/research/dossiers",
        json={
            "title": "方法私有原件边界",
            "subject": {"kind": "company", "key": "MSFT.US", "label": "Microsoft"},
            "idempotency_key": "owned-private-alias-dossier",
        },
    )
    assert dossier.status_code == 201, dossier.text
    dossier_alias = client.post(
        f"/api/research/dossiers/{dossier.json()['id']}/evidence",
        json={
            "expected_revision": 1,
            "idempotency_key": "owned-private-alias-evidence",
            "source_session_id": sid,
            "reference": {"type": "file", "id": relative},
        },
    )
    assert dossier_alias.status_code == 403, dossier_alias.text
    target = client.post("/api/research/sessions", json={}).json()["id"]
    before = copy.deepcopy(service.store.session(target)["files"])
    copied = client.post(
        f"/api/research/sessions/{target}/file-references",
        json={
            "source_session_id": sid,
            "file_id": fid,
            "expected_sha256": next(
                item["sha256"] for item in scope["file_bindings"] if item["path"] == relative
            ),
        },
    )
    assert copied.status_code in {400, 403, 409}, copied.text
    assert service.store.session(target)["files"] == before
    # A half-written legacy .txt name must not use the Claw extension allowlist.
    half = service.store.directory(sid) / Path(relative).parent / "half.txt"
    half.write_text("partial original")
    half_id = hashlib.sha256(
        half.relative_to(service.store.directory(sid)).as_posix().encode()
    ).hexdigest()[:24]
    service.store.session(sid)["files"][half_id] = half.relative_to(
        service.store.directory(sid)
    ).as_posix()
    half_copy = client.post(
        f"/api/research/sessions/{target}/file-references",
        json={
            "source_session_id": sid,
            "file_id": half_id,
            "expected_sha256": hashlib.sha256(half.read_bytes()).hexdigest(),
        },
    )
    assert half_copy.status_code == 403, half_copy.text
    assert service.store.session(target)["files"] == before
    denied = client.post(
        "/api/research/internal/data/skill-preflight",
        json={"session_id": sid, "tool_name": "research_run_script"},
        headers=headers,
    )
    assert denied.status_code == 409
    half.unlink()
    # Losing the private call record cannot publish those bytes as a new source.
    receipt, _ = service._task_capabilities(sid)
    executions = receipt.pop("method_executions")
    denied = client.post(
        "/api/research/internal/data/skill-preflight",
        json={"session_id": sid, "tool_name": "research_run_script"},
        headers=headers,
    )
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "method_input_unbound"
    assert client.get(f"/api/research/sessions/{sid}/files/{fid}/preview").status_code == 403
    with pytest.raises(StoreError):
        service.dossiers._resolve(sid, {"type": "file", "id": relative})
    receipt["method_executions"] = executions
    source_sid, _ = source
    service.store.session(source_sid)["source_scope"] = ["datahub", "uploads"]
    assert client.get(f"/api/research/sessions/{sid}/files/{fid}/download").status_code == 403
    with pytest.raises(StoreError):
        service.dossiers._resolve(sid, {"type": "file", "id": relative})
    denied = client.post(
        "/api/research/internal/data/skill-preflight",
        json={"session_id": sid, "tool_name": "research_run_script"},
        headers=headers,
    )
    assert denied.status_code == 403


def test_financial_snapshot_retains_real_reporting_period_and_unit_gaps(api, monkeypatch):
    from test_datahub_financial_time_contract import query, replay

    from app.research_web.scenario_method_sources import source_context
    from app.research_web.skills._shared.source_actions import inspect_company_sources

    client, service = api
    request = query()
    parsed, calls = replay()
    assert calls and parsed.metadata["schema_version"] == "akshare-sina-financial-disclosure-v3"
    source = client.post("/api/research/sessions", json={}).json()["id"]
    snapshot = service.datahub.snapshots.publish(
        source,
        request,
        parsed,
        request_query=request,
        authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
    )
    body = {
        "source_session_id": source,
        "target_mode": "fingpt",
        "section": "assets",
        "dataset_ids": [snapshot["dataset_id"]],
        "scenario_id": "owned-company-evidence",
        "scenario_inputs": {
            "subject": {"kind": "stock", "identity": "600600.SH"},
            "as_of": "2026-10-28",
            "question": "核验已取得财务快照",
            "material_ids": [snapshot["dataset_id"]],
        },
    }
    response = client.post(
        "/api/research/handoffs",
        json=body,
        headers={"Idempotency-Key": "method-financial-snapshot"},
    )
    assert response.status_code == 201, response.text
    context = response.json()["scenario_context"]
    projected, bodies, _ = source_context(
        service, response.json()["session_id"], "owned-company-evidence", context
    )
    descriptor = projected["sources"][0]
    assert descriptor["category"] == "financials" and descriptor["security"] == "600600.SH"
    assert descriptor["report_period"] == "2026-06-30" and descriptor["currency"] == "CNY"
    assert "unit" not in descriptor and "basis" not in descriptor
    root = service.store.directory(response.json()["session_id"])
    for relative, raw in bodies.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    ledger = inspect_company_sources(root, projected)
    assert ledger["status"] == "incomplete"
    assert {"financial_unit_unverified", "financial_basis_unverified"} <= {
        gap["code"] for gap in ledger["missing"]
    }


@pytest.mark.skipif(
    sys.platform != "darwin" or not os.environ.get("RWB_DSH_TEST_SOURCE"),
    reason="actual pinned Native macOS execution",
)
@pytest.mark.parametrize(
    "cid,cancel,preset",
    [
        ("owned-company-evidence", False, None),
        ("owned-news-evidence", False, None),
        ("owned-research-prep", False, None),
        ("owned-company-evidence", True, None),
        ("owned-company-evidence", False, "company_one_pager"),
        ("owned-company-evidence", False, "fundamental_analysis"),
        ("owned-research-prep", False, "research_outline"),
        ("owned-company-evidence", False, "negative_base_fixture"),
    ],
)
def test_company_actual_dsh_toolruntime_guard_and_method_completion(
    api, monkeypatch, tmp_path, cid, cancel, preset
):
    negative_base = preset == "negative_base_fixture"
    client, service, sid, _context, descriptor, headers, _source = prepared(
        api,
        monkeypatch,
        cid,
        cutoff=cid != "owned-company-evidence",
        preset=None if negative_base else preset,
        transform=(
            (lambda raw: raw.replace(b"| 211,915 |", b"| (211,915) |")) if negative_base else None
        ),
    )
    root = Path(__file__).parents[2]
    bundle = json.loads(
        (service.store.directory(sid) / "resources/research_evidence.json").read_bytes()
    )
    revenues = {
        row["period"]: row
        for row in bundle["observations"]
        if row["metric"] == "total_revenue" and row.get("basis") == "primitive"
    }
    if not revenues:
        revenues = {
            row["period"]: row for row in bundle["observations"] if row["metric"] == "total_revenue"
        }
    contract = service._task_capabilities(sid)[0]["research_contract"]
    if cid == "owned-company-evidence":
        assert {"2024", "2023"} <= revenues.keys()
        assert revenues["2024"]["value"] == "245122" and revenues["2023"]["value"] == (
            "-211915" if negative_base else "211915"
        )
        current, previous = revenues["2024"]["id"], revenues["2023"]["id"]
        plan = {
            "title": "公司原件限定核验",
            "calculations": [
                {
                    "id": "revenue_change",
                    "operation": "percent_change",
                    "operands": [current, previous],
                    "decimal_places": 2,
                }
            ],
            "sections": [
                {
                    "id": "income",
                    "heading": "已取得原件",
                    "evidence_ids": [current, previous, "$revenue_change"],
                    "requirement_ids": [contract["requirements"][0]["id"]],
                    "analysis": "仅在本次已取得原件范围比较收入：{{fact:"
                    + current
                    + "}}；对应比较为{{formula:$revenue_change}}。业务、竞争与估值仍缺材料，不能据此给出完整公司判断。",
                }
            ],
            "missing": ["业务、竞争、估值与来源历史资格尚未齐备。"],
        }
    else:
        fact = next(row for row in bundle["observations"] if row.get("kind") == "business_numeric")
        plan = {
            "title": "原件限定方法研究",
            "sections": [
                {
                    "id": "evidence",
                    "heading": "已取得原件",
                    "evidence_ids": [fact["id"]],
                    "requirement_ids": [contract["requirements"][0]["id"]],
                    "analysis": "本次已取得原件列示{{fact:"
                    + fact["id"]
                    + "}}。这里只形成条件性解释和未决问题；替代解释仍待补证，没有开展访谈，也不推定因果。",
                }
            ],
            "missing": ["去重制品、反证与后续研究材料尚未齐备。"],
        }
    config = {
        "sid": sid,
        "researchRoot": str(service.store.root),
        "nativeRoot": str(service.capabilities.prepare_native_root()),
        "python": sys.executable,
        "runnerPath": str(root / "app/research_web/sandbox.py"),
        "descriptor": descriptor,
        "timeoutSeconds": 15,
        "reportPlan": None if cancel else plan,
        "cancel": cancel,
    }
    path = tmp_path / "native-method.json"
    path.write_text(json.dumps(config))
    node = os.environ.get("RWB_TEST_NODE") or shutil.which("node")
    process = subprocess.Popen(
        [node, str(root / "tests/javascript/helpers/method-native-driver.mjs"), str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    final = None
    transcript = []
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready, _, _ = select.select([process.stdout], [], [], 0.5)
            if not ready:
                if process.poll() is not None:
                    break
                continue
            line = process.stdout.readline()
            if not line:
                break
            value = json.loads(line)
            if value["kind"] == "result":
                final = value
                break
            assert value["kind"] == "bridge" and value["authorizationPresent"]
            assert value["path"] in {
                "/api/research/internal/data/skill-preflight",
                "/api/research/internal/data/pack-completion",
                "/api/research/internal/data/research-quality",
            }
            response = client.post(value["path"], json=value["body"], headers=headers)
            transcript.append(
                {"path": value["path"], "request": value["body"], "status": response.status_code}
            )
            process.stdin.write(
                json.dumps(
                    {"id": value["id"], "status": response.status_code, "body": response.json()}
                )
                + "\n"
            )
            process.stdin.flush()
        process.stdin.close()
        process.wait(timeout=5)
        errors = process.stderr.read()
        assert process.returncode == 0 and final is not None, errors
        assert not final["loaded"]["isError"]
        if cancel:
            assert final["actual"]["isError"]
            receipt, _ = service._task_capabilities(sid)
            assert receipt["method_executions"][0]["state"] != "saved"
            retry = client.post(
                "/api/research/internal/data/skill-preflight",
                json={
                    "session_id": sid,
                    "tool_name": "research_run_script",
                    "method_execution": descriptor,
                    "call_id": "cannot-retry-after-cancel",
                    "pack_start": True,
                },
                headers=headers,
            )
            assert retry.status_code == 409
            return
        assert not final["actual"]["isError"], final["actual"]
        if negative_base:
            runner = json.loads(final["report"]["content"][0]["text"])
            assert runner["status"] == "failed" and runner["exit_code"] == 1
            assert json.loads(runner["stdout"])["error"] == "owned_percent_change_nonpositive_base"
            assert not (service.store.directory(sid) / "outputs/research-report.json").exists()
            assert (
                service._task_capabilities(sid)[0]["quality_last_result"]["status"] == "incomplete"
            )
            return
        assert not final["report"]["isError"], final["report"]
        assert not final["quality"]["isError"], final["quality"]
        receipt, _ = service._task_capabilities(sid)
        assert receipt["method_executions"][0]["state"] == "saved"
        assert any(item["request"].get("kind") == "owned-method" for item in transcript)
        canonical = json.loads(
            (service.store.directory(sid) / "outputs/research-report.json").read_bytes()
        )
        if cid == "owned-company-evidence":
            assert "15.67" in json.dumps(canonical, ensure_ascii=False)
            ledger = json.loads(
                (
                    service.store.directory(sid)
                    / receipt["method_executions"][0]["artifact"]["path"]
                ).read_bytes()
            )
            assert ledger["sources"][0]["category"] == "unclassified"
            assert any(g.get("category") == "financials" for g in ledger["missing"])
        assert any(item["path"].endswith("/research-quality") for item in transcript)
        assert receipt["quality_last_result"]["status"] == "incomplete"
        assert "method_source_incomplete:" + cid in receipt["quality_last_result"]["issues"]
        if cid == "owned-company-evidence":
            # An unknown .txt file is never exempted by the generated-input filter.
            from app.research_web.scenario_method_sources import original_evidence_files

            extra = service.store.directory(sid) / "inputs/methods/unknown.txt"
            extra.write_text("unregistered input")
            listed = service.store.files(sid)
            extra_id = hashlib.sha256(b"inputs/methods/unknown.txt").hexdigest()[:24]
            assert extra_id in {
                item["id"] for item in original_evidence_files(service, sid, listed)
            }
            rejected = client.post(
                "/api/research/internal/data/research-quality",
                json={"session_id": sid},
                headers=headers,
            )
            assert rejected.status_code == 200 and rejected.json()["status"] == "invalid"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
