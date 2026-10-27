"""Mac Bootstrap's six actual Native-artifact/Host-cancel orderings; no skip."""

import asyncio
import copy
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from threading import Event

import pytest
import test_owned_method_execution as method_fixture
import test_pack_execution_host as pack_fixture

from app.research_web.sandbox import SandboxConfig, run_script

api = method_fixture.api


def begin(api, monkeypatch, kind):
    if kind == "method":
        client, service, sid, context, descriptor, headers, _ = method_fixture.prepared(
            api, monkeypatch
        )
    else:
        client, service, sid, context, descriptor, headers = pack_fixture.admitted(api, monkeypatch)
    return client, service, sid, context, descriptor, headers


def artifact(client, service, sid, descriptor, headers, kind):
    if kind == "method":
        scope, admission = method_fixture.start(client, sid, descriptor, headers)
    else:
        loaded = client.post(
            "/api/research/internal/data/skill-preflight",
            headers=headers,
            json={
                "session_id": sid,
                "tool_name": "skill",
                "native_name": descriptor["capability_id"],
                "loaded": True,
            },
        )
        assert loaded.status_code == 200, loaded.text
        admission = {
            "session_id": sid,
            "tool_name": "research_run_script",
            "pack_execution": descriptor,
            "call_id": "actual-pack-cancel-window",
            "pack_start": True,
        }
        response = client.post(
            "/api/research/internal/data/skill-preflight", json=admission, headers=headers
        )
        assert response.status_code == 200, response.text
        scope = response.json()
    result = run_script(
        SandboxConfig(service.store.root, Path(sys.executable)),
        service.store.directory(sid),
        scope["code"],
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
        file_bindings=scope["file_bindings"],
        output_root=scope["output_root"],
    )
    assert result.status == "completed" and result.exit_code == 0, (result.stderr, result.error)
    body = {
        "session_id": sid,
        "execution_id": scope["binding"]["execution_id"],
        "call_id": admission["call_id"],
        "result": asdict(result),
    }
    if kind == "method":
        body["kind"] = "owned-method"
    return body, admission


@pytest.mark.parametrize("kind", ["pack", "method"])
@pytest.mark.parametrize(
    "ordering", ["accepted_before_completion", "cancel_not_accepted", "saved_before_cancel"]
)
def test_actual_cancel_acceptance_and_native_completion_order(api, monkeypatch, kind, ordering):
    assert sys.platform == "darwin", "actual Native cancellation matrix belongs to Mac Bootstrap"
    client, service, sid, context, descriptor, headers = begin(api, monkeypatch, kind)
    cancel_path = f"/api/research/sessions/{sid}/cancel"
    complete_path = "/api/research/internal/data/pack-completion"
    original_rpc = service.client.rpc
    entered, release, complete_waiting = Event(), Event(), Event()
    calls = []

    async def rpc(method, payload):
        calls.append(method)
        if method == "session.cancel":
            if ordering == "cancel_not_accepted":
                return {"accepted": False}
            if kind == "method" and ordering == "accepted_before_completion":
                entered.set()
                assert await asyncio.to_thread(
                    release.wait, 10
                ), "test did not release its Native cancel RPC"
        return await original_rpc(method, payload)

    monkeypatch.setattr(service.client, "rpc", rpc)
    if kind == "pack" and ordering == "accepted_before_completion":
        cancelled = client.post(cancel_path, json={})
        assert cancelled.status_code == 200 and cancelled.json()["accepted"] is True
    body, admission = artifact(client, service, sid, descriptor, headers, kind)
    receipt, _ = service._task_capabilities(sid)
    record = receipt[kind + "_executions"][0]
    assert record["binding"]["task_id"] == service.delivery.current(sid)["task_id"]
    if ordering == "saved_before_cancel":
        response = client.post(complete_path, json=body, headers=headers)
        assert response.status_code == 200 and response.json()["state"] == "saved", response.text
        saved = copy.deepcopy(record)
        cancelled = client.post(cancel_path, json={})
        assert cancelled.status_code == 200 and cancelled.json()["accepted"] is True
        assert record == saved
        if kind == "pack":
            from app.research_web.scenario_pack_execution import quality_issues

            assert quality_issues(service, sid, receipt, context) == [
                "pack_computation_or_source_incomplete"
            ]
        else:
            from app.research_web.scenario_method_sources import quality_issues

            assert quality_issues(service, sid, receipt) == [
                "method_source_incomplete:owned-news-evidence"
            ]
    elif kind == "method" and ordering == "accepted_before_completion":
        acquire = service.lock.acquire

        async def observed_acquire():
            if entered.is_set() and not release.is_set():
                complete_waiting.set()
            return await acquire()

        monkeypatch.setattr(service.lock, "acquire", observed_acquire)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                cancel = executor.submit(client.post, cancel_path, json={})
                assert entered.wait(5)
                completing = executor.submit(client.post, complete_path, json=body, headers=headers)
                assert complete_waiting.wait(5)
                assert not completing.done()
                release.set()
                cancelled = cancel.result(timeout=10)
                assert cancelled.status_code == 200 and cancelled.json()["accepted"] is True
                response = completing.result(timeout=10)
        finally:
            release.set()
    else:
        if ordering == "cancel_not_accepted":
            cancelled = client.post(cancel_path, json={})
            assert cancelled.status_code == 200 and cancelled.json()["accepted"] is False
            # A different server task must not mutate this started record or
            # reinterpret the earlier unaccepted cancellation as authoritative.
            delivery = service.delivery.current(sid)
            actual_task = delivery["task_id"]
            previous = copy.deepcopy(record)
            delivery["task_id"] = "foreign-server-task"
            unknown = client.post(complete_path, json=body, headers=headers)
            assert unknown.status_code == 409 and record == previous
            assert unknown.json()["error"]["code"] == kind + "_execution_unknown_do_not_retry"
            delivery["task_id"] = actual_task
        response = client.post(complete_path, json=body, headers=headers)
    expected = "cancelled" if ordering == "accepted_before_completion" else "saved"
    assert response.status_code == 200 and response.json()["state"] == expected, response.text
    assert record["state"] == expected and record["native_result"]["status"] == "completed"
    assert calls.count("session.cancel") == 1
    previous = copy.deepcopy(record)
    retry = client.post(complete_path, json=body, headers=headers)
    assert retry.status_code == 409 and record == previous
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**admission, "call_id": "no-new-call-retry"},
        headers=headers,
    )
    assert retry.status_code == 409 and len(receipt[kind + "_executions"]) == 1
