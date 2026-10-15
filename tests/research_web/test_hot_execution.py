"""Hot accepted-but-lost research replies must reconcile without a second send."""
import asyncio
import copy
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.research_web.hot_handoff import execute_hot_handoff
from app.research_web.hot_service import HotWebError
from app.research_web.client import RuntimeFailure
from app.research_web.store import StoreError
from app.research_web.capabilities.models import CapabilityError


def fixture():
    run = {"runId": str(uuid4()), "sessionId": str(uuid4()), "state": "snapshot_ready", "revision": 1, "datasetId": str(uuid4()), "datasetManifestHash": "a" * 64, "evidenceManifestHash": "b" * 64, "deliveryKey": None}
    history = []
    async def call(operation, *args, **kwargs):
        if operation == "research_run":
            return copy.deepcopy(run)
        assert operation == "advance_research_run"
        params = args[0]
        assert params["expectedRevision"] == run["revision"]
        run.update({k: v for k, v in params.items() if k not in {"expectedRevision"}})
        run["revision"] += 1
        return copy.deepcopy(run)
    service = SimpleNamespace(workbench_lock=asyncio.Lock(), ensure_hot_session=AsyncMock(), store=SimpleNamespace(data={"receipts": {}}), client=SimpleNamespace(history=AsyncMock(side_effect=lambda _: history)), datahub=SimpleNamespace(snapshots=SimpleNamespace(detail=lambda *_: {"manifest_sha256": "a" * 64})), send=AsyncMock())
    return run, service, SimpleNamespace(call=call), history


@pytest.mark.asyncio
async def test_accepted_reply_loss_queries_the_exact_native_marker_without_resubmission():
    run, service, hot, history = fixture()
    async def lost(sid, text, key, **_kwargs):
        service.store.data["receipts"][f"{sid}:{key}"] = {"status": "unknown"}
        history.append({"event": {"type": "user/message", "data": {"content": [{"type": "text", "text": text}]}}})
        raise RuntimeFailure("synthetic accepted reply loss")
    service.send.side_effect = lost
    first = await execute_hot_handoff(service, hot, run["runId"], "研究固定资料")
    assert first["state"] == "execution_outcome_unknown"
    second = await execute_hot_handoff(service, hot, run["runId"], "研究固定资料")
    assert second["state"] == "running"
    assert service.send.call_count == 1
    assert service.client.history.call_count == 1
    with pytest.raises(HotWebError, match="另一研究请求"):
        await execute_hot_handoff(service, hot, run["runId"], "改变研究问题")


@pytest.mark.asyncio
async def test_ambiguous_crash_before_send_never_auto_submits_and_completed_replay_is_read_only():
    run, service, hot, history = fixture()
    await execute_hot_handoff(service, hot, run["runId"], "固定问题")
    assert service.send.call_count == 1
    run["state"] = "execution_starting"
    service.store.data["receipts"].clear()
    result = await execute_hot_handoff(service, hot, run["runId"], "固定问题")
    assert result["state"] == "execution_outcome_unknown"
    assert service.send.call_count == 1
    run["state"] = "completed"
    result = await execute_hot_handoff(service, hot, run["runId"], "固定问题")
    assert result["state"] == "completed"
    assert service.send.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [StoreError("fixture"), OSError("fixture"), CapabilityError("fixture")])
@pytest.mark.parametrize("reserved", [False, True])
async def test_pre_submit_errors_are_failed_only_without_receipt(failure, reserved):
    run, service, hot, _ = fixture()
    async def fail(sid, _text, key, **_kwargs):
        if reserved:
            service.store.data["receipts"][f"{sid}:{key}"] = {"status": "pending"}
        raise failure
    service.send.side_effect = fail
    result = await execute_hot_handoff(service, hot, run["runId"], "fixed question")
    assert result["state"] == ("execution_outcome_unknown" if reserved else "failed")
    assert result["executionStarted"] is (None if reserved else False)


@pytest.mark.asyncio
async def test_failed_after_acceptance_is_never_reported_as_not_submitted():
    run, service, hot, _ = fixture()
    async def accept(sid, _text, key, **_kwargs):
        service.store.data["receipts"][f"{sid}:{key}"] = {"status": "accepted"}
    service.send.side_effect = accept
    await execute_hot_handoff(service, hot, run["runId"], "fixed question")
    run["state"] = "failed"
    result = await execute_hot_handoff(service, hot, run["runId"], "fixed question")
    assert result["executionStarted"] is True
    service.store.data["receipts"].clear()
    result = await execute_hot_handoff(service, hot, run["runId"], "fixed question")
    assert result["executionStarted"] is None
