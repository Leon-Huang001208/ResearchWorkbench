"""Offline real-Sender regression; Native transport and credentials are isolated."""

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_report_workflow_integration import NativeFixture, isolated_keyring

from app.research_web.capabilities.models import CapabilityError
from app.research_web.client import RuntimeFailure
from app.research_web.report_workflows.models import ReportWorkflowManifest, WorkflowError
from app.research_web.report_workflows.weekly_quality import POLICY_ID, freeze_weekly_production
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError

__all__ = ["isolated_keyring"]


@pytest.fixture
def weekly(tmp_path, monkeypatch):
    from test_report_weekly_data import build_weekly_data_contract, synthetic_snapshot
    from test_report_weekly_quality import _manifest

    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "state"))
    service.connected = {"mux", "host"}
    service.report_owner_authorizer = lambda: {"id": "owner", "role": "admin", "enabled": True}

    async def credentials(_provider):
        return None

    monkeypatch.setattr(service, "_require_model_credentials", credentials)
    catalog = service.report_workflows.catalog
    manifest = ReportWorkflowManifest.model_validate(_manifest())
    catalog.create_draft(manifest)
    catalog.create_version(manifest.workflow_id)
    catalog.publish_version(manifest.workflow_id, 1)
    with catalog._exclusive():
        catalog._row(manifest.workflow_id)["status"] = "enabled"
        catalog._save()
    workspace = catalog.create_run_workspace(manifest.workflow_id, 1)
    rid = workspace["run_id"]
    root = catalog.run_path(rid)
    contract = build_weekly_data_contract("2026-10-16T15:30:00+08:00")
    raw = json.dumps(synthetic_snapshot(contract)).encode()
    (root / "snapshots").mkdir()
    (root / "snapshots/report-data.json").write_bytes(raw)
    row = service.store.create("claw", "离线周报")
    sid = row["id"]
    row.update(created=True, model="deepseek-flash", model_provider="deepseek-official")
    frozen = freeze_weekly_production(manifest, contract)
    context = {"weekly_production": frozen, "minimum_subagents": manifest.minimum_subagents}
    context_raw = json.dumps(context).encode()
    (root / "run-context.json").write_bytes(context_raw)
    shutil.copytree(root, service.store.directory(sid) / "inputs/report-workflow")
    row["report_workflow"] = {
        "quality_policy": POLICY_ID,
        "workflow_id": manifest.workflow_id,
        "version": 1,
        "run_id": rid,
    }
    run = service.report_workflows.runtime._update_run(
        rid,
        id=rid,
        workflow_id=manifest.workflow_id,
        version=1,
        session_id=sid,
        owner_id="owner",
        weekly_production=frozen,
        weekly_data_contract=contract,
        weekly_context_sha256=hashlib.sha256(context_raw).hexdigest(),
        dataset_snapshot_sha256=hashlib.sha256(raw).hexdigest(),
    )
    return service, native, run, manifest


def test_trusted_weekly_real_sender_has_independent_admission(weekly):
    service, native, run, manifest = weekly
    runtime = service.report_workflows.runtime
    prompt = runtime._weekly_submission_prompt(run, manifest, run["dataset_snapshot_sha256"])
    runtime._update_run(run["id"], weekly_submission_prompt=prompt)
    asyncio.run(runtime._submit_weekly(run["id"]))
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1
    actual = next(body for name, body in native.calls if name == "session.prompt")
    assert f"至少 {manifest.minimum_subagents} 个原生子 Agent" in actual["content"][0]["text"]
    receipt = service.store.receipt(run["session_id"], "report-workflow-" + run["id"])
    assert receipt["research_contract"]["as_of"] == run["weekly_production"]["as_of"]
    assert len(receipt["research_contract"]["requirements"]) == len(
        run["weekly_production"]["requirements"]
    )
    assert not receipt.get("capability")


def test_generic_report_keeps_missing_data_contract_rejection(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "state"))
    row = service.store.create("claw", "离线测试")
    row.update(created=True, model="deepseek-flash", model_provider="deepseek-official")
    service.connected = {"mux", "host"}
    with pytest.raises(CapabilityError) as caught:
        asyncio.run(
            service.send(row["id"], "报告", "generic", capability_id="report-production-workflow")
        )
    assert caught.value.code == "capability_data_unavailable"
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_weekly_journal_claim_is_durable_and_exclusive(tmp_path):
    from app.research_web.report_workflows.weekly_execution import create_attempt, has_attempt

    assert not has_attempt(tmp_path)
    create_attempt(tmp_path, {"protocol": "weekly-admission-v2", "run_id": "r"})
    assert has_attempt(tmp_path)
    with pytest.raises(WorkflowError):
        create_attempt(tmp_path, {"protocol": "weekly-admission-v2", "run_id": "r"})


def freeze_scope(weekly):
    from app.research_web.report_workflows.weekly_execution import projection

    service, _native, run, manifest = weekly
    service.report_workflows.runtime._update_run(run["id"], weekly_submission_prompt="周报")
    return projection(
        service,
        run["session_id"],
        initialize=True,
        prompt="周报",
        formats=[x.value for x in manifest.delivery.formats],
    )


@pytest.mark.parametrize(
    "change",
    [
        "owner",
        "context",
        "snapshot",
        "private_snapshot",
        "purpose",
        "version",
        "model",
        "enabled",
        "scope",
        "sources",
    ],
)
def test_changed_scope_never_prompts(weekly, monkeypatch, change):
    service, native, run, _manifest = weekly
    freeze_scope(weekly)
    runtime = service.report_workflows.runtime
    sid, rid = run["session_id"], run["id"]
    if change == "owner":
        service.report_owner_authorizer = lambda: {"id": "other", "role": "admin", "enabled": True}
    elif change in {"context", "snapshot"}:
        path = "run-context.json" if change == "context" else "snapshots/report-data.json"
        (service.store.directory(sid) / "inputs/report-workflow" / path).write_bytes(b"{}")
    elif change == "private_snapshot":
        (runtime.run_path(rid) / "snapshots/report-data.json").write_bytes(b"{}")
    elif change == "purpose":
        runtime._update_run(rid, execution_purpose="historical_acceptance")
    elif change == "version":
        runtime._update_run(rid, version=2)
    elif change == "model":
        service.store.session(sid)["model"] = "unverified-model"
    elif change == "enabled":
        with runtime.catalog._exclusive():
            runtime.catalog._row(run["workflow_id"])["status"] = "disabled"
            runtime.catalog._save()
    elif change == "scope":
        scope = runtime._run(rid)["weekly_execution_scope"]
        scope["tools"].append("rwb_run_automation")
        runtime._update_run(rid, weekly_execution_scope=scope)
    else:
        service.store.session(sid)["source_scope"] = ["web"]
    with pytest.raises((WorkflowError, RuntimeFailure)):
        asyncio.run(runtime._submit_weekly(rid))
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_native_tools_and_exact_frozen_read_paths(weekly):
    from app.research_web.report_workflows.weekly_execution import TOOLS

    service, _native, run, _manifest = weekly
    scope = freeze_scope(weekly)
    sid = run["session_id"]
    for name in TOOLS:
        admitted = service.native_admission(sid, tool_name=name)
        assert admitted["admitted"], (name, admitted)
        assert admitted["visible_tools"] == list(TOOLS)
    script = service.native_admission(sid, tool_name="research_run_script")
    assert set(script["read_paths"]) == {
        "inputs/report-workflow/" + name for name in scope["inputs"]
    }
    assert "inputs/report-workflow/snapshots/report-data.json" in script["read_paths"]
    for name in (
        "datahub_get_stock_data",
        "rwb_run_automation",
        "mcp__arbitrary__tool",
        "web_fetch",
    ):
        assert not service.native_admission(sid, tool_name=name)["admitted"]
    external = service.store.directory(sid) / "inputs/report-workflow/unfrozen.txt"
    external.write_text("not frozen")
    assert (
        external.relative_to(service.store.directory(sid)).as_posix()
        not in service.native_admission(sid, tool_name="research_run_script")["read_paths"]
    )


def test_claim_failure_is_known_preflight_and_explicit_retry_reuses_contract(weekly, monkeypatch):
    from app.research_web.report_workflows import weekly_execution

    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)
    original = weekly_execution.create_attempt

    def fail(*_args):
        raise WorkflowError("fixture disk failure", "weekly_attempt_failed", 409)

    monkeypatch.setattr(weekly_execution, "create_attempt", fail)
    with pytest.raises(WorkflowError):
        asyncio.run(runtime._submit_weekly(run["id"]))
    assert not any(name == "session.prompt" for name, _ in native.calls)
    assert runtime._run(run["id"])["research_submission_state"] == "preflight_rejected"
    receipt_key = run["session_id"] + ":report-workflow-" + run["id"]
    receipt = json.loads(json.dumps(service.store.data["receipts"][receipt_key]))
    context = (
        service.store.directory(run["session_id"]) / "inputs/report-workflow/run-context.json"
    ).read_bytes()
    monkeypatch.setattr(weekly_execution, "create_attempt", original)
    asyncio.run(runtime._submit_weekly(run["id"], resume=True))
    current = service.store.data["receipts"][receipt_key]
    assert current["research_contract"] == receipt["research_contract"]
    assert {k: v for k, v in current["delivery"].items() if k != "status"} == {
        k: v for k, v in receipt["delivery"].items() if k != "status"
    }
    assert (
        context
        == (
            service.store.directory(run["session_id"]) / "inputs/report-workflow/run-context.json"
        ).read_bytes()
    )
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1
    assert runtime._run(run["id"])["research_preflight_failure_code"] == "weekly_attempt_failed"


def test_lost_ack_claim_survives_restart_and_never_replays(weekly, monkeypatch):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)
    original = native.rpc

    async def lost(method, payload):
        result = await original(method, payload)
        if method == "session.prompt":
            raise RuntimeFailure("lost ack", "transport_lost")
        return result

    monkeypatch.setattr(native, "rpc", lost)
    with pytest.raises(RuntimeFailure):
        asyncio.run(runtime._submit_weekly(run["id"]))
    assert runtime._run(run["id"])["research_submission_state"] == "unknown"
    from app.research_web.report_workflows.runtime import ReportWorkflowRuntime

    restarted = ReportWorkflowRuntime(service, runtime.catalog, runtime.refresh)
    service.report_workflows.runtime = restarted
    with pytest.raises(WorkflowError):
        asyncio.run(restarted._submit_weekly(run["id"], resume=True))
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1


@pytest.mark.parametrize("outcome", ["accepted", "lost_ack"])
@pytest.mark.parametrize("second_entry", ["direct", "background"])
def test_concurrent_submit_claim_allows_one_prompt(weekly, monkeypatch, outcome, second_entry):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)
    runtime._update_run(run["id"], finalization_status="pending")

    async def double():
        entered, release, second_inside_send = asyncio.Event(), asyncio.Event(), asyncio.Event()
        rpc, send = native.rpc, service.send
        send_count = 0
        paused = False

        async def barrier_rpc(method, payload):
            nonlocal paused
            if method == "subagent.list" and not paused:
                paused = True
                entered.set()
                await release.wait()
            value = await rpc(method, payload)
            if method == "session.prompt" and outcome == "lost_ack":
                raise RuntimeFailure("lost ACK", "transport_lost")
            return value

        async def observed_real_send(*args, **kwargs):
            nonlocal send_count
            send_count += 1
            if send_count == 2:
                second_inside_send.set()
            return await send(*args, **kwargs)

        monkeypatch.setattr(native, "rpc", barrier_rpc)
        monkeypatch.setattr(service, "send", observed_real_send)
        first = asyncio.create_task(runtime._submit_weekly(run["id"]))
        await entered.wait()
        call = (
            runtime._submit_weekly
            if second_entry == "direct"
            else runtime._resume_weekly_submission
        )
        second = asyncio.create_task(call(run["id"]))
        await second_inside_send.wait()
        release.set()
        return await asyncio.gather(first, second, return_exceptions=True)

    results = asyncio.run(double())
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1
    if second_entry == "direct":
        assert isinstance(results[1], StoreError)
        assert results[1].code == "weekly_research_unknown"
    current = runtime._run(run["id"])
    if outcome == "accepted":
        assert results[0] is None
        assert current["research_submission_state"] == "accepted"
        assert current["status"] == "running"
        assert current["finalization_status"] == "pending"
        assert current["failure_code"] is None
        assert current["research_started_at"]
    else:
        assert isinstance(results[0], RuntimeFailure)
        assert current["research_submission_state"] == "unknown"
        assert current["status"] == "needs_attention"
        assert current["finalization_status"] == "blocked"
        assert current["failure_code"] == "research_submission_unknown"


def test_public_sender_cannot_supply_weekly_scope(weekly):
    service, native, run, _manifest = weekly
    freeze_scope(weekly)
    with pytest.raises(StoreError):
        asyncio.run(service.send(run["session_id"], "forged", "other"))
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_accepted_weekly_monitor_failure_remains_visible(weekly, monkeypatch):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)

    async def failed_monitor(_run_id):
        raise RuntimeFailure("delivery observation failed", "fixture_delivery_observation_failed")

    monkeypatch.setattr(runtime, "_wait_for_delivery", failed_monitor)
    asyncio.run(runtime._resume_weekly_submission(run["id"]))
    current = runtime._run(run["id"])
    assert current["research_submission_state"] == "accepted"
    assert current["research_started_at"]
    assert current["status"] == "needs_attention"
    assert current["finalization_status"] == "blocked"
    assert current["recovery_failure_code"] == "fixture_delivery_observation_failed"
    assert current["failure_code"] is None
    assert (
        service.store.receipt(run["session_id"], "report-workflow-" + run["id"])["status"]
        == "accepted"
    )
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1


@pytest.mark.parametrize("legacy_state", ["unknown", "prepared", "preflight_rejected"])
def test_legacy_empty_native_without_sender_evidence_never_replays(weekly, legacy_state):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    runtime._update_run(
        run["id"],
        status="needs_attention",
        research_admission_at=1,
        research_submission_state=legacy_state,
        failure_code="research_submission_unknown",
    )

    async def check():
        # No receipt, key, attempt, messages, children or usage: these are still
        # insufficient to establish the historical Sender implementation.
        assert await native.history(run["session_id"]) == []
        checked = await runtime._inspect_weekly_run(run["id"])
        assert checked["recovery_failure_code"] == "weekly_legacy_sender_unproven"
        assert runtime.tasks == {}
        assert "research_submission_protocol" not in checked
        assert checked["failure_code"] == "research_submission_unknown"
        checked_again = await runtime._inspect_weekly_run(run["id"])
        assert checked_again["recovery_failure_code"] == "weekly_legacy_sender_unproven"
        with pytest.raises(StoreError):
            await service.send(run["session_id"], "周报", "report-workflow-" + run["id"])

    asyncio.run(check())
    assert not any(name == "session.prompt" for name, _ in native.calls)


@pytest.mark.parametrize(
    "operation,receipt_status",
    [
        ("inspect", "pending"),
        ("inspect", "unknown"),
        ("inspect", "accepted"),
        ("startup", "pending"),
        ("startup", "unknown"),
        ("startup", "accepted"),
        ("startup", None),
        ("startup_owner_error", "pending"),
    ],
)
def test_recovery_preserves_legacy_sender_failure_and_frozen_evidence(
    weekly, monkeypatch, operation, receipt_status
):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    rid, sid = run["id"], run["session_id"]
    frozen = runtime._update_run(
        rid,
        status="needs_attention",
        research_admission_at=123,
        research_submission_state="unknown",
        failure_code="research_submission_unknown",
    )
    key = "report-workflow-" + rid
    if receipt_status:
        task = hashlib.sha256(f"{sid}:{key}".encode()).hexdigest()[:24]
        service.store.reserve(
            sid,
            key,
            "synthetic-legacy",
            {
                "task_id": task,
                "marker": "[RESEARCH_TASK:" + task + "]",
                "required_formats": ["docx"],
            },
        )
        service.store.receipt(sid, key, receipt_status)
    receipts_before = json.loads(json.dumps(service.store.data["receipts"]))
    if operation == "startup_owner_error":
        service.report_owner_authorizer = lambda: {"id": "owner", "role": "admin", "enabled": False}
    elif receipt_status == "accepted":
        if operation == "inspect":

            async def unavailable(_sid):
                raise RuntimeFailure("observation unavailable", "fixture_observation_unavailable")

            monkeypatch.setattr(service, "detail", unavailable)
        else:
            from app.research_web.report_workflows import weekly_quality

            def unavailable_context(*_args):
                raise WorkflowError(
                    "observation unavailable", "fixture_observation_unavailable", 409
                )

            monkeypatch.setattr(weekly_quality, "trusted_weekly_context", unavailable_context)
    if operation == "inspect":
        asyncio.run(runtime._inspect_weekly_run(rid))
    else:
        asyncio.run(runtime._recover_weekly_runs())
    current = runtime._run(rid)
    for field in (
        "failure_code",
        "research_submission_state",
        "research_admission_at",
        "dataset_snapshot_sha256",
        "weekly_context_sha256",
        "weekly_production",
        "weekly_data_contract",
    ):
        assert current[field] == frozen[field], field
    assert "research_submission_protocol" not in current
    assert current["recovery_failure_code"]
    assert service.store.data["receipts"] == receipts_before
    assert runtime.tasks == {}
    assert not any(name == "session.prompt" for name, _ in native.calls)


@pytest.mark.parametrize("phase", ["prepared", "preflight_rejected"])
def test_startup_keeps_known_preflight_stage_for_explicit_retry(weekly, phase):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)
    runtime._update_run(
        run["id"],
        status="needs_attention",
        research_submission_state=phase,
        failure_code="known_preflight_rejection",
    )
    asyncio.run(runtime._recover_weekly_runs())
    current = runtime._run(run["id"])
    assert current["research_submission_state"] == phase
    assert current["failure_code"] == "known_preflight_rejection"
    assert current["recovery_failure_code"] == "weekly_recovery_waiting_explicit_retry"
    assert runtime.tasks == {}
    assert not any(name == "session.prompt" for name, _ in native.calls)


@pytest.mark.parametrize("status", ["cancelled", "needs_attention"])
def test_ended_workflow_wait_never_restarts_on_retry_or_startup(weekly, monkeypatch, status):
    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    ended = runtime._update_run(
        run["id"],
        status=status,
        monitoring_disposition="ended_by_user",
        research_submission_state="unknown",
        research_admission_at=123,
        failure_code="research_submission_unknown",
        finalization_status="blocked",
    )

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("ended waiting must not inspect, project or submit")

    for name in ("_inspect_weekly_run", "_resume_delivery", "_submit_weekly"):
        monkeypatch.setattr(runtime, name, forbidden)

    async def check():
        assert await runtime.retry(run["id"]) == runtime.public_run(ended)
        await runtime._recover_weekly_runs()
        assert runtime._run(run["id"]) == ended
        assert runtime.tasks == {}

    asyncio.run(check())
    assert native.calls == []


def test_explicit_preflight_retry_observes_original_inputs_without_collection(weekly, monkeypatch):
    from app.research_web.report_workflows import weekly_execution

    service, native, run, _manifest = weekly
    runtime = service.report_workflows.runtime
    freeze_scope(weekly)
    original = weekly_execution.create_attempt

    def fail(*_args):
        raise WorkflowError("disk", "weekly_attempt_failed", 409)

    monkeypatch.setattr(weekly_execution, "create_attempt", fail)
    with pytest.raises(WorkflowError):
        asyncio.run(runtime._submit_weekly(run["id"]))
    context_path = (
        service.store.directory(run["session_id"]) / "inputs/report-workflow/run-context.json"
    )
    original_bytes = context_path.read_bytes()
    collections = []

    async def collector(*_args, **_kwargs):
        collections.append(True)
        raise AssertionError("frozen retry must never collect")

    async def monitor(_run_id):
        return None

    monkeypatch.setattr(service.datahub, "collect_report_weekly", collector)
    monkeypatch.setattr(runtime, "_wait_for_delivery", monitor)
    monkeypatch.setattr(weekly_execution, "create_attempt", original)

    async def check():
        await runtime._inspect_weekly_run(run["id"])
        await asyncio.gather(*list(runtime.tasks.values()))
        assert runtime._run(run["id"])["research_submission_state"] == "accepted"

    asyncio.run(check())
    assert collections == []
    assert context_path.read_bytes() == original_bytes
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1


def test_contract_preparation_failure_is_zero_rpc(weekly, monkeypatch):
    import app.research_web.service as service_module

    service, native, run, _manifest = weekly
    freeze_scope(weekly)

    def fail(*_args, **_kwargs):
        raise ValueError("fixture preparation failure")

    monkeypatch.setattr(service_module, "prepare_contract", fail)
    with pytest.raises(StoreError) as caught:
        asyncio.run(service.report_workflows.runtime._submit_weekly(run["id"]))
    assert caught.value.code == "research_contract_preflight_failed"
    current = service.report_workflows.runtime._run(run["id"])
    assert current["research_submission_state"] == "preflight_rejected"
    assert current["failure_code"] == "research_contract_preflight_failed"
    assert not any(name == "session.prompt" for name, _ in native.calls)


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS Seatbelt evidence")
def test_frozen_weekly_files_are_readable_in_real_script_sandbox(weekly):
    from app.research_web.sandbox import SandboxConfig, run_script

    service, _native, run, _manifest = weekly
    sid = run["session_id"]
    session = service.store.directory(sid)
    chinese = session / "inputs/report-workflow/workbooks/中文 空格.xlsx"
    chinese.parent.mkdir(exist_ok=True)
    chinese.write_bytes(b"x" * 3_457_644)
    freeze_scope(weekly)
    (session / "inputs/unrelated.txt").write_text("unrelated")
    (session / "inputs/report-workflow/unfrozen.txt").write_text("not frozen")
    scope = service.native_admission(sid, tool_name="research_run_script")
    code = (
        "from pathlib import Path\nimport json, hashlib\n"
        "raw=Path('inputs/report-workflow/snapshots/report-data.json').read_bytes()\n"
        f"assert hashlib.sha256(raw).hexdigest()=={run['dataset_snapshot_sha256']!r}\n"
        "context=json.loads(Path('inputs/report-workflow/run-context.json').read_text())\n"
        "assert len(Path('inputs/report-workflow/workbooks/中文 空格.xlsx').read_bytes())==3457644\n"
        f"assert context['weekly_production']['version']=={run['version']}\n"
        "for name in ['inputs/unrelated.txt','inputs/report-workflow/unfrozen.txt']:\n"
        "    try:\n        Path(name).read_bytes()\n"
        "    except PermissionError:\n        pass\n"
        "    else:\n        raise AssertionError('unfrozen input readable')\n"
        "try:\n    Path('inputs/report-workflow/run-context.json').write_text('changed')\n"
        "except PermissionError:\n    pass\n"
        "else:\n    raise AssertionError('frozen input writable')\n"
        "print('frozen weekly input scope verified')\n"
    )
    result = run_script(
        SandboxConfig(research_root=service.store.root, python=Path(sys.executable)),
        session,
        code,
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
    )
    assert result.status == "completed", result
    assert result.stdout == "frozen weekly input scope verified\n"
    plugin = Path(__file__).resolve().parents[2] / "app/research_web/runtime/research-tools.mjs"
    runner = plugin.parent.parent / "sandbox.py"
    config = {
        "python": sys.executable,
        "runnerPath": str(runner),
        "researchRoot": str(service.store.root),
    }
    program = (
        f"import {{apply}} from {json.dumps(plugin.as_uri())};\n"
        f"const scope={json.dumps(scope)},cwd={json.dumps(str(session))};\n"
        "const parent={header:{id:'parent',cwd}};\n"
        "const child={header:{id:'child',cwd,parentSession:'parent'}};\n"
        "let tool; const ctx={tools:{register(t){if(t.name==='research_run_script')tool=t;}},"
        "sessions:{get(id){return id==='parent'?parent:undefined;}},logger:{info(){},warn(){},error(){}}};\n"
        f"apply(ctx,{json.dumps(config)},undefined,async()=>scope);\n"
        f"const args={{code:{json.dumps(code)}}};\n"
        "for(const session of [parent,child]) {\n"
        "const result=await tool.execute(args,{agent:{session},signal:new AbortController().signal});\n"
        "if(result.status!=='completed'||result.stdout!=='frozen weekly input scope verified\\n') throw Error(JSON.stringify(result));\n}\n"
        "console.log('native-parent-and-child-frozen-input-scope-verified');\n"
    )
    native = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert native.returncode == 0, native.stderr
    assert native.stdout == "native-parent-and-child-frozen-input-scope-verified\n"
