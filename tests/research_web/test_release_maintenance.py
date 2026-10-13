"""Task admission races and durable maintenance, without supplier calls."""

import asyncio
import json

import pytest

from app.research_web.client import RuntimeFailure
from app.research_web.maintenance import MaintenanceGate


@pytest.mark.asyncio
async def test_enter_blocks_new_work_but_preserves_admitted_work(tmp_path):
    gate = MaintenanceGate(tmp_path / "gate.json")
    admitted = asyncio.Event()
    finish = asyncio.Event()

    async def running():
        async with gate.admit():
            admitted.set()
            await finish.wait()
            async with gate.admit():
                assert gate.active == 1

    task = asyncio.create_task(running())
    await admitted.wait()
    await gate.begin("a" * 32)
    with pytest.raises(RuntimeFailure, match="维护"):
        async with gate.admit():
            pytest.fail("new request admitted")
    assert not task.done() and gate.active == 1
    finish.set()
    await task
    assert gate.active == 0
    reopened = MaintenanceGate(tmp_path / "gate.json")
    assert reopened.transaction == "a" * 32
    with pytest.raises(RuntimeFailure):
        await reopened.end("b" * 32)
    await reopened.end("a" * 32)
    async with reopened.admit():
        assert reopened.active == 1


@pytest.mark.asyncio
async def test_background_queued_work_waits_without_cancel_or_new_run(tmp_path):
    gate = MaintenanceGate(tmp_path / "gate.json")
    await gate.begin("a" * 32)
    reached = asyncio.Event()

    async def queued():
        async with gate.admit(background=True):
            reached.set()

    task = asyncio.create_task(queued())
    await asyncio.sleep(0)
    assert not reached.is_set() and not task.done()
    await gate.end("a" * 32)
    await task
    assert reached.is_set()


def test_invalid_or_alias_gate_fails_closed(tmp_path):
    path = tmp_path / "gate.json"
    path.write_text(json.dumps({"transaction": "invalid"}))
    with pytest.raises(RuntimeFailure):
        MaintenanceGate(path)


@pytest.mark.asyncio
async def test_persistence_failure_and_restart_never_reopen(tmp_path, monkeypatch):
    from app.research_web import maintenance

    path = tmp_path / "gate.json"
    gate = MaintenanceGate(path)
    with monkeypatch.context() as patch:
        patch.setattr(maintenance.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("fail")))
        with pytest.raises(RuntimeFailure):
            await gate.begin("a" * 32)
    assert gate.transaction == "a" * 32
    with pytest.raises(RuntimeFailure):
        MaintenanceGate(path)


@pytest.mark.asyncio
async def test_resume_requires_confirmed_controller_after_restart(tmp_path):
    path = tmp_path / "gate.json"
    gate = MaintenanceGate(path)
    await gate.begin("a" * 32)
    await gate.end("a" * 32)
    assert gate.transaction is None
    reopened = MaintenanceGate(path)
    assert reopened.transaction == "a" * 32
    with pytest.raises(RuntimeFailure):
        async with reopened.admit():
            pytest.fail("restarted instance silently reopened")
    path.unlink()
    path.symlink_to(tmp_path / "absent")
    with pytest.raises(RuntimeFailure):
        MaintenanceGate(path)
