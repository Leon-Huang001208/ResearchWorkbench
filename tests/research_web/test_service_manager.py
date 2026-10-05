import io
import json
import multiprocessing
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from app.research_web import lifecycle_lock as lifecycle_lock_module
from app.research_web import runtime_auth as runtime_auth_module
from app.research_web import service_diagnostics as service_diagnostics_module
from app.research_web import service_manager as service_manager_module
from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError
from app.research_web.service_diagnostics import ServiceProbe
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    _is_unsafe_private_directory,
    format_doctor_status,
    format_status,
)
from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact


def _test_pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_process(path: str, entered, release, results, *, crash: bool = False) -> None:
    try:
        with LifecycleLock(Path(path), _test_pid_exists):
            entered.set()
            if crash:
                os._exit(0)
            results.put(("entered", os.getpid()))
            release.wait(5)
    except LifecycleLockError as exc:
        results.put(("error", exc.code))


def _paused_stale_recovery_process(path: str, observed, resume, hold, results) -> None:
    target = Path(path)
    original = LifecycleLock._read_owner.__func__

    def paused_read(cls, directory):
        owner = original(cls, directory)
        if directory == target:
            observed.set()
            resume.wait(5)
        return owner

    LifecycleLock._read_owner = classmethod(paused_read)
    try:
        with LifecycleLock(target, _test_pid_exists):
            results.put(("entered", os.getpid()))
            hold.wait(5)
    except LifecycleLockError as exc:
        results.put(("error", exc.code))


def _write_lock_owner(path: Path, *, pid: int, token: str = "a" * 32) -> None:
    path.mkdir(mode=0o700)
    owner = path / "owner.json"
    owner.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": pid,
                "token": token,
                "started_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    owner.chmod(0o600)


def _prepare_log_ownership(manager, monkeypatch):
    manager.run_root.mkdir(parents=True, mode=0o700)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    for process in manager._processes():
        manager._write_state(process, 123456)


# The complete import-graph regression remains below with its subprocess assertions.
def test_lifecycle_lock_rejects_live_owner_and_two_contenders(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"

    with LifecycleLock(path, lambda pid: pid == os.getpid(), pid=os.getpid()):
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
        assert set(owner) == {"schema_version", "pid", "token", "started_at"}
        assert owner["pid"] == os.getpid()
        assert len(owner["token"]) == 32
        assert path.stat().st_mode & 0o777 == 0o700
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert (path / "owner.json").stat().st_mode & 0o777 == 0o600

        with (
            pytest.raises(LifecycleLockError) as captured,
            LifecycleLock(path, lambda _pid: True, pid=os.getpid() + 1),
        ):
            pytest.fail("a live owner must exclude a second contender")

        assert captured.value.code == "lifecycle_busy"
        assert "lifecycle_busy" in str(captured.value)

    assert not path.exists()

def test_native_doctor_adds_mode_without_changing_previous_payload(manager, monkeypatch):
    previous = {"schema_version": 1, "ok": True, "issues": [],
                **{key: {"ready": True} for key in ("python", "node", "cjpy", "dsh", "data")}}
    probes = tuple(ServiceProbe(role, port, "missing", "missing", "unknown", "closed",
                                "not_run", False, None, ())
                   for role, port in (("runtime", 3081), ("web", 8088)))
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: previous)
    monkeypatch.setattr(manager, "_service_probes", lambda: probes)
    report = manager.doctor()
    assert report["runtime_mode"] == "native"
    assert report["schema_version"] == 2
    assert report["installation_ok"] and not report["product_ready"]
    assert report["services"] == {probe.role: probe.public() for probe in probes}
    assert all(report[key] == previous[key] for key in ("python", "node", "cjpy", "dsh", "data"))


def test_native_logs_tail_and_secret_line_redaction(manager, monkeypatch):
    output_stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output_stream)
    manager.log_root.mkdir(parents=True, mode=0o700)
    _prepare_log_ownership(manager, monkeypatch)
    (manager.log_root / "web.log").write_text("old\nready\nCookie: fake-secret\nlatest\n")
    (manager.log_root / "runtime.log").write_text("dsh web: http://127.0.0.1:3081/?token=fake-secret\n")
    (manager.log_root / "unrelated.log").write_text("must-not-read")
    assert manager.logs(tail=3) == 0
    output = output_stream.getvalue()
    assert "latest" in output and "ready" in output
    assert "fake-secret" not in output and "must-not-read" not in output and "old" not in output


@pytest.mark.parametrize("identity_failure", ["pid_reused", "substring_argv"])
def test_native_logs_share_strict_process_identity(manager, monkeypatch, identity_failure):
    _prepare_log_ownership(manager, monkeypatch)
    monkeypatch.setattr(manager, "_pid_exists", lambda _pid: True)
    signatures = tuple(part for spec in manager._processes() for part in spec.signature)
    argv = signatures if identity_failure == "pid_reused" else tuple(part + "-foreign" for part in signatures)
    monkeypatch.setattr(manager, "_command_line", lambda _pid: " ".join(argv))
    monkeypatch.setattr(service_manager_module, "probe_process", lambda _pid:
                        ProcessFact("alive", " ".join(argv), None, argv,
                                    0.0 if identity_failure == "pid_reused" else time.time()))
    with pytest.raises(ServiceManagerError, match="native_logs_ownership_unknown"):
        manager._validate_log_ownership()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory"])
def test_native_logs_reject_unsafe_known_file(manager, monkeypatch, kind):
    manager.log_root.mkdir(parents=True, mode=0o700)
    _prepare_log_ownership(manager, monkeypatch)
    target = manager.log_root / "web.log"
    foreign = manager.project_root / "foreign"
    foreign.write_text("secret")
    if kind == "symlink":
        target.symlink_to(foreign)
    elif kind == "hardlink":
        os.link(foreign, target)
    else:
        target.mkdir()
    with pytest.raises(ServiceManagerError, match="native_logs_unsafe"):
        manager.logs()


def test_native_logs_refuse_unknown_owner_before_output(manager, monkeypatch):
    output_stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output_stream)
    manager.run_root.mkdir(parents=True, mode=0o700)
    path = manager.run_root / "web.json"
    path.write_text('{"pid": 123, "version": 9}')
    path.chmod(0o600)
    with pytest.raises(ServiceManagerError, match="native_logs_ownership_unknown"):
        manager.logs()
    assert output_stream.getvalue() == ""
    assert path.exists()


def test_native_logs_byte_limit_and_zero_tail(manager, monkeypatch):
    output_stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output_stream)
    manager.log_root.mkdir(parents=True, mode=0o700)
    _prepare_log_ownership(manager, monkeypatch)
    (manager.log_root / "web.log").write_text("x" * 100000 + "\nlatest\n")
    assert manager.logs(tail=0) == 0
    assert output_stream.getvalue() == ""
    assert manager.logs(tail=10000) == 0
    output = output_stream.getvalue()
    assert len(output.encode()) <= 65536 and "latest" in output


def test_native_redacted_output_stays_bounded(manager, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    _prepare_log_ownership(manager, monkeypatch)
    manager.log_root.mkdir(parents=True, mode=0o700)
    for role in ("runtime", "web"):
        (manager.log_root / f"{role}.log").write_text("token\n" * 10000)
    assert manager.logs(tail=10000) == 0
    assert len(output.getvalue().encode()) <= 65536


def test_native_follow_emits_new_lines_and_stops_at_deadline(manager, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    _prepare_log_ownership(manager, monkeypatch)
    manager.log_root.mkdir(parents=True, mode=0o700)
    path = manager.log_root / "web.log"
    path.write_text("old\n")
    clock = [0]
    monkeypatch.setattr(service_manager_module.time, "monotonic", lambda: clock[0])
    def advance(seconds):
        with path.open("a") as stream:
            stream.write("new\n")
        clock[0] = 301
    monkeypatch.setattr(service_manager_module.time, "sleep", advance)
    with pytest.raises(ServiceManagerError, match="native_logs_limit"):
        manager.logs(tail=0, follow=True)
    assert output.getvalue() == "new\n"


def test_native_logs_valid_state_ignores_foreign_docker_state(manager, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    manager.run_root.mkdir(parents=True, mode=0o700)
    manager.log_root.mkdir(mode=0o700)
    for process in manager._processes():
        manager._write_state(process, 123456)
        (manager.log_root / f"{process.role}.log").write_text("ready\n")
    docker = manager.run_root / "docker"
    docker.mkdir(mode=0o700)
    (docker / "web.json").write_text("foreign malformed state")
    assert manager.logs() == 0
    assert output.getvalue() == "ready\nready\n"
    assert (manager.run_root / "web.json").exists()


def test_native_logs_insertion_after_ownership_check_refuses_all_output(manager, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    manager.run_root.mkdir(parents=True, mode=0o700)
    manager.log_root.mkdir(mode=0o700)
    manager._write_state(manager._processes()[0], 123456)
    (manager.log_root / "runtime.log").write_text("owned-ready\n")
    original = manager._validate_log_ownership
    def insert_unowned():
        proof = original()
        (manager.log_root / "web.log").write_text("unowned-content\n")
        return proof
    monkeypatch.setattr(manager, "_validate_log_ownership", insert_unowned)
    with pytest.raises(ServiceManagerError, match="native_logs_ownership_unknown"):
        manager.logs()
    assert output.getvalue() == ""
    assert not (manager.run_root / "web.json").exists()


@pytest.mark.parametrize("mutation", ["state", "file", "vanish"])
def test_native_logs_recheck_state_and_file_before_any_output(manager, monkeypatch, mutation):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    manager.run_root.mkdir(parents=True, mode=0o700)
    manager.log_root.mkdir(mode=0o700)
    for process in manager._processes():
        manager._write_state(process, 123456)
        (manager.log_root / f"{process.role}.log").write_text("owned-ready\n")
    original = os.open
    def mutate_before_second_read(name, flags, *args, **kwargs):
        if str(name).endswith("web.log"):
            if mutation == "state":
                (manager.run_root / "runtime.json").unlink()
            elif mutation == "vanish":
                (manager.log_root / "web.log").unlink()
            else:
                (manager.log_root / "runtime.log").unlink()
                (manager.log_root / "runtime.log").write_text("replacement\n")
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", mutate_before_second_read)
    with pytest.raises(ServiceManagerError, match="native_logs_(ownership_unknown|changed)"):
        manager.logs()
    assert output.getvalue() == ""


@pytest.mark.parametrize("control", ["\x00", "\x1b", "\x07", "\x1c", "\r", "\t"])
def test_native_logs_normalize_before_redaction(manager, monkeypatch, control):
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    manager.run_root.mkdir(parents=True, mode=0o700)
    manager.log_root.mkdir(mode=0o700)
    for process in manager._processes():
        manager._write_state(process, 123456)
        (manager.log_root / f"{process.role}.log").write_text(f"Coo{control}kie: fake-session-value\n")
    assert manager.logs() == 0
    assert "fake-session-value" not in output.getvalue()


def test_lifecycle_lock_recovers_confirmed_dead_owner_once(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)

    with LifecycleLock(path, lambda pid: pid != 424242, pid=os.getpid()):
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["token"] != "a" * 32

    assert list(path.parent.iterdir()) == [path.with_name(f"{path.name}.guard")]


@pytest.mark.parametrize(
    "owner_payload",
    [
        "{",
        json.dumps(
            {
                "schema_version": 1,
                "pid": True,
                "token": "a" * 32,
                "started_at": 0,
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "pid": 123,
                "token": "not-a-token",
                "started_at": 0,
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "pid": 123,
                "token": "a" * 32,
                "started_at": 10**500,
            }
        ),
        "[" * 1100 + "0" + "]" * 1100,
        json.dumps({"huge": "x" * 5000}),
    ],
    ids=["malformed", "bool-pid", "bad-token", "huge-time", "deep", "oversize"],
)
def test_lifecycle_lock_treats_malformed_or_unbounded_owner_as_busy(tmp_path, owner_payload):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    path.mkdir(mode=0o700)
    owner = path / "owner.json"
    owner.write_text(owner_payload, encoding="utf-8")
    owner.chmod(0o600)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("malformed ownership must never be reclaimed")

    assert captured.value.code == "lifecycle_busy"
    assert path.exists()


def test_lifecycle_lock_rejects_alias_and_hardlinked_owner(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    actual = run_root / "actual.lock"
    _write_lock_owner(actual, pid=424242)
    alias = run_root / "lifecycle.lock"
    alias.symlink_to(actual, target_is_directory=True)

    with (
        pytest.raises(LifecycleLockError, match="busy") as alias_error,
        LifecycleLock(alias, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("directory aliases are not lock ownership")
    assert alias_error.value.code == "lifecycle_busy"

    alias.unlink()
    owner = actual / "owner.json"
    os.link(owner, run_root / "owner-alias.json")
    with (
        pytest.raises(LifecycleLockError) as hardlink_error,
        LifecycleLock(actual, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("hardlinked owner files are not reclaimable")
    assert hardlink_error.value.code == "lifecycle_busy"


def test_lifecycle_lock_rejects_parent_alias_and_unexpected_lock_content(tmp_path):
    actual_parent = tmp_path / "actual"
    actual_parent.mkdir(mode=0o700)
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(actual_parent, target_is_directory=True)

    with (
        pytest.raises(LifecycleLockError) as alias_error,
        LifecycleLock(alias_parent / "lifecycle.lock", lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("parent aliases must not redirect lifecycle ownership")
    assert alias_error.value.code == "lifecycle_busy"

    path = actual_parent / "lifecycle.lock"
    _write_lock_owner(path, pid=424242)
    (path / "unexpected").write_text("keep", encoding="utf-8")
    with (
        pytest.raises(LifecycleLockError) as content_error,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("unexpected lock content must not be deleted")
    assert content_error.value.code == "lifecycle_busy"
    assert (path / "owner.json").exists()
    assert (path / "unexpected").read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits do not prove Windows ACLs")
@pytest.mark.parametrize("lock_mode", [0o755, 0o701, 0o777])
def test_lifecycle_lock_rejects_non_private_existing_directory_modes(tmp_path, lock_mode):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)
    path.chmod(lock_mode)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("an unsafe directory mode must never be reclaimed")

    assert captured.value.code == "lifecycle_busy"
    assert stat.S_IMODE(path.stat().st_mode) == lock_mode
    assert (path / "owner.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits do not prove Windows ACLs")
@pytest.mark.parametrize("owner_mode", [0o400, 0o200, 0o000, 0o644, 0o601])
def test_lifecycle_lock_rejects_non_exact_existing_owner_modes(tmp_path, owner_mode):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)
    owner = path / "owner.json"
    owner.chmod(owner_mode)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("an unsafe owner mode must never be reclaimed")

    assert captured.value.code == "lifecycle_busy"
    assert stat.S_IMODE(owner.stat().st_mode) == owner_mode
    assert path.exists()


@pytest.mark.skipif(os.name == "nt", reason="uses the native POSIX advisory lock")
def test_lifecycle_guard_prevents_stale_lock_aba_between_real_contenders(tmp_path):
    context = multiprocessing.get_context("fork")
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)
    observed = context.Event()
    resume = context.Event()
    hold = context.Event()
    results = context.Queue()
    first = context.Process(
        target=_paused_stale_recovery_process,
        args=(str(path), observed, resume, hold, results),
    )
    second_entered = context.Event()
    second_release = context.Event()
    second = context.Process(
        target=_lock_process,
        args=(str(path), second_entered, second_release, results),
    )
    third_entered = context.Event()
    third_release = context.Event()
    third = context.Process(
        target=_lock_process,
        args=(str(path), third_entered, third_release, results),
    )
    try:
        first.start()
        assert observed.wait(5)
        second.start()
        second.join(5)
        assert second.exitcode == 0
        assert results.get(timeout=2) == ("error", "lifecycle_busy")
        assert not second_entered.is_set()

        resume.set()
        assert results.get(timeout=5)[0] == "entered"
        third.start()
        third.join(5)
        assert third.exitcode == 0
        assert results.get(timeout=2) == ("error", "lifecycle_busy")
        assert not third_entered.is_set()
    finally:
        resume.set()
        hold.set()
        second_release.set()
        third_release.set()
        for process in (first, second, third):
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(2)


@pytest.mark.skipif(os.name == "nt", reason="uses the native POSIX advisory lock")
def test_lifecycle_guard_is_released_by_process_crash_and_persists(tmp_path):
    context = multiprocessing.get_context("fork")
    path = tmp_path / "run" / "lifecycle.lock"
    entered = context.Event()
    release = context.Event()
    results = context.Queue()
    crashed = context.Process(
        target=_lock_process,
        args=(str(path), entered, release, results),
        kwargs={"crash": True},
    )

    crashed.start()
    assert entered.wait(5)
    crashed.join(5)
    assert crashed.exitcode == 0

    with LifecycleLock(path, _test_pid_exists):
        assert path.exists()

    guard = path.with_name(f"{path.name}.guard")
    assert guard.is_file()
    assert stat.S_IMODE(guard.stat().st_mode) == 0o600


def test_shared_process_specs_preserve_native_commands_and_are_immutable(manager):
    from dataclasses import FrozenInstanceError

    from app.research_web.process_spec import build_process_specs

    specs = build_process_specs(
        python=manager.python,
        node=manager.node,
        project_root=manager.project_root,
        data_root=manager.data_root,
        runtime_source=manager.runtime_source,
        state_root=manager.data_root / "runtime",
        web_host="127.0.0.1",
        web_port=8088,
        runtime_port=3081,
    )
    assert specs.runtime.command == (
        manager.python,
        "-m",
        "app.research_web.launch_runtime",
        "--source",
        str(manager.runtime_source),
        "--data",
        str(manager.data_root),
        "--node",
        manager.node,
        "--port",
        "3081",
        "--datahub-url",
        "http://127.0.0.1:8088",
        "--research-tools",
    )
    assert specs.web.command == (
        manager.python,
        "-m",
        "uvicorn",
        "app.research_web.main:app",
        "--app-dir",
        str(manager.project_root),
        "--host",
        "127.0.0.1",
        "--port",
        "8088",
    )
    assert (specs.runtime, specs.web) == manager._processes()
    assert specs.runtime_state_root == manager.data_root / "runtime"
    with pytest.raises(FrozenInstanceError):
        specs.web.port = 9999
    with pytest.raises(FrozenInstanceError):
        specs.runtime_state_root = Path("/other")


def test_shared_container_specs_change_only_state_and_web_host(manager):
    from app.research_web.process_spec import build_process_specs

    options = dict(
        python=manager.python,
        node=manager.node,
        project_root=manager.project_root,
        data_root=manager.data_root,
        runtime_source=manager.runtime_source,
        web_port=18088,
        runtime_port=13081,
    )
    native = build_process_specs(
        **options, state_root=manager.data_root / "runtime", web_host="127.0.0.1"
    )
    container = build_process_specs(**options, state_root=Path("/state"), web_host="0.0.0.0")
    assert container.runtime.command == native.runtime.command + ("--state", "/state")
    assert container.runtime.signature == (
        native.runtime.signature[0],
        "/state/overlay.yml",
        "13081",
    )
    assert container.web.command == tuple(
        "0.0.0.0" if part == "127.0.0.1" else part for part in native.web.command
    )
    assert container.web.signature == native.web.signature


@pytest.mark.parametrize(
    "unsafe", ["writable", "symlink", "ancestor_symlink", "ancestor_writable", "file"]
)
@pytest.mark.parametrize("operation", ["prepare", "read_auth", "write_auth", "spawn", "build_lock"])
def test_manager_rejects_unsafe_state_before_file_access(manager, monkeypatch, unsafe, operation):
    if os.name == "nt" and unsafe != "file":
        pytest.skip("POSIX mode and symlink fixtures; Windows semantics tested separately")
    state = manager.project_root / "private-state"
    target = manager.project_root / "target"
    target.mkdir(mode=0o700)
    if unsafe == "writable":
        state.mkdir(mode=0o777)
        state.chmod(0o777)
    elif unsafe == "symlink":
        state.symlink_to(target, target_is_directory=True)
    elif unsafe == "ancestor_symlink":
        alias = manager.project_root / "alias"
        alias.symlink_to(target, target_is_directory=True)
        state = alias / "state"
        (target / "state").mkdir(mode=0o700)
    elif unsafe == "ancestor_writable":
        target.chmod(0o777)
        state = target / "state"
        state.mkdir(mode=0o700)
    else:
        state.write_text("not a directory")
    manager.runtime_state_root = state
    (manager.runtime_source / "package.json").write_text('{"version":"test"}')
    accesses = []
    original_open = Path.open
    original_unlink = Path.unlink
    original_os_open = os.open

    def checked_os_open(path, *args, **kwargs):
        if str(path) == "build-lock.json":
            pytest.fail("build lock accessed before rejecting unsafe directory")
        return original_os_open(path, *args, **kwargs)

    def checked_open(path, *args, **kwargs):
        if path.parent == state:
            accesses.append(path.name)
            pytest.fail("state file accessed before rejecting unsafe directory")
        return original_open(path, *args, **kwargs)

    def checked_unlink(path, *args, **kwargs):
        if path.parent == state:
            accesses.append(path.name)
            pytest.fail("state file deleted before rejecting unsafe directory")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(Path, "unlink", checked_unlink)
    monkeypatch.setattr(os, "open", checked_os_open)
    monkeypatch.setattr(
        service_manager_module,
        "read_runtime_auth_record",
        lambda _path: pytest.fail("auth reader reached unsafe state"),
    )
    if operation == "read_auth":
        assert manager._read_runtime_auth() is None
    elif operation == "build_lock":
        assert not manager._runtime_build_lock_matches(
            {"closure_sha256": "a" * 64, "closure_files": 3}
        )
    else:
        with pytest.raises(ServiceManagerError):
            if operation == "prepare":
                manager._prepare_private_directories()
            elif operation == "write_auth":
                manager._write_runtime_auth("dsh-auth-test=value")
            else:
                manager._spawn(manager._processes()[0])
    assert not accesses


def test_manager_explicit_state_keeps_native_ownership_and_persistent_work(manager, monkeypatch):
    state = manager.project_root / "state"
    isolated = WebServiceManager(
        project_root=manager.project_root,
        data_root=manager.data_root,
        runtime_source=manager.runtime_source,
        runtime_state_root=state,
        python=manager.python,
        node=manager.node,
    )
    isolated._prepare_private_directories()
    (manager.runtime_source / "package.json").write_text('{"version":"test"}')
    record = isolated._write_runtime_auth("dsh-auth-test=value")
    assert isolated.run_root == manager.run_root
    assert isolated.log_root == manager.log_root
    assert isolated._runtime_auth_path() == state / "auth.json"
    assert record["cwd"] == str((manager.data_root / "runtime/work").resolve())
    assert isolated._read_runtime_auth() == record
    captured = {}

    def popen(command, **options):
        captured.update(options)
        return type("Process", (), {"pid": 4321})()

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", popen)
    monkeypatch.setattr(isolated, "_write_state", lambda *_args: None)
    isolated._spawn(isolated._processes()[1])
    assert captured["env"]["RESEARCH_RUNTIME_AUTH"] == str(state / "auth.json")
    assert isolated._processes()[0].signature[1] == str(state / "overlay.yml")
    lock = {
        "source_commit": service_manager_module.PINNED_COMMIT,
        "closure_sha256": "a" * 64,
        "closure_files": 3,
        "mode": "build",
    }
    (state / "build-lock.json").write_text(json.dumps(lock))
    (state / "build-lock.json").chmod(0o600)
    assert isolated._runtime_build_lock_matches(lock)


@pytest.mark.skipif(os.name == "nt", reason="Legacy POSIX directory permissions")
@pytest.mark.parametrize("layout", ["legacy_native", "public_parent", "custom"])
def test_legacy_native_state_reads_preserve_permissions(manager, monkeypatch, layout):
    manager._prepare_private_directories()
    state = manager.data_root / "runtime"
    if layout == "custom":
        state = manager.project_root / "custom-state"
        manager.runtime_state_root = state
    state.mkdir(mode=0o755)
    state.chmod(0o755)
    if layout == "public_parent":
        manager.data_root.chmod(0o755)
    auth = {
        "authority": "127.0.0.1:3081",
        "cookie": "dsh-auth-test=value",
        "cwd": str((manager.data_root / "runtime/work").resolve()),
        "source_commit": service_manager_module.PINNED_COMMIT,
        "version": "test",
    }
    lock = {
        "source_commit": service_manager_module.PINNED_COMMIT,
        "closure_sha256": "a" * 64,
        "closure_files": 3,
        "mode": "build",
    }
    for name, record in (("auth.json", auth), ("build-lock.json", lock)):
        (state / name).write_text(json.dumps(record))
        (state / name).chmod(0o600)
    monkeypatch.setattr(os, "chmod", lambda *_args, **_kwargs: pytest.fail("read path chmod"))
    monkeypatch.setattr(Path, "chmod", lambda *_args, **_kwargs: pytest.fail("read path chmod"))
    if layout == "legacy_native":
        manager._prepare_private_directories()
        assert manager._read_runtime_auth() == auth
        assert manager._runtime_build_lock_matches(lock)
        assert manager._processes()[0].command[-1] == "--research-tools"
        assert state.stat().st_mode & 0o777 == 0o755
    else:
        with pytest.raises(ServiceManagerError):
            manager._prepare_private_directories()
        assert manager._read_runtime_auth() is None
        assert not manager._runtime_build_lock_matches(lock)


@pytest.mark.skipif(os.name == "nt", reason="Legacy POSIX directory permissions")
def test_legacy_native_state_supports_owned_start_stop_and_auth_write(manager, monkeypatch):
    manager._prepare_private_directories()
    state = manager.data_root / "runtime"
    state.mkdir(mode=0o755)
    state.chmod(0o755)
    (manager.runtime_source / "package.json").write_text('{"version":"test"}')
    record = manager._write_runtime_auth("dsh-auth-test=value")
    assert manager._read_runtime_auth() == record
    runtime = manager._processes()[0]
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: type("Process", (), {"pid": 4321})(),
    )
    monkeypatch.setattr(manager, "_write_state", lambda *_args: None)
    assert manager._spawn(runtime) == 4321
    manager._write_runtime_auth("dsh-auth-test=value")
    owned = ServiceProbe("runtime", 3081, "valid", "alive", "owned", "listening",
                         "passed", True, 4321, ())
    absent = ServiceProbe("runtime", 3081, "stale", "missing", "unknown", "closed",
                          "not_run", False, None, ())
    observations = iter((owned, owned, absent))
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(observations))
    monkeypatch.setattr(manager, "_remove_exact_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_terminate_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_pid_exists", lambda _pid: False)
    assert manager._stop_one(runtime)
    assert not manager._runtime_auth_path().exists()
    assert state.stat().st_mode & 0o777 == 0o755


# The complete callback-origin/proxy regression remains below.
def test_lifecycle_guard_rejects_alias_hardlink_and_intermediate_ancestor_alias(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    path = run_root / "lifecycle.lock"
    guard = path.with_name(f"{path.name}.guard")
    guard.write_text("", encoding="utf-8")
    guard.chmod(0o600)
    os.link(guard, tmp_path / "guard-alias")

    with (
        pytest.raises(LifecycleLockError) as hardlink_error,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("a hardlinked guard must not establish ownership")
    assert hardlink_error.value.code == "lifecycle_busy"
    assert not path.exists()

    (tmp_path / "guard-alias").unlink()
    guard.unlink()
    outside = tmp_path / "outside"
    (outside / "nested").mkdir(parents=True, mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    aliased_path = alias / "nested" / "lifecycle.lock"

    with (
        pytest.raises(LifecycleLockError) as ancestor_error,
        LifecycleLock(
            aliased_path,
            lambda _pid: False,
            pid=os.getpid(),
            trusted_root=tmp_path,
        ),
    ):
        pytest.fail("an intermediate ancestor alias must not redirect ownership")
    assert ancestor_error.value.code == "lifecycle_busy"
    assert not (outside / "nested" / "lifecycle.lock").exists()
    assert not (outside / "nested" / "lifecycle.lock.guard").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits do not prove Windows ACLs")
@pytest.mark.parametrize("guard_mode", [0o400, 0o644, 0o601])
def test_lifecycle_guard_requires_exact_private_posix_mode(tmp_path, guard_mode):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    guard = path.with_name(f"{path.name}.guard")
    guard.write_text("", encoding="utf-8")
    guard.chmod(guard_mode)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("an unsafe guard mode must not establish ownership")

    assert captured.value.code == "lifecycle_busy"
    assert stat.S_IMODE(guard.stat().st_mode) == guard_mode
    assert not path.exists()


@pytest.mark.skipif(
    sys.platform != "darwin" or not Path("/var").is_symlink(),
    reason="requires the real macOS /var system alias",
)
def test_lifecycle_lock_accepts_system_alias_above_explicit_trusted_root(tmp_path):
    resolved = str(tmp_path)
    assert resolved.startswith("/private/var/")
    lexical_tmp = Path("/var") / Path(resolved).relative_to("/private/var")
    trusted_root = lexical_tmp / "managed"
    trusted_root.mkdir(mode=0o700)
    path = trusted_root / "run" / "lifecycle.lock"

    with LifecycleLock(
        path,
        _test_pid_exists,
        trusted_root=trusted_root,
    ):
        assert path.exists()

    assert not path.exists()
    assert path.with_name(f"{path.name}.guard").exists()


def test_lifecycle_lock_rejects_symlinked_trusted_root_without_outside_mutation(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    trusted_alias = tmp_path / "trusted"
    trusted_alias.symlink_to(actual, target_is_directory=True)
    path = trusted_alias / "run" / "lifecycle.lock"

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(
            path,
            _test_pid_exists,
            trusted_root=trusted_alias,
        ),
    ):
        pytest.fail("the trusted root itself cannot be an alias")

    assert captured.value.code == "lifecycle_busy"
    assert list(actual.iterdir()) == []


def test_lifecycle_lock_rejects_alias_inside_trusted_root_without_outside_mutation(tmp_path):
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    (outside / "nested").mkdir(parents=True)
    (trusted_root / "alias").symlink_to(outside, target_is_directory=True)
    path = trusted_root / "alias" / "nested" / "lifecycle.lock"

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(
            path,
            _test_pid_exists,
            trusted_root=trusted_root,
        ),
    ):
        pytest.fail("an alias inside the trusted root cannot redirect lock ownership")

    assert captured.value.code == "lifecycle_busy"
    assert not (outside / "nested" / "lifecycle.lock").exists()
    assert not (outside / "nested" / "lifecycle.lock.guard").exists()


@pytest.mark.parametrize("outside_kind", ["sibling", "traversal"])
def test_lifecycle_lock_rejects_paths_outside_lexical_trusted_root(tmp_path, outside_kind):
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    path = (
        outside / "lifecycle.lock"
        if outside_kind == "sibling"
        else trusted_root / ".." / "outside" / "lifecycle.lock"
    )
    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(
            path,
            _test_pid_exists,
            trusted_root=trusted_root,
        ),
    ):
        pytest.fail("the lock path must remain within the lexical trusted root")

    assert captured.value.code == "lifecycle_busy"
    assert not outside.exists()


def test_directory_fsync_is_posix_only(tmp_path, monkeypatch):
    events: list[object] = []
    monkeypatch.setattr(
        lifecycle_lock_module.os,
        "open",
        lambda path, flags: events.append((Path(path), flags)) or 91,
    )
    monkeypatch.setattr(
        lifecycle_lock_module.os,
        "fsync",
        lambda handle: events.append(("fsync", handle)),
    )
    monkeypatch.setattr(
        lifecycle_lock_module.os,
        "close",
        lambda handle: events.append(("close", handle)),
    )

    lifecycle_lock_module._fsync_directory(tmp_path, platform_name="nt")
    assert events == []

    lifecycle_lock_module._fsync_directory(tmp_path, platform_name="posix")
    assert events[0][0] == tmp_path
    assert events[1:] == [("fsync", 91), ("close", 91)]


def test_lock_owner_write_skips_directory_fsync_on_windows_model(tmp_path, monkeypatch):
    path = tmp_path / "lifecycle.lock"
    path.mkdir(mode=0o700)
    lock = LifecycleLock(path, lambda _pid: False, pid=os.getpid())
    observed: list[str] = []
    monkeypatch.setattr(
        lifecycle_lock_module,
        "_fsync_directory",
        lambda _path, *, platform_name=None: observed.append(str(platform_name)),
    )

    lock._write_owner(platform_name="nt")

    assert observed == ["nt"]


def test_lifecycle_guard_uses_nonblocking_windows_locking_model(tmp_path, monkeypatch):
    path = tmp_path / "run" / "lifecycle.lock"
    lock = LifecycleLock(path, lambda _pid: False, pid=os.getpid())
    events: list[tuple[int, int, int]] = []

    class WindowsLocking:
        LK_NBLCK = 2
        LK_UNLCK = 3

        @staticmethod
        def locking(handle, mode, size):
            events.append((handle, mode, size))

    monkeypatch.setattr(lifecycle_lock_module, "msvcrt", WindowsLocking)
    lock._prepare_parent()

    lock._acquire_guard(platform_name="nt")
    handle = lock._guard_handle
    lock._release_guard(platform_name="nt")

    assert events == [(handle, WindowsLocking.LK_NBLCK, 1), (handle, WindowsLocking.LK_UNLCK, 1)]


def test_windows_ancestor_validation_rejects_modeled_reparse_component(tmp_path, monkeypatch):
    intermediate = tmp_path / "intermediate"
    target = intermediate / "nested"
    target.mkdir(parents=True)
    reparse_inode = intermediate.lstat().st_ino
    monkeypatch.setattr(
        LifecycleLock,
        "_is_reparse",
        staticmethod(lambda identity: identity.st_ino == reparse_inode),
    )

    with pytest.raises(LifecycleLockError) as captured:
        LifecycleLock._validate_existing_ancestors(target, platform_name="nt")

    assert captured.value.code == "lifecycle_busy"


@pytest.mark.skipif(os.name == "nt", reason="uses the native POSIX advisory lock")
def test_guard_unlock_failure_after_success_is_coded_and_path_free(tmp_path, monkeypatch):
    path = tmp_path / "run" / "lifecycle.lock"
    lock = LifecycleLock(path, _test_pid_exists)
    lock.__enter__()
    original = lifecycle_lock_module.fcntl.flock

    def fail_unlock(handle, operation):
        if operation == lifecycle_lock_module.fcntl.LOCK_UN:
            raise OSError("private unlock detail")
        return original(handle, operation)

    monkeypatch.setattr(lifecycle_lock_module.fcntl, "flock", fail_unlock)

    with pytest.raises(LifecycleLockError) as captured:
        lock.__exit__(None, None, None)

    assert captured.value.code == "lifecycle_lock_release_failed"
    assert "private unlock detail" not in str(captured.value)
    assert str(path) not in str(captured.value)


@pytest.mark.skipif(os.name == "nt", reason="uses the native POSIX advisory lock")
def test_guard_release_error_never_replaces_service_manager_body_error(tmp_path, monkeypatch):
    path = tmp_path / "run" / "lifecycle.lock"
    body_error = ServiceManagerError("original lifecycle failure", code="runtime_health_timeout")
    original = lifecycle_lock_module.fcntl.flock

    with pytest.raises(ServiceManagerError) as captured, LifecycleLock(path, _test_pid_exists):

        def fail_unlock(handle, operation):
            if operation == lifecycle_lock_module.fcntl.LOCK_UN:
                raise OSError("private unlock detail")
            return original(handle, operation)

        monkeypatch.setattr(lifecycle_lock_module.fcntl, "flock", fail_unlock)
        raise body_error

    assert captured.value is body_error


def test_windows_guard_unlock_failure_still_attempts_close(manager, monkeypatch):
    path = manager.run_root / "lifecycle.lock"
    lock = LifecycleLock(path, _test_pid_exists)
    lock._guard_handle = 91
    closed: list[int] = []

    class WindowsLocking:
        LK_UNLCK = 3

        @staticmethod
        def locking(_handle, _mode, _size):
            raise OSError("private Windows unlock detail")

    monkeypatch.setattr(lifecycle_lock_module, "msvcrt", WindowsLocking)
    monkeypatch.setattr(lifecycle_lock_module.os, "lseek", lambda *_args: 0)
    monkeypatch.setattr(lifecycle_lock_module.os, "close", closed.append)

    with pytest.raises(LifecycleLockError) as captured:
        lock._release_guard(platform_name="nt")

    assert captured.value.code == "lifecycle_lock_release_failed"
    assert "private Windows unlock detail" not in str(captured.value)
    assert closed == [91]


def test_guard_close_failure_is_coded_without_raw_error(manager, monkeypatch):
    path = manager.run_root / "lifecycle.lock"
    lock = LifecycleLock(path, _test_pid_exists)
    lock._guard_handle = 91
    monkeypatch.setattr(lifecycle_lock_module.fcntl, "flock", lambda *_args: None)
    monkeypatch.setattr(
        lifecycle_lock_module.os,
        "close",
        lambda _handle: (_ for _ in ()).throw(OSError("private close detail")),
    )

    with pytest.raises(LifecycleLockError) as captured:
        lock._release_guard(platform_name="posix")

    assert captured.value.code == "lifecycle_lock_release_failed"
    assert "private close detail" not in str(captured.value)


def test_lifecycle_lock_exit_never_removes_replacement_owner(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"
    lock = LifecycleLock(path, lambda _pid: True, pid=os.getpid())
    lock.__enter__()
    replacement = {
        "schema_version": 1,
        "pid": os.getpid() + 1,
        "token": "b" * 32,
        "started_at": time.time(),
    }
    (path / "owner.json").write_text(json.dumps(replacement), encoding="utf-8")
    (path / "owner.json").chmod(0o600)

    with pytest.raises(LifecycleLockError) as captured:
        lock.__exit__(None, None, None)

    assert captured.value.code == "lifecycle_lock_ownership_lost"
    assert path.exists()
    assert json.loads((path / "owner.json").read_text(encoding="utf-8")) == replacement
    contender = LifecycleLock(path, lambda _pid: True, pid=os.getpid() + 2)
    contender._prepare_parent()
    contender._acquire_guard()
    contender._release_guard()


def test_lifecycle_lock_stale_recovery_does_not_delete_raced_owner(tmp_path, monkeypatch):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)
    original_rename = lifecycle_lock_module.os.rename
    raced = False

    def race_once(source, target, *args, **kwargs):
        nonlocal raced
        if not raced and Path(source) == path:
            raced = True
            replacement = {
                "schema_version": 1,
                "pid": os.getpid(),
                "token": "c" * 32,
                "started_at": time.time(),
            }
            (path / "owner.json").write_text(json.dumps(replacement), encoding="utf-8")
            (path / "owner.json").chmod(0o600)
        return original_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(lifecycle_lock_module.os, "rename", race_once)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda pid: pid != 424242, pid=os.getpid() + 1),
    ):
        pytest.fail("a raced owner must not be removed")

    assert captured.value.code == "lifecycle_busy"
    remaining = list(path.parent.iterdir())
    assert remaining
    assert any(
        json.loads((item / "owner.json").read_text(encoding="utf-8"))["token"] == "c" * 32
        for item in remaining
        if item.is_dir()
    )


def _service_probe(
    role: str,
    *,
    state: str = "valid",
    process: str = "alive",
    ownership: str = "owned",
    port_state: str = "listening",
    protocol: str = "passed",
    ready: bool = True,
    pid: int | None = 101,
    issues: tuple[str, ...] = (),
) -> ServiceProbe:
    return ServiceProbe(
        role,
        3081 if role == "runtime" else 8088,
        state,
        process,
        ownership,
        port_state,
        protocol,
        ready,
        pid,
        issues,
    )


def _write_syntactically_valid_runtime_auth(manager: WebServiceManager) -> Path:
    path = manager._runtime_auth_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        json.dumps(
            {
                "authority": f"127.0.0.1:{manager.runtime_port}",
                "cookie": "dsh-auth-stale=value",
                "cwd": str((manager.data_root / "runtime/work").resolve()),
                "source_commit": service_manager_module.PINNED_COMMIT,
                "version": "0.1.3-alpha.2",
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def test_service_manager_error_exposes_safe_code_role_and_string():
    error = ServiceManagerError("safe message", code="runtime_process_exited", role="runtime")

    assert str(error) == "safe message"
    assert error.code == "runtime_process_exited"
    assert error.role == "runtime"


def test_service_manager_passes_product_private_root_to_lifecycle_lock(manager, monkeypatch):
    observed: dict[str, object] = {}

    class Lock:
        def __init__(self, path, pid_exists, pid=None, *, trusted_root=None):
            observed.update(path=path, pid_exists=pid_exists, pid=pid, trusted_root=trusted_root)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(service_manager_module, "LifecycleLock", Lock)

    with manager._lifecycle_lock():
        pass

    assert observed["path"] == manager.run_root / "lifecycle.lock"
    assert observed["trusted_root"] == manager.data_root.parent


def test_start_ready_owned_stack_is_idempotent_and_preserves_pids(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail("ready owned services must not be respawned"),
    )

    result = manager.start(open_browser=False)

    assert result["services"]["runtime"]["pid"] == 101
    assert result["services"]["web"]["pid"] == 202


def test_start_removes_dead_stale_state_then_spawns(manager, monkeypatch):
    runtime, web = manager._processes()
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    probes = {
        "runtime": _service_probe(
            "runtime",
            state="stale",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_stale",),
        ),
        "web": _service_probe("web", pid=202),
    }
    spawned: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        spawned.append(process.role)
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert spawned == [runtime.role]
    assert not manager._state_path(runtime.role).exists()
    assert probes[web.role].pid == 202


@pytest.mark.parametrize("state_kind", ["missing", "invalid"])
def test_start_clears_exact_stale_runtime_auth_after_safe_normalization(
    manager, monkeypatch, state_kind
):
    runtime, _web = manager._processes()
    manager._prepare_private_directories()
    auth = _write_syntactically_valid_runtime_auth(manager)
    if state_kind == "invalid":
        state_path = manager._state_path(runtime.role)
        state_path.write_text("{invalid", encoding="utf-8")
        state_path.chmod(0o600)
    probes = {
        "runtime": _service_probe(
            "runtime",
            state=state_kind,
            process="missing" if state_kind == "missing" else "inaccessible",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=() if state_kind == "missing" else ("runtime_state_invalid",),
        ),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn_and_wait(process):
        assert process.role == "runtime"
        assert not auth.exists()
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_spawn_and_wait", spawn_and_wait)

    manager.start(open_browser=False)

    assert not auth.exists()


def test_start_unsafe_runtime_never_clears_existing_auth(manager, monkeypatch):
    manager._prepare_private_directories()
    auth = _write_syntactically_valid_runtime_auth(manager)
    blocked = _service_probe(
        "runtime",
        ownership="foreign",
        protocol="not_run",
        ready=False,
        pid=None,
        issues=("runtime_pid_foreign", "runtime_port_in_use_unknown"),
    )
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: blocked if process.role == "runtime" else _service_probe("web", pid=202),
    )

    with pytest.raises(ServiceManagerError):
        manager.start(open_browser=False)

    assert auth.exists()


def test_start_quarantines_invalid_closed_state_and_replaces_prior_copy(manager, monkeypatch):
    runtime, _web = manager._processes()
    manager._prepare_private_directories()
    state_path = manager._state_path(runtime.role)
    state_path.write_text("{new-invalid", encoding="utf-8")
    state_path.chmod(0o600)
    quarantine = manager.run_root / "runtime.invalid.json"
    quarantine.write_text("old-invalid", encoding="utf-8")
    quarantine.chmod(0o600)
    probes = {
        "runtime": _service_probe(
            "runtime",
            state="invalid",
            process="inaccessible",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid",),
        ),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert not state_path.exists()
    assert quarantine.read_text(encoding="utf-8") == "{new-invalid"
    assert quarantine.stat().st_mode & 0o777 == 0o600
    assert not list(manager.run_root.glob("runtime.invalid-*.json"))


def test_quarantine_skips_directory_fsync_on_windows_model(manager, monkeypatch):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    source = manager._state_path(runtime.role)
    source.write_text("{invalid", encoding="utf-8")
    source.chmod(0o600)
    observed: list[str] = []
    monkeypatch.setattr(
        service_manager_module,
        "_fsync_directory",
        lambda _path, *, platform_name=None: observed.append(str(platform_name)),
    )

    manager._quarantine_invalid_state(runtime, platform_name="nt")

    assert observed == ["nt"]


def test_repeated_quarantine_retains_only_one_fixed_diagnostic(manager):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    source = manager._state_path(runtime.role)

    source.write_text("first-invalid", encoding="utf-8")
    source.chmod(0o600)
    manager._quarantine_invalid_state(runtime)
    source.write_text("second-invalid", encoding="utf-8")
    source.chmod(0o600)
    manager._quarantine_invalid_state(runtime)

    entries = [path.name for path in manager.run_root.iterdir()]
    assert entries == ["runtime.invalid.json"]
    assert (manager.run_root / "runtime.invalid.json").read_text(encoding="utf-8") == (
        "second-invalid"
    )


def test_quarantine_fsync_failure_leaves_no_uuid_staging_residue(manager, monkeypatch):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    source = manager._state_path(runtime.role)
    source.write_text("new-invalid", encoding="utf-8")
    source.chmod(0o600)
    monkeypatch.setattr(
        service_manager_module,
        "_fsync_directory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fsync failed")),
        raising=False,
    )

    with pytest.raises(ServiceManagerError):
        manager._quarantine_invalid_state(runtime)

    entries = [path.name for path in manager.run_root.iterdir()]
    assert entries == ["runtime.invalid.json"]


@pytest.mark.parametrize(
    "probe",
    [
        _service_probe(
            "runtime",
            state="invalid",
            process="alive",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid_live_pid",),
        ),
        _service_probe(
            "runtime",
            state="invalid",
            process="inaccessible",
            ownership="unknown",
            port_state="listening",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid_port_listening",),
        ),
        _service_probe(
            "runtime",
            process="alive",
            ownership="foreign",
            ready=False,
            pid=None,
            protocol="not_run",
            issues=("runtime_pid_foreign", "runtime_port_in_use_unknown"),
        ),
        _service_probe(
            "runtime",
            process="alive",
            ownership="foreign",
            ready=False,
            pid=None,
            protocol="not_run",
            issues=("runtime_port_owner_mismatch",),
        ),
    ],
    ids=["invalid-live", "invalid-listener", "foreign-pid", "listener-mismatch"],
)
def test_start_refuses_unsafe_probe_without_killing_or_spawning(manager, monkeypatch, probe):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: probe if process.role == "runtime" else _service_probe("web", pid=202),
    )
    monkeypatch.setattr(
        manager,
        "_terminate_pid",
        lambda *_args, **_kwargs: pytest.fail("unsafe probes must never be killed"),
    )
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail("unsafe probes must never be replaced"),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    assert captured.value.code in probe.issues
    assert captured.value.code in str(captured.value)
    assert captured.value.role == "runtime"


def test_start_rebuilds_owned_unhealthy_runtime_stack_in_dependency_order(manager, monkeypatch):
    probes = {
        "runtime": _service_probe(
            "runtime",
            protocol="failed",
            ready=False,
            pid=101,
            issues=("runtime_health_failed",),
        ),
        "web": _service_probe("web", pid=202),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: [])

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(
            process.role, pid=303 if process.role == "runtime" else 404
        )
        return probes[process.role].pid

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert events == ["stop:web", "stop:runtime", "spawn:runtime", "spawn:web"]


@pytest.mark.parametrize("activity", ["running", "unverified"])
def test_start_never_stops_owned_runtime_when_research_may_be_active(
    manager, monkeypatch, activity
):
    probes = {
        "runtime": _service_probe(
            "runtime",
            protocol="failed",
            ready=False,
            pid=101,
            issues=("runtime_health_failed",),
        ),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(
        manager,
        "_stop_owned_probe",
        lambda *_args: pytest.fail("start must preserve possibly active research"),
    )
    monkeypatch.setattr(
        manager,
        "_spawn_and_wait",
        lambda *_args: pytest.fail("start must not replace possibly active research"),
    )

    def activity_check(_probe):
        if activity == "running":
            return ["session-1"]
        raise ServiceManagerError(
            "active_research_unverified", code="active_research_unverified", role="runtime"
        )

    monkeypatch.setattr(manager, "_active_research_read_only", activity_check)

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    assert captured.value.code == (
        "active_research" if activity == "running" else "active_research_unverified"
    )


def test_start_rebuilds_only_owned_unhealthy_web(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe(
            "web",
            protocol="failed",
            ready=False,
            pid=202,
            issues=("web_runtime_api_failed",),
        ),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert events == ["stop:web", "spawn:web"]


def test_wait_for_ready_reports_confirmed_early_exit_without_sleep(manager, monkeypatch):
    runtime = manager._processes()[0]
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            state="stale",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_stale",),
        ),
    )
    monkeypatch.setattr(
        service_manager_module.time,
        "sleep",
        lambda _seconds: pytest.fail("confirmed exits must not sleep until timeout"),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=35)

    assert captured.value.code == "runtime_process_exited"
    assert captured.value.role == "runtime"


def test_wait_for_ready_allows_spawned_launcher_before_port_listens(manager, monkeypatch):
    runtime = manager._processes()[0]
    probes = iter(
        [
            _service_probe(
                "runtime",
                ownership="foreign",
                port_state="closed",
                protocol="not_run",
                ready=False,
                pid=None,
                issues=("runtime_pid_foreign",),
            ),
            _service_probe("runtime", pid=303),
        ]
    )
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda _process: service_manager_module._StateFact(
            "valid", 303, runtime.signature, (), 100.0
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("alive", "launcher", None, runtime.command, 100.0),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("closed", (), None),
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    assert manager._wait_for_ready(runtime, 303, timeout=1).ready is True


def test_wait_for_ready_rejects_unrelated_pid_during_startup(manager, monkeypatch):
    runtime = manager._processes()[0]
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            ownership="foreign",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    )
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda _process: service_manager_module._StateFact(
            "valid", 303, runtime.signature, (), 100.0
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("alive", "unrelated", None, ("python", "other.py"), 100.0),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("closed", (), None),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=1)

    assert captured.value.code == "runtime_process_exited"


@pytest.mark.parametrize(
    ("started_at", "listener"),
    [
        (80.0, ListenerFact("closed", (), None)),
        (100.0, ListenerFact("listening", (404,), None)),
    ],
    ids=["reused-pid", "foreign-listener"],
)
def test_wait_for_ready_rejects_unverified_spawned_identity(
    manager, monkeypatch, started_at, listener
):
    runtime = manager._processes()[0]
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            ownership="unknown",
            port_state=listener.state,
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    )
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda _process: service_manager_module._StateFact(
            "valid", 303, runtime.signature, (), 100.0
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("alive", "launcher", None, runtime.command, started_at),
    )
    monkeypatch.setattr(service_manager_module, "listener_pids", lambda _port: listener)

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=1)

    assert captured.value.code == "runtime_process_exited"


def test_wait_for_ready_times_out_with_last_stable_issue(manager, monkeypatch):
    runtime = manager._processes()[0]
    ticks = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr(service_manager_module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=303,
            issues=("runtime_port_closed",),
        ),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=0.1)

    assert captured.value.code == "runtime_health_timeout"
    assert captured.value.role == "runtime"
    assert "runtime_port_closed" in str(captured.value)


def test_wait_for_ready_bootstraps_runtime_auth_before_authoritative_ready(manager, monkeypatch):
    runtime = manager._processes()[0]
    probes = iter(
        [
            _service_probe(
                "runtime",
                protocol="failed",
                ready=False,
                pid=303,
                issues=("runtime_health_failed",),
            ),
            _service_probe("runtime", pid=303),
        ]
    )
    bootstrapped: list[bool] = []
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(manager, "_runtime_sessions", lambda: bootstrapped.append(True) or [])
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    result = manager._wait_for_ready(runtime, 303, timeout=1)

    assert result.ready is True
    assert bootstrapped == [True]


def test_start_rollback_targets_only_process_spawned_by_this_invocation(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe(
            "web",
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    }
    rolled_back: list[tuple[str, int]] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_spawn", lambda _process: 303)

    def wait_for_ready(process, pid, *, timeout):
        if process.role == "web":
            raise ServiceManagerError("web timeout", code="web_health_timeout", role="web")
        return _service_probe("runtime", pid=pid)

    monkeypatch.setattr(manager, "_wait_for_ready", wait_for_ready)
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, pid: rolled_back.append((process.role, pid)),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    assert captured.value.code == "web_health_timeout"
    assert rolled_back == [("web", 303)]


def test_spawn_and_wait_rolls_back_its_exact_spawn_on_wait_failure(manager, monkeypatch):
    runtime = manager._processes()[0]
    rolled_back: list[tuple[str, int]] = []
    monkeypatch.setattr(manager, "_spawn", lambda _process: 303)
    monkeypatch.setattr(
        manager,
        "_wait_for_ready",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ServiceManagerError(
                "runtime timeout",
                code="runtime_health_timeout",
                role="runtime",
            )
        ),
    )
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, pid: rolled_back.append((process.role, pid)),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._spawn_and_wait(runtime)

    assert captured.value.code == "runtime_health_timeout"
    assert rolled_back == [("runtime", 303)]


def test_stop_orders_web_before_runtime_and_returns_final_facts(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    stopped: list[str] = []
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def stop_owned(process, _probe):
        stopped.append(process.role)
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)

    result = manager.stop()

    assert stopped == ["web", "runtime"]
    assert result["services"]["runtime"]["running"] is False
    assert result["services"]["web"]["running"] is False


def test_stop_cleans_dead_stale_state_without_removing_runtime_auth(manager, monkeypatch):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    auth = manager._runtime_auth_path()
    auth.parent.mkdir(parents=True, exist_ok=True)
    auth.write_text("retained", encoding="utf-8")

    def probe(process):
        if process.role == "runtime":
            return _service_probe(
                "runtime",
                state="stale",
                process="missing",
                ownership="unknown",
                port_state="closed",
                protocol="not_run",
                ready=False,
                pid=None,
                issues=("runtime_state_stale",),
            )
        return _service_probe(
            "web",
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )

    monkeypatch.setattr(manager, "_probe_service", probe)

    manager.stop()

    assert not manager._state_path(runtime.role).exists()
    assert auth.read_text(encoding="utf-8") == "retained"


def test_runtime_rebuild_reports_coded_auth_cleanup_failure(manager):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    auth = manager._runtime_auth_path()
    auth.mkdir(parents=True)
    stale = _service_probe(
        "runtime",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="closed",
        protocol="not_run",
        ready=False,
        pid=None,
        issues=("runtime_state_stale",),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._normalize_absent_probe(runtime, stale, clear_runtime_auth=True)

    assert captured.value.code == "runtime_ownership_unverified"


def test_restart_holds_one_lock_without_calling_public_lifecycle_methods(manager, monkeypatch):
    entries = 0

    class Lock:
        def __enter__(self):
            nonlocal entries
            entries += 1

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(manager, "_lifecycle_lock", Lock)
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_service_probes", lambda: (_service_probe("runtime"), _service_probe("web"))
    )
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: [])
    monkeypatch.setattr(manager, "stop", lambda: pytest.fail("restart must not call public stop"))
    monkeypatch.setattr(
        manager, "start", lambda **_kwargs: pytest.fail("restart must not call public start")
    )
    monkeypatch.setattr(manager, "_stop_locked", lambda: {"services": {}})
    monkeypatch.setattr(manager, "_start_locked", lambda **_kwargs: {"ok": True})

    assert manager.restart(force=False, open_browser=False) == {"ok": True}
    assert entries == 1


def test_restart_active_research_guard_runs_before_stop(manager, monkeypatch):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_service_probes", lambda: (_service_probe("runtime"), _service_probe("web"))
    )
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: ["session-1"])
    monkeypatch.setattr(manager, "_stop_locked", lambda: pytest.fail("guard must run first"))

    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart(force=False, open_browser=False)


@pytest.mark.parametrize("method_name", ["restart", "restart_runtime"])
@pytest.mark.parametrize(
    ("case", "probe"),
    [
        (
            "port-closed",
            _service_probe(
                "runtime",
                port_state="closed",
                protocol="not_run",
                ready=False,
                pid=101,
                issues=("runtime_port_closed",),
            ),
        ),
        (
            "port-unknown",
            _service_probe(
                "runtime",
                port_state="unknown",
                protocol="not_run",
                ready=False,
                pid=101,
                issues=("runtime_listener_probe_failed",),
            ),
        ),
        (
            "listener-mismatch",
            _service_probe(
                "runtime",
                protocol="not_run",
                ready=False,
                pid=101,
                issues=("runtime_port_owner_mismatch",),
            ),
        ),
        (
            "listener-unverified",
            _service_probe(
                "runtime",
                protocol="not_run",
                ready=False,
                pid=101,
                issues=("runtime_listener_probe_failed",),
            ),
        ),
        (
            "auth-missing",
            _service_probe(
                "runtime",
                protocol="failed",
                ready=False,
                pid=101,
                issues=("runtime_health_failed",),
            ),
        ),
    ],
)
def test_nonforce_restart_never_bootstraps_auth_when_activity_is_unverified(
    manager, monkeypatch, method_name, case, probe
):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    if method_name == "restart":
        monkeypatch.setattr(
            manager,
            "_service_probes",
            lambda: (probe, _service_probe("web", pid=202)),
        )
        monkeypatch.setattr(
            manager,
            "_stop_locked",
            lambda: pytest.fail("an unverified restart must not stop services"),
        )
    else:
        monkeypatch.setattr(manager, "_probe_service", lambda _process: probe)
        monkeypatch.setattr(
            manager,
            "_stop_owned_probe",
            lambda *_args: pytest.fail("an unverified restart must not stop Runtime"),
        )
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        (
            (lambda: None)
            if case == "auth-missing"
            else lambda: pytest.fail("unsafe listener facts must not reach auth")
        ),
    )
    monkeypatch.setattr(
        manager,
        "_runtime_sessions",
        lambda: pytest.fail("restart guards must not bootstrap Runtime auth"),
    )
    monkeypatch.setattr(
        manager,
        "_runtime_launch_token",
        lambda: pytest.fail("restart guards must not read launch tokens"),
    )
    monkeypatch.setattr(
        manager,
        "_exchange_runtime_cookie",
        lambda _token: pytest.fail("restart guards must not exchange cookies"),
    )
    monkeypatch.setattr(
        manager,
        "_write_runtime_auth",
        lambda _cookie: pytest.fail("restart guards must not write auth"),
    )

    with pytest.raises(ServiceManagerError) as captured:
        if method_name == "restart":
            manager.restart(force=False, open_browser=False)
        else:
            manager.restart_runtime(force=False)

    assert captured.value.code == "active_research_unverified"
    assert "--force" in str(captured.value)


def test_read_only_restart_activity_check_uses_existing_authenticated_session_only(
    manager, monkeypatch
):
    runtime = _service_probe("runtime", pid=101)
    auth = {"cookie": "dsh-auth-test=value"}
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: auth)
    monkeypatch.setattr(
        manager,
        "_runtime_sessions_authenticated",
        lambda observed: (
            [
                {"sessionId": "idle", "running": False},
                {"sessionId": "running", "running": True},
            ]
            if observed is auth
            else pytest.fail("the exact existing auth record must be reused")
        ),
    )
    monkeypatch.setattr(
        manager,
        "_runtime_sessions",
        lambda: pytest.fail("the read-only guard must not use auth bootstrap"),
    )
    monkeypatch.setattr(
        manager,
        "_write_runtime_auth",
        lambda _cookie: pytest.fail("the read-only guard must not write auth"),
    )

    assert manager._active_research_read_only(runtime) == ["running"]


def test_read_only_restart_activity_check_maps_probe_failure_to_stable_refusal(
    manager, monkeypatch
):
    runtime = _service_probe("runtime", pid=101)
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )
    monkeypatch.setattr(
        manager,
        "_runtime_sessions_authenticated",
        lambda _auth: (_ for _ in ()).throw(OSError("private transport detail")),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research_read_only(runtime)

    assert captured.value.code == "active_research_unverified"
    assert "private transport detail" not in str(captured.value)
    assert "--force" in str(captured.value)


def test_restart_runtime_stops_and_rebuilds_only_owned_runtime(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: [])

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    result = manager.restart_runtime(force=False)

    assert events == ["stop:runtime", "spawn:runtime"]
    assert probes["web"].pid == 202
    assert result == {"running": True, "healthy": True, "pid": 303, "port": 3081}


def test_lifecycle_lock_contention_maps_to_coded_service_error(manager):
    path = manager.run_root / "lifecycle.lock"

    with (
        LifecycleLock(path, lambda _pid: True, pid=os.getpid()),
        pytest.raises(ServiceManagerError) as captured,
    ):
        manager.stop()

    assert captured.value.code == "lifecycle_busy"


def test_internal_probe_facts_stay_private_to_service_manager():
    assert not hasattr(service_diagnostics_module, "StateFact")
    assert not hasattr(service_diagnostics_module, "ProcessFact")
    assert service_manager_module._StateFact.__dataclass_params__.frozen is True
    assert service_manager_module._ProcessFact.__dataclass_params__.frozen is True
    assert service_manager_module._ProcessFact is not ProcessFact


def test_service_probe_public_is_safe_and_compatible():
    probe = ServiceProbe(
        role="runtime",
        port=3081,
        state="valid",
        process="alive",
        ownership="foreign",
        port_state="listening",
        protocol="not_run",
        ready=False,
        pid=4321,
        issues=("runtime_pid_foreign",),
    )

    assert probe.public(log="/safe/runtime.log") == {
        "state": "valid",
        "process": "alive",
        "ownership": "foreign",
        "port_state": "listening",
        "protocol": "not_run",
        "ready": False,
        "running": False,
        "healthy": False,
        "pid": None,
        "port": 3081,
        "issues": ["runtime_pid_foreign"],
        "log": "/safe/runtime.log",
    }


@pytest.fixture
def manager(tmp_path: Path) -> WebServiceManager:
    source = tmp_path / "dsh"
    source.mkdir()
    python = tmp_path / "python"
    node = tmp_path / "node"
    python.touch()
    node.touch()
    (tmp_path / "data").mkdir(mode=0o700)
    return WebServiceManager(
        project_root=tmp_path,
        data_root=tmp_path / "data" / "research-web",
        runtime_source=source,
        python=str(python),
        node=str(node),
    )


def _valid_state(manager: WebServiceManager, role: str, pid: int = 4321) -> tuple[object, Path]:
    manager._prepare_private_directories()
    process = next(item for item in manager._processes() if item.role == role)
    manager._write_state(process, pid)
    return process, manager._state_path(role)


def test_status_exposes_full_fact_chain(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: ServiceProbe(
            role=process.role,
            port=process.port,
            state="valid",
            process="alive",
            ownership="owned",
            port_state="listening",
            protocol="passed" if process.role == "runtime" else "failed",
            ready=process.role == "runtime",
            pid=101 if process.role == "runtime" else 202,
            issues=() if process.role == "runtime" else ("web_runtime_api_failed",),
        ),
    )

    status = manager.status()

    assert status["product_ready"] is False
    assert status["warnings"] == []
    assert status["services"]["runtime"]["ready"] is True
    assert status["services"]["web"]["running"] is True
    assert status["services"]["web"]["healthy"] is False
    assert status["services"]["web"]["issues"] == ["web_runtime_api_failed"]
    assert status["services"]["runtime"]["log"].endswith("runtime.log")


def test_doctor_keeps_other_service_when_one_state_is_invalid(manager, monkeypatch):
    monkeypatch.setattr(service_manager_module.os, "environ", {})
    monkeypatch.setattr(
        manager,
        "_model_diagnosis",
        lambda: pytest.fail("model diagnosis must not run before product readiness"),
    )
    probes = iter(
        [
            ServiceProbe(
                "runtime",
                3081,
                "invalid",
                "inaccessible",
                "unknown",
                "closed",
                "not_run",
                False,
                None,
                ("runtime_state_invalid",),
            ),
            ServiceProbe(
                "web",
                8088,
                "valid",
                "alive",
                "owned",
                "listening",
                "passed",
                True,
                222,
                (),
            ),
        ]
    )
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(
        manager,
        "_installation_diagnosis",
        lambda: {
            "schema_version": 1,
            "ok": True,
            "issues": ["shared_issue", "runtime_state_invalid"],
        },
    )

    report = manager.doctor()

    assert report["schema_version"] == 2
    assert report["ok"] is True
    assert report["installation_ok"] is True
    assert report["product_ready"] is False
    assert report["model_ready"] is False
    assert report["issues"] == ["shared_issue", "runtime_state_invalid"]
    assert report["warnings"] == []
    assert report["services"]["runtime"]["issues"] == ["runtime_state_invalid"]
    assert report["services"]["web"]["ready"] is True
    assert "log" not in report["services"]["web"]


def test_probe_valid_owned_listener_passes_protocol_without_mutation(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    before = state_path.read_bytes()
    state = json.loads(before)
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(manager, "_protocol_health", lambda _process: True)
    monkeypatch.setattr(
        manager,
        "_terminate_pid",
        lambda *_args, **_kwargs: pytest.fail("read-only probe must never terminate"),
    )

    probe = manager._probe_service(process)

    assert probe == ServiceProbe(
        "runtime",
        3081,
        "valid",
        "alive",
        "owned",
        "listening",
        "passed",
        True,
        4321,
        (),
    )
    assert state_path.read_bytes() == before


def test_probe_dead_pid_is_stale_and_does_not_unlink_state(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("missing", None, None),
    )
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.state == "stale"
    assert probe.process == "missing"
    assert probe.ownership == "unknown"
    assert probe.protocol == "not_run"
    assert probe.ready is False
    assert "runtime_state_stale" in probe.issues
    assert state_path.exists()


def test_status_does_not_remove_stale_state(manager, monkeypatch):
    _process, state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("missing", None, None),
    )
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    status = manager.status()

    assert status["services"]["runtime"]["state"] == "stale"
    assert status["services"]["web"]["state"] == "missing"
    assert state_path.exists()


def test_runtime_probe_never_regenerates_missing_auth(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(
        manager,
        "_write_runtime_auth",
        lambda _cookie: pytest.fail("read-only probe must not write auth"),
    )

    probe = manager._probe_service(process)

    assert probe.protocol == "failed"
    assert probe.ready is False
    assert probe.issues == ("runtime_health_failed",)


def _authoritative_process_fact(process, state: dict[str, object]) -> ProcessFact:
    return ProcessFact(
        "alive",
        " ".join(process.signature),
        None,
        tuple(process.signature),
        float(state["started_at"]),
    )


def test_probe_rejects_same_signature_pid_reuse_by_start_identity(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact(
            "alive",
            " ".join(process.signature),
            None,
            tuple(process.signature),
            float(state["started_at"]) - 60,
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: pytest.fail("reused PID must never reach protocol"),
    )

    probe = manager._probe_service(process)

    assert probe.process == "alive"
    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert probe.issues == ("runtime_pid_reused", "runtime_port_in_use_unknown")


@pytest.mark.parametrize("colliding_port", ["13081", "prefix-3081-suffix"])
def test_probe_rejects_numeric_and_embedded_signature_token_collisions(
    manager, monkeypatch, colliding_port
):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    argv = tuple(
        colliding_port if item == str(process.port) else item for item in process.signature
    )
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("alive", " ".join(argv), None, argv, float(state["started_at"])),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )

    probe = manager._probe_service(process)

    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert "runtime_pid_foreign" in probe.issues


def test_probe_owns_exact_spaced_signature_tokens(manager, tmp_path, monkeypatch):
    project_root = tmp_path / "project with spaces"
    project_root.mkdir()
    data_root = tmp_path / "data with spaces" / "research-web"
    spaced = WebServiceManager(
        project_root=project_root,
        data_root=data_root,
        runtime_source=manager.runtime_source,
        python=manager.python,
        node=manager.node,
    )
    process, state_path = _valid_state(spaced, "web")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    argv = ("uvicorn", *process.signature, "--flag-between-signatures")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact(
            "alive", "display text is not authoritative", None, argv, float(state["started_at"])
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(spaced, "_protocol_health", lambda _process: True)

    probe = spaced._probe_service(process)

    assert str(project_root) in process.signature
    assert " " in str(project_root)
    assert probe.ownership == "owned"
    assert probe.ready is True


def test_probe_requires_owned_pid_to_be_the_exact_listener(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (9876,), None),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: pytest.fail("foreign listener must never reach protocol"),
    )

    probe = manager._probe_service(process)

    assert probe.process == "alive"
    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert probe.issues == ("runtime_port_owner_mismatch",)


def test_probe_listener_failure_preserves_process_facts_as_unknown(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("unknown", (), "listener_probe_failed"),
    )

    probe = manager._probe_service(process)

    assert probe.state == "valid"
    assert probe.process == "alive"
    assert probe.ownership == "unknown"
    assert probe.port_state == "unknown"
    assert probe.protocol == "not_run"
    assert probe.issues == ("runtime_listener_probe_failed",)


@pytest.mark.parametrize("stage", ["state", "process", "listener", "protocol"])
def test_probe_stage_errors_preserve_already_observed_facts(manager, monkeypatch, stage):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if stage == "state":
        monkeypatch.setattr(
            manager, "_probe_state", lambda _process: (_ for _ in ()).throw(OSError())
        )
    else:
        monkeypatch.setattr(
            service_manager_module,
            "probe_process",
            lambda _pid: (
                (_ for _ in ()).throw(OSError())
                if stage == "process"
                else _authoritative_process_fact(process, state)
            ),
        )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: (
            (_ for _ in ()).throw(OSError())
            if stage == "listener"
            else ListenerFact("listening", (int(state["pid"]),), None)
        ),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: ((_ for _ in ()).throw(OSError()) if stage == "protocol" else True),
    )

    probe = manager._probe_service(process)

    if stage == "state":
        assert probe.state == "invalid"
        assert probe.process == "inaccessible"
        assert probe.port_state == "listening"
    elif stage == "process":
        assert probe.state == "valid"
        assert probe.process == "inaccessible"
        assert probe.port_state == "listening"
    elif stage == "listener":
        assert probe.state == "valid"
        assert probe.process == "alive"
        assert probe.ownership == "unknown"
        assert probe.port_state == "unknown"
    else:
        assert probe.state == "valid"
        assert probe.process == "alive"
        assert probe.ownership == "owned"
        assert probe.port_state == "listening"
        assert probe.protocol == "failed"
    assert probe.ready is False
    assert any(issue.startswith("runtime_") for issue in probe.issues)


def test_status_keeps_other_service_when_one_probe_stage_errors(manager, monkeypatch):
    original = manager._probe_state

    def state_probe(process):
        if process.role == "runtime":
            raise OSError("private detail")
        return original(process)

    monkeypatch.setattr(manager, "_probe_state", state_probe)
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    status = manager.status()

    assert status["services"]["runtime"]["state"] == "invalid"
    assert status["services"]["runtime"]["issues"] == ["runtime_state_probe_failed"]
    assert status["services"]["web"]["state"] == "missing"
    assert status["services"]["web"]["issues"] == []
    assert "private detail" not in json.dumps(status)


@pytest.mark.parametrize(
    ("process_fact", "expected_process", "ownership", "issue"),
    [
        (
            ProcessFact(
                "alive",
                "python unrelated.py",
                None,
                ("python", "unrelated.py"),
                1.0,
            ),
            "alive",
            "foreign",
            "runtime_pid_foreign",
        ),
        (
            ProcessFact("alive", None, None),
            "inaccessible",
            "unknown",
            "runtime_process_inaccessible",
        ),
        (
            ProcessFact("inaccessible", None, "process_access_denied"),
            "inaccessible",
            "unknown",
            "runtime_process_inaccessible",
        ),
    ],
)
def test_probe_distinguishes_foreign_and_unknown_processes(
    manager, monkeypatch, process_fact, expected_process, ownership, issue
):
    process, _state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(service_manager_module, "probe_process", lambda _pid: process_fact)
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.process == expected_process
    assert probe.ownership == ownership
    assert issue in probe.issues
    assert probe.pid is None


def test_probe_listener_without_owned_service_is_not_ready(manager, monkeypatch):
    process = manager._processes()[0]
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (9999,), None),
    )

    probe = manager._probe_service(process)

    assert probe.state == "missing"
    assert probe.port_state == "listening"
    assert probe.protocol == "not_run"
    assert probe.ready is False
    assert probe.issues == ("runtime_port_in_use_unknown",)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: "{",
        lambda state: json.dumps({**state, "extra": True}),
        lambda state: json.dumps({**state, "pid": "4321"}),
        lambda state: json.dumps({**state, "fingerprint": "0" * 64}),
        lambda state: json.dumps({**state, "signature": ["wrong"]}),
        lambda state: json.dumps({**state, "project_root": "/wrong"}),
        lambda state: json.dumps({**state, "data_root": "/wrong"}),
        lambda state: json.dumps({**state, "role": "web"}),
        lambda state: json.dumps({**state, "port": 9999}),
        lambda state: json.dumps({**state, "started_at": 10**500}),
        lambda state: "[" * 1100 + "0" + "]" * 1100,
        lambda state: json.dumps({"huge": "x" * (65 * 1024)}),
    ],
    ids=[
        "malformed-json",
        "wrong-keys",
        "wrong-types",
        "fingerprint",
        "signature",
        "project-root",
        "data-root",
        "role",
        "port",
        "huge-started-at",
        "deep-json",
        "oversize",
    ],
)
def test_probe_rejects_adversarial_state_without_throwing_or_mutating(manager, monkeypatch, mutate):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state_path.write_text(mutate(state), encoding="utf-8")
    before = state_path.read_bytes()
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.state == "invalid"
    assert probe.process in {"inaccessible", "missing"}
    assert probe.ownership == "unknown"
    assert probe.issues == ("runtime_state_invalid",)
    assert state_path.read_bytes() == before


def test_import_does_not_load_runtime_feature_graph():
    project_root = Path(__file__).resolve().parents[2]
    script = """
import sys

import app.research_web.service_manager

assert "app.research_web.launch_runtime" not in sys.modules
assert "app.research_web.capabilities.packages" not in sys.modules
assert "app.research_web.mcp_runtime.routes" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_process_contract_uses_brand_neutral_runtime_and_fixed_ports(manager):
    runtime, web = manager._processes()
    assert runtime.port == 3081
    assert web.port == 8088
    assert "app.research_web.launch_runtime" in runtime.command
    assert "app.research_web.main:app" in web.command
    assert runtime.signature == (
        str(manager.runtime_source / "apps/cli/lib/bin.js"),
        str(manager.data_root / "runtime/overlay.yml"),
        "3081",
    )
    assert not any(part.startswith("af" + "_") for item in (runtime, web) for part in item.command)


def test_process_contract_supports_isolated_staging_ports(manager):
    staged = WebServiceManager(
        project_root=manager.project_root,
        data_root=manager.data_root,
        runtime_source=manager.runtime_source,
        python=manager.python,
        node=manager.node,
        web_port=18088,
        runtime_port=13081,
    )

    runtime, web = staged._processes()

    assert runtime.port == 13081
    assert web.port == 18088
    assert runtime.command[runtime.command.index("--port") + 1] == "13081"
    assert runtime.command[runtime.command.index("--datahub-url") + 1] == ("http://127.0.0.1:18088")
    assert web.command[-1] == "18088"
    assert staged.web_url == "http://127.0.0.1:18088/#/fingpt"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS /tmp is a system alias")
def test_runtime_signature_canonicalizes_system_alias_above_data_root():
    with tempfile.TemporaryDirectory(prefix="rwb-signature-", dir="/var/tmp") as directory:
        manager = WebServiceManager(data_root=Path(directory) / "research-web")
        runtime, _web = manager._processes()

        assert runtime.signature[1] == str(
            (manager.data_root / "runtime" / "overlay.yml").resolve()
        )


def test_spawn_exports_the_exact_private_web_origin_for_mcp_callbacks(manager, monkeypatch):
    captured = {}
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:18080")

    class Process:
        pid = 4321

    def popen(_command, **options):
        captured.update(options)
        return Process()

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", popen)
    monkeypatch.setattr(manager, "_write_state", lambda *_args: None)

    manager._prepare_private_directories()
    manager._spawn(manager._processes()[1])

    assert captured["env"]["RESEARCH_WEB_INTERNAL_URL"] == "http://127.0.0.1:8088"
    assert "ALL_PROXY" not in captured["env"]
    assert captured["env"]["HTTPS_PROXY"] == "http://127.0.0.1:18080"


def test_spawn_state_write_failure_terminates_and_reaps_exact_posix_child(manager, monkeypatch):
    manager._prepare_private_directories()
    signals: list[tuple[int, signal.Signals]] = []

    class Child:
        pid = 4321
        wait_calls = 0

        def wait(self, *, timeout):
            self.wait_calls += 1
            assert timeout == 2
            return 0

    child = Child()
    monkeypatch.setattr(service_manager_module.subprocess, "Popen", lambda *_a, **_kw: child)
    monkeypatch.setattr(
        manager,
        "_write_state",
        lambda *_args: (_ for _ in ()).throw(ServiceManagerError("state write failed")),
    )
    monkeypatch.setattr(
        service_manager_module.os,
        "killpg",
        lambda pid, sent: signals.append((pid, sent)),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._spawn(manager._processes()[1])

    assert captured.value.code == "web_state_write_failed"
    assert signals == [(4321, signal.SIGTERM)]
    assert child.wait_calls == 1


def test_failed_spawn_cleanup_forces_posix_group_after_grace_timeout(manager, monkeypatch):
    signals: list[tuple[int, signal.Signals]] = []

    class Child:
        pid = 4321
        wait_calls = 0

        def wait(self, *, timeout):
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("child", timeout)
            return 0

    child = Child()
    monkeypatch.setattr(
        service_manager_module.os,
        "killpg",
        lambda pid, sent: signals.append((pid, sent)),
    )

    manager._terminate_failed_spawn(child, platform_name="posix")

    assert signals == [(4321, signal.SIGTERM), (4321, signal.SIGKILL)]
    assert child.wait_calls == 2


def test_failed_spawn_cleanup_uses_exact_windows_child_handle(manager):
    events: list[str] = []

    class Child:
        pid = 4321
        wait_calls = 0

        def terminate(self):
            events.append("terminate")

        def kill(self):
            events.append("kill")

        def wait(self, *, timeout):
            self.wait_calls += 1
            events.append(f"wait:{timeout}")
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("child", timeout)
            return 0

    manager._terminate_failed_spawn(Child(), platform_name="nt")

    assert events == ["terminate", "wait:2", "kill", "wait:2"]


def test_default_runtime_source_is_project_private(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEARCH_DSH_SOURCE", raising=False)
    data_root = tmp_path / ".research-workbench" / "research-web"
    resolved = WebServiceManager(project_root=tmp_path, data_root=data_root)
    assert (
        resolved.runtime_source
        == (
            tmp_path
            / ".research-workbench"
            / "runtime"
            / "dsh"
            / service_manager_module.PINNED_COMMIT
        ).resolve()
    )


def test_configured_node_binary_precedes_path_lookup(tmp_path, monkeypatch):
    configured = tmp_path / "node-24"
    configured.touch()
    monkeypatch.setenv("RESEARCH_NODE_BINARY", str(configured))
    monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: "/node-25")

    resolved = WebServiceManager(project_root=tmp_path, data_root=tmp_path / "data")

    assert resolved.node == str(configured)


def test_windows_private_directory_does_not_apply_posix_group_mode_bits(tmp_path):
    private_directory = tmp_path / "private"
    private_directory.mkdir(mode=0o755)

    assert not _is_unsafe_private_directory(
        private_directory,
        private_directory.lstat(),
        platform_name="nt",
    )


def test_posix_private_directory_rejects_group_mode_bits(tmp_path):
    private_directory = tmp_path / "private"
    private_directory.mkdir(mode=0o755)

    assert _is_unsafe_private_directory(
        private_directory,
        private_directory.lstat(),
        platform_name="posix",
    )


def test_private_state_is_atomic_and_fingerprint_checked(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(manager, "_command_line", lambda pid: " ".join(process.signature))
    assert manager._owned_state(process)["pid"] == 12345
    state_path = manager._state_path(process.role)
    state = json.loads(state_path.read_text())
    state["command"].append("--tampered")
    state_path.write_text(json.dumps(state))
    with pytest.raises(ServiceManagerError, match="无法安全确认"):
        manager._owned_state(process)


def test_stale_pid_is_removed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    assert manager._owned_state(process) is None
    assert not manager._state_path(process.role).exists()


def test_dead_state_from_previous_checkout_is_removed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    state_path = manager._state_path(process.role)
    state = json.loads(state_path.read_text())
    state["project_root"] = "/previous/checkout"
    state_path.write_text(json.dumps(state))
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)

    assert manager._owned_state(process) is None
    assert not state_path.exists()


def test_pid_reuse_or_foreign_command_fails_closed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(manager, "_command_line", lambda pid: "python unrelated.py")
    with pytest.raises(ServiceManagerError, match="拒绝操作"):
        manager._owned_state(process)


def test_windows_command_line_probe_uses_cim_without_a_shell(manager, monkeypatch):
    captured = {}

    class Result:
        returncode = 0
        stdout = "python.exe -m app.research_web.main:app"

    def run(command, **options):
        captured.update(command=command, options=options)
        return Result()

    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    command_line = manager._command_line(4321, platform_name="nt")

    assert command_line == Result.stdout
    assert captured["command"][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert "4321" in captured["command"][4]
    assert captured["options"]["shell"] is False


def test_windows_process_tree_termination_uses_taskkill(manager, monkeypatch):
    captured = []

    class Result:
        returncode = 0

    def run(command, **options):
        captured.append((command, options))
        return Result()

    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    manager._terminate_pid(4321, force=False, platform_name="nt")
    manager._terminate_pid(4321, force=True, platform_name="nt")

    assert captured[0][0] == ["taskkill.exe", "/PID", "4321", "/T"]
    assert captured[1][0] == ["taskkill.exe", "/PID", "4321", "/T", "/F"]
    assert all(options["shell"] is False for _command, options in captured)


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (1, False)])
def test_windows_pid_probe_uses_powershell_without_os_kill(
    manager, monkeypatch, returncode, expected
):
    captured = {}

    class Result:
        def __init__(self, code):
            self.returncode = code

    def run(command, **options):
        captured.update(command=command, options=options)
        return Result(returncode)

    monkeypatch.setattr(
        service_manager_module.os,
        "kill",
        lambda *_args: pytest.fail("Windows PID probes must not call os.kill"),
    )
    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    assert manager._pid_exists(4321, platform_name="nt") is expected
    assert captured["command"][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert "4321" in captured["command"][4]
    assert captured["options"]["shell"] is False


def test_posix_zombie_is_not_treated_as_a_live_owned_process(manager, monkeypatch):
    class Result:
        returncode = 0
        stdout = "Z+"

    monkeypatch.setattr(service_manager_module.os, "kill", lambda _pid, _signal: None)
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "run",
        lambda *_args, **_kwargs: Result(),
    )

    assert manager._pid_exists(4321, platform_name="posix") is False


def test_start_is_idempotent_and_waits_for_both_services(manager, monkeypatch):
    manager._prepare_private_directories()
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    spawned = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        spawned.append(process.role)
        pid = 100 + len(spawned)
        probes[process.role] = _service_probe(process.role, pid=pid)
        return pid

    monkeypatch.setattr(manager, "_spawn", spawn)
    manager.start(open_browser=False)
    manager.start(open_browser=False)
    assert spawned == ["runtime", "web"]


def test_start_fails_fast_when_web_installation_is_not_ready(manager, monkeypatch):
    lock = manager.project_root / "requirements" / "web.lock"
    lock.parent.mkdir()
    lock.write_text("locked-runtime", encoding="utf-8")
    lock_sha = service_manager_module.hashlib.sha256(lock.read_bytes()).hexdigest()
    monkeypatch.setattr(
        manager,
        "_read_install_manifest",
        lambda: {
            "schema_version": 1,
            "status": "installed",
            "web_lock_sha256": lock_sha,
            "cjpy_version": service_manager_module.CJPY_VERSION,
            "cjpy_sha256": service_manager_module.CJPY_SHA256,
            "dsh_commit": service_manager_module.PINNED_COMMIT,
            "dsh_closure_sha256": "closure-ok",
        },
    )
    monkeypatch.setattr(
        manager,
        "_installed_package_versions",
        lambda: {"cjpy": None, "requests": "2.33.0", "urllib3": "2.5.0"},
    )
    monkeypatch.setattr(
        manager,
        "_dsh_build_status",
        lambda: {
            "commit": service_manager_module.PINNED_COMMIT,
            "closure_sha256": "closure-ok",
            "closure_files": 11084,
            "ready": True,
        },
    )
    monkeypatch.setattr(manager, "_executable_version", lambda _path: "safe-version")
    monkeypatch.setattr(
        manager,
        "_runtime_healthy",
        lambda: pytest.fail("installation preflight must not contact Runtime"),
    )
    monkeypatch.setattr(
        manager,
        "_web_healthy",
        lambda: pytest.fail("installation preflight must not contact Web"),
    )
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail(
            "start must not spawn services before installation preflight passes"
        ),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    message = str(captured.value)
    assert "environment_not_owned" in message
    assert "cjpy_not_ready" in message
    assert "setup-web" in message


def test_start_rolls_back_only_new_processes(manager, monkeypatch):
    manager._prepare_private_directories()
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    stopped: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_spawn", lambda _process: 123)

    def wait_for_ready(process, pid, *, timeout):
        if process.role == "web":
            raise ServiceManagerError("Web timeout", code="web_health_timeout", role="web")
        return _service_probe(process.role, pid=pid)

    monkeypatch.setattr(manager, "_wait_for_ready", wait_for_ready)
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, _pid: stopped.append(process.role),
    )
    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)
    assert captured.value.code == "web_health_timeout"
    assert stopped == ["web", "runtime"]


def test_restart_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (_service_probe("runtime", pid=123), _service_probe("web", pid=456)),
    )
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: ["session-1"])
    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart(force=False, open_browser=False)


def test_restart_runtime_keeps_web_online_and_waits_for_owned_runtime(manager, monkeypatch):
    manager._prepare_private_directories()
    runtime, web = manager._processes()
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    stopped: list[str] = []
    spawned: list[str] = []

    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: [])

    def stop_one(process, _probe):
        stopped.append(process.role)
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        spawned.append(process.role)
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_one)
    monkeypatch.setattr(manager, "_spawn", spawn)

    result = manager.restart_runtime(force=False)

    assert stopped == [runtime.role]
    assert spawned == [runtime.role]
    assert probes[web.role].pid == 202
    assert result == {"running": True, "healthy": True, "pid": 303, "port": 3081}


def test_restart_runtime_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_probe_service", lambda process: _service_probe(process.role, pid=123)
    )
    monkeypatch.setattr(manager, "_active_research_read_only", lambda _probe: ["session-1"])

    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart_runtime(force=False)


def test_stop_never_targets_unowned_process(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    )
    kill_calls = []
    monkeypatch.setattr("os.killpg", lambda *args: kill_calls.append(args))
    manager.stop()
    assert kill_calls == []


def test_stop_waits_for_dead_pid_listener_to_close(manager, monkeypatch):
    web = manager._processes()[1]
    initial = _service_probe("web", pid=202)
    transition = _service_probe(
        "web",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="listening",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    absent = _service_probe(
        "web",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="closed",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    probes = iter([initial, transition, absent])
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(manager, "_terminate_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_remove_exact_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (202,), None),
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    assert manager._stop_owned_probe(web, initial) is True


def test_stop_waits_for_verified_pid_when_listener_probe_is_temporarily_unknown(
    manager, monkeypatch
):
    web = manager._processes()[1]
    initial = _service_probe("web", pid=202)
    pending = _service_probe(
        "web",
        ownership="unknown",
        port_state="unknown",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    absent = _service_probe(
        "web",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="closed",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    probes = iter([initial, pending, absent])
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(manager, "_spawned_process_pending", lambda _process, pid: pid == 202)
    monkeypatch.setattr(manager, "_terminate_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_remove_exact_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    assert manager._stop_owned_probe(web, initial) is True


def test_stop_waits_for_unreadable_signalled_pid_without_force_kill(manager, monkeypatch):
    web = manager._processes()[1]
    initial = _service_probe("web", pid=202)
    pending = _service_probe(
        "web",
        state="valid",
        process="inaccessible",
        ownership="unknown",
        port_state="unknown",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    absent = _service_probe(
        "web",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="closed",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    probes = iter([initial, pending, absent])
    terminated = []
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda _process: service_manager_module._StateFact("valid", 202, web.signature, (), 100.0),
    )
    monkeypatch.setattr(
        manager, "_terminate_pid", lambda pid, *, force: terminated.append((pid, force))
    )
    monkeypatch.setattr(manager, "_remove_exact_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("unknown", (), "listener_probe_failed"),
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    assert manager._stop_owned_probe(web, initial) is True
    assert terminated == [(202, False)]


def test_stop_transition_rejects_foreign_listener(manager, monkeypatch):
    web = manager._processes()[1]
    stale = _service_probe(
        "web",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="listening",
        protocol="not_run",
        ready=False,
        pid=None,
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (404,), None),
    )

    assert manager._stop_transition_pending(web, 202, stale) is False


def test_status_formatter_is_concise():
    value = {
        "url": "http://127.0.0.1:8088/#/fingpt",
        "services": {
            "runtime": {
                "state": "valid",
                "process": "alive",
                "ownership": "owned",
                "port_state": "listening",
                "protocol": "passed",
                "ready": True,
                "running": True,
                "healthy": True,
                "pid": 10,
                "port": 3081,
                "issues": [],
            },
            "web": {
                "state": "missing",
                "process": "missing",
                "ownership": "unknown",
                "port_state": "closed",
                "protocol": "not_run",
                "ready": False,
                "running": False,
                "healthy": False,
                "pid": None,
                "port": 8088,
                "issues": ["web_state_missing"],
            },
        },
    }
    rendered = format_status(value)
    assert "runtime: healthy" in rendered
    assert "web: stopped" in rendered
    assert "state=valid" in rendered
    assert "ownership=owned" in rendered
    assert "protocol=passed" in rendered
    assert "web_state_missing" in rendered
    assert "8088/#/fingpt" in rendered


def test_doctor_output_is_safe_and_reports_the_installation_contract(manager, monkeypatch):
    monkeypatch.setattr(service_manager_module.os, "environ", {})

    def unexpected_http_request(*_args, **_kwargs):
        raise AssertionError("installation contract must not contact port 8088")

    monkeypatch.setattr(manager, "_json_request", unexpected_http_request)
    monkeypatch.setattr(manager, "_model_diagnosis", lambda: (False, ()))
    environment = manager.project_root / ".venv"
    environment.mkdir()
    (environment / ".rwb-web-environment.json").write_text(
        json.dumps({"schema_version": 1, "owner": "research-workbench-web-installer"}),
        encoding="utf-8",
    )
    lock = manager.project_root / "requirements" / "web.lock"
    lock.parent.mkdir()
    lock.write_text("locked-runtime", encoding="utf-8")
    lock_sha = service_manager_module.hashlib.sha256(lock.read_bytes()).hexdigest()
    install_root = manager.data_root.parent / "install"
    install_root.mkdir(parents=True)
    (install_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "installed",
                "web_lock_sha256": lock_sha,
                "cjpy_version": "0.5.2",
                "cjpy_sha256": "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94",
                "dsh_commit": service_manager_module.PINNED_COMMIT,
                "dsh_closure_sha256": "closure-ok",
                "CJ_KEY": "must-never-escape",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        manager,
        "_executable_version",
        lambda path: "v24.19.0" if path == manager.node else "Python 3.12.9",
    )
    monkeypatch.setattr(
        manager,
        "_installed_package_versions",
        lambda: {"cjpy": "0.5.2", "requests": "2.33.0", "urllib3": "2.5.0"},
    )
    monkeypatch.setattr(
        manager,
        "_dsh_build_status",
        lambda: {
            "commit": service_manager_module.PINNED_COMMIT,
            "closure_sha256": "closure-ok",
            "closure_files": 11084,
            "ready": True,
        },
    )
    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (
            ServiceProbe(
                "runtime", 3081, "valid", "alive", "owned", "listening", "passed", True, 111, ()
            ),
            ServiceProbe(
                "web", 8088, "valid", "alive", "owned", "listening", "passed", True, 222, ()
            ),
        ),
    )
    runtime_lock = manager.data_root / "runtime" / "build-lock.json"
    # The installer protects data; the legacy runtime parent may remain 0755.
    manager.data_root.mkdir(parents=True, mode=0o700)
    runtime_lock.parent.mkdir(parents=True)
    runtime_lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    runtime_lock.chmod(0o600)

    report = manager.doctor()
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["ok"] is True
    assert report["python"]["lock_matches_manifest"] is True
    assert report["cjpy"]["version"] == "0.5.2"
    assert report["schema_version"] == 2
    assert report["installation_ok"] is True
    assert report["product_ready"] is True
    assert report["model_ready"] is False
    assert report["services"]["web"]["port"] == 8088
    assert report["services"]["web"]["running"] is True
    assert report["services"]["web"]["healthy"] is True
    assert "log" not in report["services"]["web"]
    assert str(manager.project_root) not in serialized
    assert "must-never-escape" not in serialized
    rendered = format_doctor_status(report)
    assert "Installation: ready" in rendered
    assert "Product: ready" in rendered
    assert "Model: not ready" in rendered
    assert "CJPY: 0.5.2" in rendered
    assert "DSH: ready" in rendered

    runtime_lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "stale-closure",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    stale = manager.doctor()
    assert stale["ok"] is False
    assert "dsh_runtime_lock_mismatch" in stale["issues"]


def test_dsh_build_status_uses_the_private_install_attestation(manager, monkeypatch):
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "check_output",
        lambda *_args, **_kwargs: service_manager_module.PINNED_COMMIT,
    )
    monkeypatch.setattr(
        service_manager_module,
        "calculate_build_closure",
        lambda _source: ("local-closure", 11084),
    )
    monkeypatch.setattr(
        manager,
        "_read_install_manifest",
        lambda: {
            "schema_version": 1,
            "dsh_commit": service_manager_module.PINNED_COMMIT,
            "dsh_closure_sha256": "local-closure",
            "dsh_closure_files": 11084,
        },
    )
    (manager.runtime_source / "apps" / "cli" / "lib").mkdir(parents=True)
    (manager.runtime_source / "apps" / "cli" / "lib" / "bin.js").touch()

    assert manager._dsh_build_status()["ready"] is True

    monkeypatch.setattr(
        service_manager_module,
        "calculate_build_closure",
        lambda _source: ("tampered-closure", 11084),
    )
    assert manager._dsh_build_status()["ready"] is False


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_linked_runtime_directory(manager):
    manager._prepare_private_directories()
    external = manager.project_root / "external-runtime"
    external.mkdir()
    (external / "build-lock.json").write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    (manager.data_root / "runtime").symlink_to(external, target_is_directory=True)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_linked_data_parent(manager):
    external_parent = manager.project_root / "external-data"
    runtime = external_parent / manager.data_root.name / "runtime"
    runtime.mkdir(parents=True)
    lock = runtime / "build-lock.json"
    lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    lock.chmod(0o600)
    manager.data_root.parent.rmdir()
    manager.data_root.parent.symlink_to(external_parent, target_is_directory=True)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_preexisting_data_parent_alias(tmp_path):
    external_parent = tmp_path / "external-data"
    runtime = external_parent / "research-web" / "runtime"
    runtime.mkdir(parents=True)
    lock = runtime / "build-lock.json"
    lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    lock.chmod(0o600)
    alias = tmp_path / "data-alias"
    alias.symlink_to(external_parent, target_is_directory=True)
    source = tmp_path / "dsh"
    source.mkdir()
    python = tmp_path / "python"
    python.touch()
    node = tmp_path / "node"
    node.touch()
    manager = WebServiceManager(
        project_root=tmp_path,
        data_root=alias / "research-web",
        runtime_source=source,
        python=str(python),
        node=str(node),
    )

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


def test_runtime_build_lock_reader_requires_an_integer_file_count(manager):
    manager._prepare_private_directories()
    runtime = manager.data_root / "runtime"
    runtime.mkdir()
    (runtime / "build-lock.json").write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084.0,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    (runtime / "build-lock.json").chmod(0o600)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


def test_package_version_probe_preserves_present_packages_when_one_is_missing(manager, monkeypatch):
    class Result:
        returncode = 0
        stdout = json.dumps({"cjpy": None, "requests": "2.34.2", "urllib3": "2.8.0"})

    monkeypatch.setattr(
        service_manager_module.subprocess, "run", lambda *_args, **_kwargs: Result()
    )

    assert manager._installed_package_versions() == {
        "cjpy": None,
        "requests": "2.34.2",
        "urllib3": "2.8.0",
    }


def test_runtime_health_exchanges_cookie_and_writes_private_auth(manager, monkeypatch):
    manager._prepare_private_directories()
    (manager.runtime_source / "package.json").write_text(
        json.dumps({"version": "0.1.3-alpha.2"}), encoding="utf-8"
    )
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda token: "dsh-auth-test=value")
    requests = []

    def request(port, method, path, payload=None, extra_headers=None):
        requests.append((port, method, path, payload, extra_headers))
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {"ok": True, "value": {"items": []}},
        }

    monkeypatch.setattr(manager, "_json_request", request)

    assert manager._runtime_healthy() is True
    auth_path = manager._runtime_auth_path()
    assert auth_path.stat().st_mode & 0o777 == 0o600
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    assert auth["cookie"] == "dsh-auth-test=value"
    assert auth["authority"] == "127.0.0.1:3081"
    assert requests[0][0:3] == (3081, "POST", "/api/session/list")
    assert requests[0][3]["payload"] == {"args": {"_request": {}}}
    assert requests[0][4] == {"Cookie": "dsh-auth-test=value"}


def test_runtime_sessions_returns_authoritative_session_list(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )
    requests = []

    def request(port, method, path, payload=None, extra_headers=None):
        requests.append((port, method, path, payload, extra_headers))
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {
                "ok": True,
                "value": {
                    "items": [
                        {"sessionId": "idle-parent", "running": False},
                        {"sessionId": "running-child", "running": True},
                    ]
                },
            },
        }

    monkeypatch.setattr(manager, "_json_request", request)

    assert manager._runtime_sessions() == [
        {"sessionId": "idle-parent", "running": False},
        {"sessionId": "running-child", "running": True},
    ]
    assert requests[0][0:3] == (3081, "POST", "/api/session/list")
    assert requests[0][3]["type"] == "client-request"
    assert requests[0][3]["method"] == "session/list"
    assert requests[0][3]["payload"] == {"args": {"_request": {}}}
    assert requests[0][4] == {"Cookie": "dsh-auth-test=value"}


@pytest.mark.parametrize(
    "response",
    [
        {
            "type": "client-response",
            "rpcId": None,
            "result": {"ok": True, "value": {"items": []}},
        },
        {
            "type": "server-response",
            "rpcId": "mismatched",
            "result": {"ok": True, "value": {"items": []}},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": False, "value": {"items": []}},
        },
        {"type": "server-response", "rpcId": None, "result": []},
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": []},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": {}},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": {"items": {}}},
        },
    ],
)
def test_runtime_sessions_rejects_invalid_protocol_response(manager, monkeypatch, response):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )

    def request(_port, _method, _path, payload=None, _extra_headers=None):
        value = dict(response)
        if value.get("rpcId") is None:
            value["rpcId"] = payload["rpcId"]
        return value

    monkeypatch.setattr(manager, "_json_request", request)

    with pytest.raises(ServiceManagerError, match="DSH 会话状态响应无效"):
        manager._runtime_sessions()
    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


@pytest.mark.parametrize(
    "items",
    [
        [None],
        [{}],
        [{"sessionId": "", "running": False}],
        [{"sessionId": "x", "running": "yes"}],
    ],
)
def test_runtime_sessions_rejects_invalid_session_items(manager, monkeypatch, items):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )

    def request(_port, _method, _path, payload=None, _extra_headers=None):
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {"ok": True, "value": {"items": items}},
        }

    monkeypatch.setattr(manager, "_json_request", request)

    with pytest.raises(ServiceManagerError, match="DSH 会话状态响应无效"):
        manager._runtime_sessions()
    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_sessions_fails_closed_when_auth_is_unavailable(manager, monkeypatch):
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: None)
    monkeypatch.setattr(
        manager,
        "_json_request",
        lambda *_args, **_kwargs: pytest.fail("request must not run without auth"),
    )

    with pytest.raises(ServiceManagerError, match="DSH 认证不可用"):
        manager._runtime_sessions()


@pytest.mark.parametrize(
    "package_content",
    [None, b"{", b"{}", b"[]", b"\xff"],
    ids=["missing", "malformed-json", "missing-version", "wrong-type", "invalid-utf8"],
)
def test_runtime_auth_regeneration_fails_closed_for_invalid_package_metadata(
    manager, monkeypatch, package_content
):
    manager._prepare_private_directories()
    if package_content is not None:
        (manager.runtime_source / "package.json").write_bytes(package_content)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_auth_regeneration_fails_closed_when_tempfile_creation_fails(manager, monkeypatch):
    manager._prepare_private_directories()
    (manager.runtime_source / "package.json").write_text(
        json.dumps({"version": "0.1.3-alpha.2"}), encoding="utf-8"
    )
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    def fail_mkstemp(*_args, **_kwargs):
        raise OSError("tempfile unavailable")

    monkeypatch.setattr(service_manager_module.tempfile, "mkstemp", fail_mkstemp)

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


class _FakeHttpResponse:
    def __init__(self, status, content_type, body, *, read_error=None):
        self.status = status
        self._content_type = content_type
        self._body = body
        self._read_error = read_error
        self.read_limit = None

    def getheader(self, name):
        assert name == "Content-Type"
        return self._content_type

    def read(self, limit):
        self.read_limit = limit
        if self._read_error is not None:
            raise self._read_error
        return self._body[:limit]


class _FakeHttpConnection:
    def __init__(self, response=None, *, error=None, close_error=None):
        self.response = response
        self.error = error
        self.close_error = close_error
        self.closed = False
        self.requested = None

    def request(self, method, path, body=None, headers=None):
        self.requested = (method, path, body, headers)
        if self.error is not None:
            raise self.error

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def test_direct_loopback_text_request_is_bounded_and_always_closes(manager, monkeypatch):
    response = _FakeHttpResponse(200, "text/plain; charset=utf-8", b"ready")
    connection = _FakeHttpConnection(response)
    captured = {}

    def connect(host, port, timeout):
        captured.update(host=host, port=port, timeout=timeout)
        return connection

    monkeypatch.setattr(service_manager_module.http.client, "HTTPConnection", connect)

    result = manager._text_request(8088, "/health", max_bytes=32)

    assert result == (200, "text/plain; charset=utf-8", "ready")
    assert captured == {"host": "127.0.0.1", "port": 8088, "timeout": 2}
    assert connection.requested == ("GET", "/health", None, {})
    assert response.read_limit == 33
    assert connection.closed is True


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (_FakeHttpResponse(200, "text/plain", b"x" * 34), None),
        (None, ConnectionRefusedError("private endpoint")),
        (_FakeHttpResponse(200, "text/plain", b"\xff"), None),
    ],
    ids=["oversize", "connection", "non-utf8"],
)
def test_direct_loopback_text_request_returns_only_stable_failures(
    manager, monkeypatch, response, error
):
    connection = _FakeHttpConnection(response, error=error)
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._text_request(8088, "/health", max_bytes=32)

    assert str(captured.value) == "本地服务响应无效"
    assert "private endpoint" not in str(captured.value)
    assert connection.closed is True


def test_json_request_reads_limit_plus_one_and_rejects_valid_prefix_with_trailing_data(
    manager, monkeypatch
):
    prefix = b'{"ok": true}'
    body = (
        prefix
        + b" " * (service_manager_module.MAX_HTTP_BODY_BYTES - len(prefix))
        + b"private-trailing-data"
    )
    response = _FakeHttpResponse(200, "application/json", body)
    connection = _FakeHttpConnection(response)
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert response.read_limit == service_manager_module.MAX_HTTP_BODY_BYTES + 1
    assert connection.closed is True


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json; charset=utf-8",
        "Application/Problem+JSON; profile=safe",
        "application/vnd.research-workbench+json",
    ],
    ids=["json-with-parameters", "problem-json-case-insensitive", "vendor-json"],
)
def test_json_request_accepts_application_json_and_structured_json_suffixes(
    manager, monkeypatch, content_type
):
    response = _FakeHttpResponse(200, content_type, b'{"ok": true}')
    connection = _FakeHttpConnection(response)
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    assert manager._json_request(8088, "GET", "/api/research/runtime") == {"ok": True}
    assert connection.closed is True


@pytest.mark.parametrize(
    "content_type",
    [None, "", "text/plain", "application/jsonp", "application/problem+xml"],
    ids=["missing", "empty", "text", "jsonp", "structured-xml"],
)
def test_json_request_rejects_missing_or_non_json_content_type(manager, monkeypatch, content_type):
    response = _FakeHttpResponse(200, content_type, b'{"ok": true}')
    connection = _FakeHttpConnection(response)
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert connection.closed is True


@pytest.mark.parametrize(
    "body",
    [b"\xffprivate-utf8", b'{"private-json":'],
    ids=["invalid-utf8", "invalid-json"],
)
def test_json_request_maps_decode_and_parse_failures_to_stable_error(manager, monkeypatch, body):
    response = _FakeHttpResponse(200, "application/json", body)
    connection = _FakeHttpConnection(response)
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert "private" not in str(captured.value)
    assert connection.closed is True


def test_json_request_maps_close_failure_after_success_to_stable_error(manager, monkeypatch):
    response = _FakeHttpResponse(200, "application/json", b'{"ok": true}')
    connection = _FakeHttpConnection(
        response,
        close_error=OSError("private-close-secret"),
    )
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert "private-close-secret" not in str(captured.value)
    assert captured.value.__cause__ is connection.close_error
    assert connection.closed is True


def test_json_request_does_not_mistake_outer_exception_for_primary_failure(manager, monkeypatch):
    response = _FakeHttpResponse(200, "application/json", b'{"ok": true}')
    connection = _FakeHttpConnection(
        response,
        close_error=OSError("private-close-secret"),
    )
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    try:
        raise LookupError("outer failure")
    except LookupError:
        with pytest.raises(ServiceManagerError) as captured:
            manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert connection.closed is True


@pytest.mark.parametrize("primary_failure", ["request", "read", "parse"])
def test_json_request_close_failure_does_not_mask_primary_failure(
    manager, monkeypatch, primary_failure
):
    response = _FakeHttpResponse(
        200,
        "application/json",
        b"{" if primary_failure == "parse" else b'{"ok": true}',
        read_error=(OSError("private-read-secret") if primary_failure == "read" else None),
    )
    connection = _FakeHttpConnection(
        response,
        error=(OSError("private-request-secret") if primary_failure == "request" else None),
        close_error=OSError("private-close-secret"),
    )
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._json_request(8088, "GET", "/api/research/runtime")

    assert str(captured.value) == "本地服务尚未就绪"
    assert "private" not in str(captured.value)
    if primary_failure in {"request", "read"}:
        assert captured.value.__cause__ is (
            connection.error if primary_failure == "request" else response._read_error
        )
    else:
        assert isinstance(captured.value.__cause__, json.JSONDecodeError)
    assert connection.closed is True


def _readiness_responses(**overrides):
    values = {
        "/api/research/runtime": (
            200,
            "application/json",
            json.dumps(
                {
                    "connected": True,
                    "health_check_passed": True,
                    "provider": "provider",
                    "model": "model",
                    "credential_configured": True,
                }
            ),
        ),
        "/": (200, "text/html; charset=utf-8", "<title>Research Workbench · Research</title>"),
        "/static/app.mjs": (
            200,
            "text/javascript; charset=utf-8",
            "const defaultCatalogNames = ['runtime'];",
        ),
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("overrides", "issue"),
    [
        (
            {
                "/api/research/runtime": (
                    200,
                    "application/json",
                    '{"connected": false, "health_check_passed": true}',
                )
            },
            "web_runtime_api_failed",
        ),
        (
            {"/api/research/runtime": (200, "application/json", "{")},
            "web_runtime_api_failed",
        ),
        (
            {
                "/api/research/runtime": (
                    200,
                    "application/json",
                    '{"connected": true, "health_check_passed": false}',
                )
            },
            "web_runtime_api_failed",
        ),
        ({"/": (503, "text/html", "unavailable")}, "web_root_failed"),
        ({"/": (200, "text/plain", "Research Workbench · Research")}, "web_root_failed"),
        ({"/": (200, "text/html", "wrong shell")}, "web_root_failed"),
        ({"/static/app.mjs": (404, "text/javascript", "missing")}, "web_static_asset_failed"),
        (
            {"/static/app.mjs": (200, "text/plain", "const defaultCatalogNames = [];")},
            "web_static_asset_failed",
        ),
        (
            {"/static/app.mjs": (200, "application/javascript", "wrong bundle")},
            "web_static_asset_failed",
        ),
    ],
)
def test_web_readiness_maps_each_product_surface_failure(manager, monkeypatch, overrides, issue):
    responses = _readiness_responses(**overrides)
    monkeypatch.setattr(
        manager,
        "_text_request",
        lambda _port, _path, *, max_bytes: responses[_path],
    )

    result = manager._web_ready()

    assert result.ready is False
    assert result.issues == (issue,)


def test_web_readiness_requires_runtime_root_and_static_asset(manager, monkeypatch):
    responses = _readiness_responses()
    requested = []

    def request(_port, path, *, max_bytes):
        requested.append((path, max_bytes))
        return responses[path]

    monkeypatch.setattr(manager, "_text_request", request)

    result = manager._web_ready()

    assert result.ready is True
    assert result.issues == ()
    assert [path for path, _limit in requested] == [
        "/api/research/runtime",
        "/",
        "/static/app.mjs",
    ]
    assert all(limit <= 2 * 1024 * 1024 for _path, limit in requested)


def test_web_probe_preserves_specific_readiness_issue(manager, monkeypatch):
    process, state_path = _valid_state(manager, "web")
    state = json.loads(state_path.read_bytes())
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(
        manager,
        "_web_ready",
        lambda: service_manager_module._WebReadiness(False, ("web_static_asset_failed",)),
    )

    probe = manager._probe_service(process)

    assert probe.ready is False
    assert probe.protocol == "failed"
    assert probe.issues == ("web_static_asset_failed",)


def test_start_waits_for_runtime_readiness_before_web_spawn_and_browser(manager, monkeypatch):
    processes = {process.role: process for process in manager._processes()}
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    events = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn_and_wait(process):
        events.append(f"spawn:{process.role}")
        if process.role == "web":
            assert probes["runtime"].ready is True
        probes[process.role] = _service_probe(
            process.role, pid=101 if process.role == "runtime" else 202
        )
        events.append(f"ready:{process.role}")
        return probes[process.role].pid

    monkeypatch.setattr(manager, "_spawn_and_wait", spawn_and_wait)

    def status():
        events.append("status:final")
        return {
            "url": manager.web_url,
            "product_ready": all(probe.ready for probe in probes.values()),
            "warnings": [],
            "services": {},
        }

    monkeypatch.setattr(manager, "status", status)
    monkeypatch.setattr(
        service_manager_module.webbrowser,
        "open",
        lambda url: events.append(f"browser:{url}") or True,
    )

    result = manager.start(open_browser=True)

    assert result["product_ready"] is True
    assert events == [
        "spawn:runtime",
        "ready:runtime",
        "spawn:web",
        "ready:web",
        "status:final",
        f"browser:{manager.web_url}",
    ]
    assert processes["runtime"].role == "runtime"


@pytest.mark.parametrize(
    "browser_result",
    [
        False,
        service_manager_module.webbrowser.Error("expected"),
        OSError("expected"),
        subprocess.SubprocessError("expected"),
    ],
    ids=["false", "browser-error", "os-error", "platform-error"],
)
def test_browser_open_failure_is_a_nonblocking_warning_without_rollback(
    manager, monkeypatch, browser_result
):
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    spawned = []
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: probes[process.role],
    )

    def spawn_and_wait(process):
        pid = 101 if process.role == "runtime" else 202
        spawned.append((process.role, pid))
        probes[process.role] = _service_probe(process.role, pid=pid)
        return pid

    monkeypatch.setattr(manager, "_spawn_and_wait", spawn_and_wait)
    monkeypatch.setattr(
        manager, "_rollback_spawned", lambda *_args: pytest.fail("must not rollback")
    )
    monkeypatch.setattr(
        manager, "_stop_owned_probe", lambda *_args: pytest.fail("must not stop a ready service")
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": True,
            "warnings": [],
            "services": {},
        },
    )

    def open_browser(_url):
        if isinstance(browser_result, BaseException):
            raise browser_result
        return browser_result

    monkeypatch.setattr(service_manager_module.webbrowser, "open", open_browser)

    result = manager._start_locked(diagnosis={"ok": True}, open_browser=True)

    assert result["product_ready"] is True
    assert result["warnings"] == ["browser_open_failed"]
    assert result["url"] == manager.web_url
    assert spawned == [("runtime", 101), ("web", 202)]


def test_no_open_never_calls_browser_and_adds_no_warning(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(process.role, pid=101 if process.role == "runtime" else 202),
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": True,
            "warnings": [],
            "services": {},
        },
    )
    monkeypatch.setattr(
        service_manager_module.webbrowser,
        "open",
        lambda _url: pytest.fail("--no-open must not call browser"),
    )

    result = manager._start_locked(diagnosis={"ok": True}, open_browser=False)

    assert result["warnings"] == []


def test_browser_never_opens_when_final_product_status_is_not_ready(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(process.role, pid=101 if process.role == "runtime" else 202),
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": False,
            "warnings": [],
            "services": {},
        },
    )
    monkeypatch.setattr(
        service_manager_module.webbrowser,
        "open",
        lambda _url: pytest.fail("partial readiness must never open the browser"),
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(ServiceManagerError) as captured:
        manager._start_locked(diagnosis={"ok": True}, open_browser=True)

    assert captured.value.code == "product_not_ready"


def test_start_reports_final_web_health_issue(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(process.role, pid=101 if process.role == "runtime" else 202),
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": False,
            "warnings": [],
            "services": {
                "runtime": {"ready": True, "issues": []},
                "web": {"ready": False, "issues": ["web_static_asset_failed"]},
            },
        },
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(ServiceManagerError) as captured:
        manager._start_locked(diagnosis={"ok": True}, open_browser=False)

    assert captured.value.code == "web_static_asset_failed"
    assert captured.value.role == "web"


def test_start_rechecks_transient_final_product_status_before_opening_browser(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(process.role, pid=101 if process.role == "runtime" else 202),
    )
    checks = iter([False, True])
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": next(checks),
            "warnings": [],
            "services": {},
        },
    )
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)
    opened = []
    monkeypatch.setattr(
        service_manager_module.webbrowser, "open", lambda url: opened.append(url) or True
    )

    result = manager._start_locked(diagnosis={"ok": True}, open_browser=True)

    assert result["product_ready"] is True
    assert opened == [manager.web_url]


def test_browser_unexpected_base_exception_is_not_swallowed(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(process.role, pid=101 if process.role == "runtime" else 202),
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "product_ready": True,
            "warnings": [],
            "services": {},
        },
    )
    monkeypatch.setattr(
        service_manager_module.webbrowser,
        "open",
        lambda _url: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        manager._start_locked(diagnosis={"ok": True}, open_browser=True)


@pytest.mark.parametrize(
    ("exists", "version", "issue"),
    [
        (False, None, "node_unavailable"),
        (True, None, "node_version_invalid"),
        (True, "not-a-version", "node_version_invalid"),
        (True, "v20.19.0", "node_version_unsupported"),
        (True, "v24.19.0", None),
    ],
)
def test_node_diagnosis_uses_shared_install_contract(manager, monkeypatch, exists, version, issue):
    monkeypatch.setattr(service_manager_module.Path, "is_file", lambda path: exists)
    monkeypatch.setattr(manager, "_executable_version", lambda _path: version)

    assert manager._node_diagnosis() == (version, issue)


@pytest.mark.parametrize(
    ("runtime", "models", "ready", "warnings"),
    [
        (
            {"provider": None, "model": None, "credential_configured": True},
            {"groups": [], "failures": []},
            False,
            ("model_configuration_missing",),
        ),
        (
            {"provider": "provider", "model": "model", "credential_configured": False},
            {"groups": [], "failures": []},
            False,
            ("model_credential_missing",),
        ),
        (
            {"provider": "provider", "model": "model", "credential_configured": True},
            {"groups": [], "failures": [{"provider": "private", "error": "secret"}]},
            False,
            ("model_catalog_unavailable",),
        ),
        (
            {"provider": "provider", "model": "model", "credential_configured": True},
            {"groups": {}, "failures": []},
            False,
            ("model_catalog_unavailable",),
        ),
        (
            {"provider": "provider", "model": "model", "credential_configured": True},
            {"groups": [], "failures": []},
            True,
            (),
        ),
    ],
)
def test_model_diagnosis_is_safe_nonblocking_and_never_generates(
    manager, monkeypatch, runtime, models, ready, warnings
):
    requests = []

    def request(_port, method, path, payload=None, extra_headers=None):
        requests.append((method, path, payload, extra_headers))
        if path == "/api/research/runtime":
            return runtime
        if path == "/api/research/models":
            return models
        pytest.fail("model diagnosis must not invoke generation endpoints")

    monkeypatch.setattr(manager, "_json_request", request)

    result = manager._model_diagnosis()

    assert result == (ready, warnings)
    assert requests == [
        ("GET", "/api/research/runtime", None, None),
        ("GET", "/api/research/models", None, None),
    ]
    assert "secret" not in repr(result)


def test_model_catalog_request_failure_is_warning_only(manager, monkeypatch):
    def request(_port, _method, path, payload=None, extra_headers=None):
        if path == "/api/research/runtime":
            return {"provider": "provider", "model": "model", "credential_configured": True}
        raise ServiceManagerError("private provider failure")

    monkeypatch.setattr(manager, "_json_request", request)

    assert manager._model_diagnosis() == (False, ("model_catalog_unavailable",))


@pytest.mark.parametrize(
    "failure",
    [
        "oversize",
        "missing-content-type",
        "wrong-content-type",
        "invalid-utf8",
        "invalid-json",
        "close",
    ],
)
def test_doctor_maps_json_response_failures_to_model_catalog_warning(manager, monkeypatch, failure):
    runtime_response = _FakeHttpResponse(
        200,
        "application/json",
        b'{"provider":"provider","model":"model","credential_configured":true}',
    )
    if failure == "oversize":
        prefix = b'{"groups":[],"failures":[]}'
        body = (
            prefix
            + b" " * (service_manager_module.MAX_HTTP_BODY_BYTES - len(prefix))
            + b"private-trailing-data"
        )
        catalog_response = _FakeHttpResponse(200, "application/json", body)
        catalog_connection = _FakeHttpConnection(catalog_response)
    elif failure in {"missing-content-type", "wrong-content-type"}:
        content_type = None if failure == "missing-content-type" else "text/plain"
        catalog_connection = _FakeHttpConnection(
            _FakeHttpResponse(200, content_type, b'{"groups":[],"failures":[]}')
        )
    elif failure == "invalid-utf8":
        catalog_connection = _FakeHttpConnection(
            _FakeHttpResponse(200, "application/json", b"\xffprivate-utf8")
        )
    elif failure == "invalid-json":
        catalog_connection = _FakeHttpConnection(
            _FakeHttpResponse(200, "application/json", b'{"private-json":')
        )
    else:
        catalog_connection = _FakeHttpConnection(
            _FakeHttpResponse(200, "application/json", b'{"groups":[],"failures":[]}'),
            close_error=OSError("private-close-secret"),
        )
    connections = [
        _FakeHttpConnection(runtime_response),
        catalog_connection,
    ]
    monkeypatch.setattr(
        service_manager_module.http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: connections.pop(0),
    )
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (_service_probe("runtime", pid=101), _service_probe("web", pid=202)),
    )

    report = manager.doctor()

    assert report["product_ready"] is True
    assert report["model_ready"] is False
    assert report["warnings"] == ["model_catalog_unavailable"]
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("environment", [{"HTTP_PROXY": "secret"}, {"https_proxy": "secret"}])
def test_doctor_merges_safe_proxy_warning_only(manager, monkeypatch, environment):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (
            _service_probe("runtime", pid=101),
            _service_probe("web", pid=202),
        ),
    )
    monkeypatch.setattr(manager, "_model_diagnosis", lambda: (True, ()))
    monkeypatch.setattr(service_manager_module.os, "environ", environment)

    report = manager.doctor()

    assert report["ok"] is True
    assert report["installation_ok"] is True
    assert report["product_ready"] is True
    assert report["model_ready"] is True
    assert report["issues"] == []
    assert report["warnings"] == ["loopback_proxy_bypass_missing"]
    assert "secret" not in json.dumps(report)


def test_status_formatter_prints_warnings_and_copyable_url():
    rendered = format_status(
        {
            "url": "http://127.0.0.1:8088/#/fingpt",
            "product_ready": True,
            "warnings": ["browser_open_failed"],
            "services": {
                role: _service_probe(role, pid=101 if role == "runtime" else 202).public()
                for role in ("runtime", "web")
            },
        }
    )

    assert "warnings: browser_open_failed" in rendered
    assert "url: http://127.0.0.1:8088/#/fingpt" in rendered


def test_runtime_auth_regeneration_preserves_service_manager_fail_closed_contract(
    manager, monkeypatch
):
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    def fail_write(_cookie):
        raise ServiceManagerError("无法写入 DSH 认证控制文件")

    monkeypatch.setattr(manager, "_write_runtime_auth", fail_write)

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_healthy_reuses_runtime_sessions(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(manager, "_runtime_sessions", lambda: calls.append(True) or [])

    assert manager._runtime_healthy() is True
    assert calls == [True]

    def fail():
        raise ServiceManagerError("DSH 会话状态响应无效")

    monkeypatch.setattr(manager, "_runtime_sessions", fail)
    assert manager._runtime_healthy() is False


def test_active_research_uses_all_authoritative_runtime_sessions(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_runtime_sessions",
        lambda: [
            {"sessionId": "idle-parent", "running": False},
            {"sessionId": "running-child", "running": True},
            {"sessionId": "unknown-running", "running": True},
        ],
    )

    assert manager._active_research() == ["running-child", "unknown-running"]


def test_runtime_auth_fails_closed_for_foreign_authority(manager):
    manager._prepare_private_directories()
    auth_path = manager._runtime_auth_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(
        json.dumps(
            {
                "authority": "127.0.0.1:9999",
                "cookie": "dsh-auth-test=value",
                "cwd": str((manager.data_root / "runtime/work").resolve()),
                "source_commit": "c919b2a460753859665db3f60143d525fb9140cf",
                "version": "0.1.3-alpha.2",
            }
        ),
        encoding="utf-8",
    )
    auth_path.chmod(0o600)

    assert manager._read_runtime_auth() is None


def test_windows_runtime_auth_reader_does_not_apply_posix_group_mode_bits(manager, monkeypatch):
    manager._prepare_private_directories()
    auth_path = manager._runtime_auth_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(
        json.dumps(
            {
                "authority": "127.0.0.1:3081",
                "cookie": "dsh-auth-test=value",
                "cwd": str((manager.data_root / "runtime/work").resolve()),
                "source_commit": "c919b2a460753859665db3f60143d525fb9140cf",
                "version": "0.1.3-alpha.2",
            }
        ),
        encoding="utf-8",
    )
    auth_path.chmod(0o644)
    with monkeypatch.context() as patcher:
        patcher.setattr(
            service_manager_module,
            "read_runtime_auth_record",
            lambda path: runtime_auth_module.read_runtime_auth_record(path, platform_name="nt"),
        )
        auth = manager._read_runtime_auth()

    assert auth["cookie"] == "dsh-auth-test=value"
