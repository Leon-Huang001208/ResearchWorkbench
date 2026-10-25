"""Private single-PID drain primitive; no process or service is actually signalled."""

import signal
from types import SimpleNamespace

import pytest

from app.research_web import service_manager as module
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    _GracefulStopIdentity,
    _StateFact,
)
from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact


@pytest.fixture
def drain(tmp_path, monkeypatch):
    manager = WebServiceManager(project_root=tmp_path, data_root=tmp_path / "data")
    manager.data_root.mkdir(mode=0o700)
    process = SimpleNamespace(role="web", port=8088)
    from app.research_web.service_diagnostics import ServiceProbe

    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (
            ServiceProbe(
                "web", 8088, "valid", "alive", "owned", "listening", "passed", True, 4242, ()
            ),
        ),
    )
    identity = _GracefulStopIdentity("web", 8088, 4242, 100.0, ("python", "host.py"))
    state = {"alive": True, "birth": 100.0, "argv": identity.argv, "signals": [], "intent": 0}
    monkeypatch.setattr(module, "signature_matches_argv", lambda a, b: a == b)
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda _: _StateFact("valid", identity.pid, identity.argv, (), 100.0),
    )
    monkeypatch.setattr(
        module,
        "probe_process",
        lambda _: ProcessFact(
            "alive" if state["alive"] else "missing",
            "python host.py",
            None,
            state["argv"],
            state["birth"],
        ),
    )
    monkeypatch.setattr(
        module,
        "listener_pids",
        lambda _: ListenerFact(
            "listening" if state["alive"] else "closed",
            (identity.pid,) if state["alive"] else (),
            None,
        ),
    )

    def intent():
        state["intent"] += 1

    def kill(pid, sig):
        if sig == 0:
            return
        assert state["intent"] == 1
        state["signals"].append((pid, sig))
        state["alive"] = False

    monkeypatch.setattr(module.os, "kill", kill)
    with manager._installation_start_scope() as lease:
        yield manager, process, identity, state, intent, lease


def test_graceful_stop_records_intent_then_only_single_pid_term(drain):
    manager, process, identity, state, intent, lease = drain
    manager._graceful_stop_owned_once(
        process, identity, lease=lease, persist_signal_intent=intent, signal_already_attempted=False
    )
    assert state["signals"] == [(4242, signal.SIGTERM)]
    assert state["intent"] == 1


@pytest.mark.parametrize("change", ["birth", "argv"])
def test_pid_reuse_or_command_change_never_signalled(drain, change):
    manager, process, identity, state, intent, lease = drain
    state[change] = 101.0 if change == "birth" else ("other",)
    with pytest.raises(ServiceManagerError, match="身份变化"):
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=False,
        )
    assert state["signals"] == []
    assert state["intent"] == 0


def test_birth_race_after_durable_intent_blocks_signal(drain):
    manager, process, identity, state, _intent, lease = drain

    def intent():
        state["intent"] += 1
        state["birth"] = 200.0

    with pytest.raises(ServiceManagerError, match="身份变化"):
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=False,
        )
    assert state["signals"] == []
    assert state["intent"] == 1


def test_resume_never_resends_and_timeout_never_escalates(drain, monkeypatch):
    manager, process, identity, state, intent, lease = drain
    clock = iter([0, 100])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    with pytest.raises(ServiceManagerError) as error:
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=True,
            timeout=1,
        )
    assert error.value.code == "graceful_stop_pending"
    assert state["signals"] == []
    assert state["intent"] == 0


def test_foreign_listener_blocks_without_signal(drain, monkeypatch):
    manager, process, identity, state, intent, lease = drain
    monkeypatch.setattr(module, "listener_pids", lambda _: ListenerFact("listening", (9999,), None))
    with pytest.raises(ServiceManagerError, match="监听身份变化"):
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=False,
        )
    assert state["signals"] == []


def test_signal_failure_retains_intent_and_never_retries(drain, monkeypatch):
    manager, process, identity, state, intent, lease = drain
    attempted = []

    def fail(pid, sig):
        attempted.append((pid, sig))
        raise ProcessLookupError

    monkeypatch.setattr(module.os, "kill", fail)
    with pytest.raises(ServiceManagerError) as error:
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=False,
        )
    assert error.value.code == "graceful_stop_signal_unconfirmed"
    assert attempted == [(4242, signal.SIGTERM)]
    assert state["intent"] == 1


def test_first_signal_timeout_never_sends_force_or_second_term(drain, monkeypatch):
    manager, process, identity, state, intent, lease = drain
    monkeypatch.setattr(module.os, "kill", lambda pid, sig: state["signals"].append((pid, sig)))
    clock = iter([0, 100])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    with pytest.raises(ServiceManagerError) as error:
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=intent,
            signal_already_attempted=False,
            timeout=1,
        )
    assert error.value.code == "graceful_stop_pending"
    assert state["signals"] == [(4242, signal.SIGTERM)]
    assert state["intent"] == 1


def test_crash_while_recording_intent_does_not_send_signal(drain):
    manager, process, identity, state, _intent, lease = drain

    def crash():
        raise OSError("offline journal failure")

    with pytest.raises(OSError):
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=crash,
            signal_already_attempted=False,
        )
    assert state["signals"] == []


def test_missing_lease_refuses_before_intent_or_signal(drain):
    manager, process, identity, state, intent, _lease = drain
    with pytest.raises(ServiceManagerError) as error:
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=None,
            persist_signal_intent=intent,
            signal_already_attempted=False,
        )
    assert error.value.code == "lifecycle_lock_ownership_lost"
    assert state["signals"] == []
    assert state["intent"] == 0


def test_lost_lease_after_durable_intent_refuses_signal(drain):
    manager, process, identity, state, intent, lease = drain

    def lose_lease():
        intent()
        manager._lifecycle_lease = None

    with pytest.raises(ServiceManagerError) as error:
        manager._graceful_stop_owned_once(
            process,
            identity,
            lease=lease,
            persist_signal_intent=lose_lease,
            signal_already_attempted=False,
        )
    assert error.value.code == "lifecycle_lock_ownership_lost"
    assert state["signals"] == []
    assert state["intent"] == 1
