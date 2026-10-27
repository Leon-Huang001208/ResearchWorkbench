"""Real Host admission/private completion and actual native sandbox, no model."""

import copy
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import test_scenario_handoffs as scenario_fixtures

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.sandbox import SandboxConfig, run_script
from app.research_web.scenario_handoffs import fingerprint

api = scenario_fixtures.api


def admitted(api, monkeypatch):
    client, service = api
    price_day = (datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)).isoformat()
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    query = BusinessQuery(
        capability="market_bars",
        source="baostock",
        parameters={
            "asset": "600600.SH",
            "asset_type": "stock",
            "adjustment": "none",
            "start_date": price_day,
            "end_date": price_day,
        },
    )
    dataset = service.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[
                {
                    "asset": "600600.SH",
                    "date": price_day,
                    "close": 68.2,
                    "trading_status": True,
                    "adjustment": "none",
                }
            ],
            raw=[
                json.dumps(
                    [
                        {
                            "code": "sh.600600",
                            "date": price_day,
                            "close": "68.2",
                            "adjustflag": "3",
                            "tradestatus": "1",
                        }
                    ]
                ).encode()
            ],
            status="snapshot",
            fields={"close": {"unit": "currency_per_share", "currency": "CNY"}},
            metadata={
                "provider_semantics_revision": "baostock-raw-sh-sz-v1",
                "upstream_id": "baostock",
            },
        ),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("baostock"),
    )
    as_of = (
        datetime.fromisoformat(dataset["retrieved_at"])
        .astimezone(ZoneInfo("Asia/Shanghai"))
        .date()
        .isoformat()
    )
    body = {
        "source_session_id": sid,
        "target_mode": "fingpt",
        "section": "assets",
        "dataset_ids": [dataset["dataset_id"]],
        "scenario_id": "pack-event-review",
        "scenario_inputs": {
            "subject": {"kind": "stock", "identity": "600600.SH"},
            "as_of": as_of,
            "question": "核验真实冻结价格和缺日历",
            "material_ids": [dataset["dataset_id"]],
            "research_scope": {
                "cutoff_at": as_of + "T23:59:59+08:00",
                "methods": {
                    "align_event_trading_day": {
                        "release_at": price_day + "T10:00:00+08:00",
                        "pre_sessions": 1,
                        "post_sessions": 1,
                        "adjustment": "none",
                    }
                },
            },
        },
    }
    response = client.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "native-pack-prepare"}
    )
    assert response.status_code == 201, response.text
    target = response.json()["session_id"]
    context = response.json()["scenario_context"]
    original = service.client.rpc

    async def rpc(method, payload):
        # Offline Native fixture supplies discovery; Host/model whitelist,
        # admission, resources, seal, supervisor and completion remain real.
        if method == "skill.list":
            return {
                "skills": [
                    {"name": p.name} for p in service.capabilities.prepare_native_root().iterdir()
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    assert service._model_tools_verified(target)
    response = client.post(
        f"/api/research/sessions/{target}/messages",
        json={"text": "执行冻结组合包", "expected_formats": []},
        headers={"Idempotency-Key": "native-pack-send"},
    )
    assert response.status_code == 202, response.text
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    descriptor = {
        "capability_id": context["pack_seal"]["capability_id"],
        "version": context["pack_seal"]["version"],
        "context_sha256": fingerprint(context),
        "input_manifest_sha256": context["pack_seal"]["manifest_sha256"],
    }
    return client, service, target, context, descriptor, headers


@pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS sandbox")
def test_actual_host_admission_real_sandbox_completion_and_no_retry(api, monkeypatch):
    client, service, sid, context, descriptor, headers = admitted(api, monkeypatch)
    admission = {
        "session_id": sid,
        "tool_name": "research_run_script",
        "pack_execution": descriptor,
        "call_id": "actual-pack-call",
        "pack_start": True,
    }
    not_loaded = client.post(
        "/api/research/internal/data/skill-preflight", json=admission, headers=headers
    )
    assert not_loaded.status_code == 409
    assert not_loaded.json()["error"]["code"] == "pack_capability_not_loaded"
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
    preview = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**admission, "pack_start": False},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert not service._task_capabilities(sid)[0].get("pack_executions")
    response = client.post(
        "/api/research/internal/data/skill-preflight", json=admission, headers=headers
    )
    assert response.status_code == 200, response.text
    scope = response.json()
    assert scope["input_policy"] == "scenario-frozen-inputs-v1"
    assert scope["binding"]["call_id"] == "actual-pack-call"
    assert (
        client.post(
            "/api/research/internal/data/skill-preflight",
            json={**admission, "call_id": "retry-with-new-call"},
            headers=headers,
        ).status_code
        == 409
    )
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
    from dataclasses import asdict

    completion = {
        "session_id": sid,
        "execution_id": scope["binding"]["execution_id"],
        "call_id": "actual-pack-call",
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
    assert saved.json()["computation_status"] != "complete"
    receipt, _ = service._task_capabilities(sid)
    actual = receipt["pack_executions"][0]
    assert actual["actual_exit_code"] == 0
    assert actual["counts"]["components"] == {"align_event_trading_day": 0}
    from app.research_web.scenario_pack_execution import quality_issues

    assert quality_issues(service, sid, receipt, context) == [
        "pack_computation_or_source_incomplete"
    ]
    quality = client.post(
        "/api/research/internal/data/research-quality", json={"session_id": sid}, headers=headers
    )
    assert quality.status_code == 200, quality.text
    assert quality.json()["status"] == "incomplete"
    assert "pack_computation_or_source_incomplete" in quality.json()["issues"]


@pytest.mark.skipif(
    sys.platform != "darwin" or not os.environ.get("RWB_DSH_TEST_SOURCE"),
    reason="Exact pinned DSH + Native macOS required",
)
@pytest.mark.parametrize("cancel", [False, True])
def test_actual_dsh_skill_guard_toolruntime_host_and_sandbox(api, monkeypatch, tmp_path, cancel):
    client, service, sid, _context, descriptor, headers = admitted(api, monkeypatch)
    root = Path(__file__).parents[2]
    config = {
        "sid": sid,
        "researchRoot": str(service.store.root),
        "nativeRoot": str(service.capabilities.prepare_native_root()),
        "python": sys.executable,
        "runnerPath": str(root / "app/research_web/sandbox.py"),
        "descriptor": descriptor,
        "timeoutSeconds": 15,
        "cancel": cancel,
    }
    config_path = tmp_path / "driver.json"
    config_path.write_text(json.dumps(config))
    node = os.environ.get("RWB_TEST_NODE") or shutil.which("node")
    assert node
    process = subprocess.Popen(
        [node, str(root / "tests/javascript/helpers/pack-native-driver.mjs"), str(config_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    transcript = []
    final = None
    deadline = time.monotonic() + 45
    try:
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
            }
            response = client.post(value["path"], json=value["body"], headers=headers)
            transcript.append(
                {
                    "path": value["path"],
                    "request": value["body"],
                    "response_status": response.status_code,
                }
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
        assert final["loaded"]["isError"] is False
        receipt, _ = service._task_capabilities(sid)
        if cancel:
            assert final["actual"]["isError"] is True
            assert receipt["pack_executions"][0]["state"] != "saved"
            from app.research_web.store import Store

            # Restore persisted control state: an uncertain process cannot reopen
            # execution under another call ID after its Native process has gone.
            monkeypatch.setattr(service, "store", Store(service.store.root))
            replay = client.post(
                "/api/research/internal/data/skill-preflight",
                json={
                    "session_id": sid,
                    "tool_name": "research_run_script",
                    "pack_execution": descriptor,
                    "call_id": "new-after-restore",
                    "pack_start": True,
                },
                headers=headers,
            )
            assert replay.status_code == 409
            assert replay.json()["error"]["code"] == "pack_execution_unknown_do_not_retry"
        else:
            assert final["actual"]["isError"] is False, final["actual"]
            assert final["actual"]["value"]["status"] == "completed", final["actual"]
            assert receipt["pack_executions"][0]["state"] == "saved"
            persisted = receipt["pack_executions"][0]
            assert persisted["native_result"] == final["actual"]["value"]
            assert (
                persisted["native_rendered_sha256"]
                == hashlib.sha256(final["actual"]["content"][0]["text"].encode()).hexdigest()
            )
        requests = [item["request"] for item in transcript]
        assert sum(item.get("pack_start") is True for item in requests) == 1
        assert any(
            item.get("pack_execution") and item.get("pack_start") is False for item in requests
        )
        assert any(item.get("loaded") is True for item in requests)
        (tmp_path / "native-transcript.json").write_text(
            json.dumps({"events": transcript, "result": final}, ensure_ascii=False)
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)


@pytest.mark.parametrize(
    "failure", ["fake_stdout", "prewritten", "changed_artifact", "cancelled", "failed"]
)
@pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS sandbox")
def test_host_never_certifies_fake_files_failed_or_cancelled_calls(api, monkeypatch, failure):
    from dataclasses import asdict

    client, service, sid, _context, descriptor, headers = admitted(api, monkeypatch)
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
    assert loaded.status_code == 200
    admission = {
        "session_id": sid,
        "tool_name": "research_run_script",
        "pack_execution": descriptor,
        "call_id": "negative-call",
        "pack_start": True,
    }
    scope = client.post(
        "/api/research/internal/data/skill-preflight", json=admission, headers=headers
    ).json()
    root = service.store.root
    session = root / "sessions" / sid
    target = session / scope["output_root"] / "v1"
    if failure in {"cancelled", "failed"}:
        result = {
            "status": failure,
            "stdout": "",
            "stderr": "",
            "exit_code": None if failure == "cancelled" else 1,
            "error": "actual runner failure",
        }
    else:
        if failure == "prewritten":
            target.mkdir()
            (target / "full-result.json").write_text("{}")
        actual = run_script(
            SandboxConfig(root, Path(sys.executable)),
            session,
            scope["code"],
            read_paths=scope["read_paths"],
            input_policy=scope["input_policy"],
            file_bindings=scope["file_bindings"],
            output_root=scope["output_root"],
        )
        result = asdict(actual)
        if failure == "fake_stdout":
            assert actual.status == "completed"
            result["stdout"] = '{"status":"complete","passed":true}'
        elif failure == "changed_artifact":
            assert actual.status == "completed"
            path = target / "full-result.json"
            path.chmod(0o600)
            path.write_text("{}")
        else:
            assert actual.status == "failed" and "output_exists" in actual.stderr
    response = client.post(
        "/api/research/internal/data/pack-completion",
        json={
            "session_id": sid,
            "execution_id": scope["binding"]["execution_id"],
            "call_id": "negative-call",
            "result": result,
        },
        headers=headers,
    )
    receipt, _ = service._task_capabilities(sid)
    record = receipt["pack_executions"][0]
    assert record["state"] in {"invalid", "cancelled", "failed"}
    assert record["state"] != "saved"
    assert response.status_code == (409 if failure in {"fake_stdout", "changed_artifact"} else 200)
    assert (
        client.post(
            "/api/research/internal/data/skill-preflight",
            json={**admission, "call_id": "new-call-still-no-retry"},
            headers=headers,
        ).status_code
        == 409
    )


def test_immutable_successor_keeps_old_handoff_and_receipt_but_cannot_resend(api, monkeypatch):
    from app.research_web.capabilities.models import CapabilityError
    from app.research_web.scenario_handoffs import trusted_context

    _client, service, sid, context, _descriptor, _headers = admitted(api, monkeypatch)
    before = copy.deepcopy(service._task_capabilities(sid)[0])
    service.capabilities.publish("research-pack-event-review", _allow_builtin_migration=True)
    assert service.capabilities.row("research-pack-event-review")["version"] == 2
    handoff = service.store.data["handoffs"][service.store.session(sid)["scenario_handoff_id"]]
    assert handoff["scenario_context"] == context
    context_file = service.store.directory(sid) / handoff["context_file"]["path"]
    assert (
        hashlib.sha256(context_file.read_bytes()).hexdigest() == handoff["context_file"]["sha256"]
    )
    assert service._task_capabilities(sid)[0] == before
    with pytest.raises(CapabilityError) as error:
        trusted_context(service, sid)
    assert error.value.code == "version_conflict"
