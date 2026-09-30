"""Runtime-mode persistence stays private, strict and bootstrap-safe."""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import re
import stat
import subprocess
import sys
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint import runtime_mode
from research_workbench_entrypoint.runtime_mode import RuntimeModeError, RuntimeModeStore


def _path(home: Path) -> Path:
    return home / "install" / "runtime.json"


def _payload(*, mode: str = "native", installation_id: str = "a" * 32) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": mode,
        "installation_id": installation_id,
        "updated_at": "2026-09-29T01:02:03.456789Z",
    }


def _write_payload(home: Path, payload: object) -> Path:
    path = _path(home)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _with_uid(identity: os.stat_result, uid: int) -> SimpleNamespace:
    return SimpleNamespace(
        **{
            name: getattr(identity, name)
            for name in (
                "st_mode",
                "st_nlink",
                "st_size",
                "st_dev",
                "st_ino",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        },
        st_uid=uid,
        st_file_attributes=getattr(identity, "st_file_attributes", 0),
    )


def test_missing_record_defaults_to_native_without_writing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    record = RuntimeModeStore(home).read()

    assert record.schema_version == 1
    assert record.mode == "native"
    assert record.installation_id == ""
    assert record.updated_at is None
    assert not _path(home).exists()
    with pytest.raises(FrozenInstanceError):
        record.mode = "docker"
    assert not hasattr(record, "__dict__")


def test_first_write_is_private_and_generates_one_persistent_id(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    store = RuntimeModeStore(home)

    first = store.write("docker")
    second = store.write("native")

    assert first.mode == "docker"
    assert second.mode == "native"
    assert re.fullmatch(r"[a-f0-9]{32}", first.installation_id)
    assert second.installation_id == first.installation_id
    assert second.updated_at is not None
    assert stat.S_IMODE(_path(home).parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(_path(home).stat().st_mode) == 0o600
    assert RuntimeModeStore(home).read() == second


def test_unrelated_ancestor_entry_change_does_not_invalidate_read(tmp_path, monkeypatch):
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    expected = store.write("native")
    original = os.open

    def concurrent_sibling(candidate, flags, *args, **kwargs):
        if Path(candidate).name == "runtime.json":
            (tmp_path / "unrelated").mkdir()
        return original(candidate, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", concurrent_sibling)
    assert store.read() == expected


def test_same_mode_switch_is_read_only(tmp_path):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    home = tmp_path / "missing"
    store = RuntimeModeStore(home)
    assert switch_runtime(store, "native", None, None) == {
        "schema_version": 1, "ok": True, "issues": [], "mode": "native", "changed": False,
    }
    assert not home.exists()


def test_conditional_mode_write_rejects_concurrent_change(tmp_path):
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    expected = store.write("native")
    changed = RuntimeModeStore(home).write("docker")
    with pytest.raises(RuntimeModeError, match="runtime_mode_changed"):
        store.write("native", expected=expected)
    assert store.read() == changed


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"{", "runtime_mode_json"),
        (b"\xff", "runtime_mode_encoding"),
        (b" " * (16 * 1024 + 1), "runtime_mode_too_large"),
        (b'{"schema_version":1,"schema_version":1}', "runtime_mode_json"),
        (b'{"schema_version":NaN}', "runtime_mode_json"),
        (b"[" * 2000, "runtime_mode_json"),
    ],
)
def test_rejects_invalid_or_unbounded_input(tmp_path: Path, raw: bytes, code: str) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    path.write_bytes(raw)

    with pytest.raises(RuntimeModeError, match=f"^{code}$") as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == code


@pytest.mark.parametrize("change", ["extra", "missing", "not_object"])
def test_rejects_inexact_schema(tmp_path: Path, change: str) -> None:
    home = tmp_path / "home"
    payload: object = _payload()
    if change == "extra":
        assert isinstance(payload, dict)
        payload["unexpected"] = True
    elif change == "missing":
        assert isinstance(payload, dict)
        payload.pop("updated_at")
    else:
        payload = []
    _write_payload(home, payload)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_keys$"):
        RuntimeModeStore(home).read()


@pytest.mark.parametrize(
    "key,value,code",
    [
        ("schema_version", True, "runtime_mode_type"),
        ("schema_version", 2, "runtime_mode_value"),
        ("mode", 1, "runtime_mode_type"),
        ("mode", "podman", "runtime_mode_value"),
        ("installation_id", 1, "runtime_mode_type"),
        ("installation_id", "A" * 32, "runtime_mode_value"),
        ("installation_id", "a" * 31, "runtime_mode_value"),
        ("updated_at", None, "runtime_mode_type"),
        ("updated_at", "not-a-time", "runtime_mode_value"),
        ("updated_at", "2026-99-99T01:02:03.456789Z", "runtime_mode_value"),
    ],
)
def test_rejects_invalid_field(tmp_path: Path, key: str, value: object, code: str) -> None:
    home = tmp_path / "home"
    payload = _payload()
    payload[key] = value
    _write_payload(home, payload)

    with pytest.raises(RuntimeModeError, match=f"^{code}$") as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == code


@pytest.mark.parametrize("value", ["podman", "Native", "", None, 1, True])
def test_write_rejects_unknown_mode(tmp_path: Path, value: object) -> None:
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(RuntimeModeError, match="^runtime_mode_value$"):
        RuntimeModeStore(home).write(value)  # type: ignore[arg-type]

    assert not _path(home).exists()


def test_store_rejects_changed_installation_id(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    store = RuntimeModeStore(home)
    record = store.write("native")
    replacement_id = "b" * 32 if record.installation_id != "b" * 32 else "c" * 32
    _write_payload(home, _payload(installation_id=replacement_id))

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        store.read()


@pytest.mark.parametrize("alias", ["file_symlink", "parent_symlink", "hardlink", "directory"])
def test_rejects_aliases_and_non_regular_files(tmp_path: Path, alias: str) -> None:
    real_home = tmp_path / "real-home"
    source = _write_payload(real_home, _payload())
    home = tmp_path / "home"
    if alias == "file_symlink":
        home.mkdir()
        (home / "install").mkdir()
        _path(home).symlink_to(source)
    elif alias == "parent_symlink":
        home.symlink_to(real_home, target_is_directory=True)
    elif alias == "hardlink":
        home.mkdir()
        (home / "install").mkdir()
        os.link(source, _path(home))
    else:
        home.mkdir()
        _path(home).mkdir(parents=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


def test_write_rejects_symlinked_install_parent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    real_install = tmp_path / "real-install"
    real_install.mkdir()
    (home / "install").symlink_to(real_install, target_is_directory=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).write("docker")

    assert not (real_install / "runtime.json").exists()


def test_missing_record_does_not_hide_symlinked_parent(tmp_path: Path) -> None:
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    home = tmp_path / "home"
    home.symlink_to(real_home, target_is_directory=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
@pytest.mark.parametrize("target,mode", [("directory", 0o755), ("file", 0o644)])
def test_read_rejects_non_private_storage(tmp_path: Path, target: str, mode: int) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    (path.parent if target == "directory" else path).chmod(mode)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
@pytest.mark.parametrize("target", ["directory", "file"])
def test_read_rejects_other_uid_path_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    selected = path.parent if target == "directory" else path
    original = Path.lstat

    def lstat(candidate: Path):
        identity = original(candidate)
        if candidate == selected:
            return _with_uid(identity, os.getuid() + 1)
        return identity

    monkeypatch.setattr(Path, "lstat", lstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
@pytest.mark.parametrize("target", ["directory", "file"])
def test_read_rejects_other_uid_open_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    selected = path.parent if target == "directory" else path
    selected_inode = selected.stat().st_ino
    original = os.fstat

    def fstat(descriptor: int):
        identity = original(descriptor)
        if identity.st_ino == selected_inode:
            return _with_uid(identity, os.getuid() + 1)
        return identity

    monkeypatch.setattr(os, "fstat", fstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained descriptor contract")
def test_private_directory_chmod_uses_retained_descriptor_during_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install = home / "install"
    install.mkdir()
    install.chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o755)
    moved = home / "moved-install"
    install_inode = install.stat().st_ino
    original = os.fchmod
    attacked: list[bool] = []

    def fchmod(descriptor: int, mode: int):
        identity = os.fstat(descriptor)
        if identity.st_ino == install_inode and not attacked:
            attacked.append(True)
            install.rename(moved)
            install.symlink_to(outside, target_is_directory=True)
            try:
                return original(descriptor, mode)
            finally:
                install.unlink()
                moved.rename(install)
        return original(descriptor, mode)

    monkeypatch.setattr(os, "fchmod", fchmod)

    record = RuntimeModeStore(home).write("docker")

    assert record.mode == "docker"
    assert attacked == [True]
    assert stat.S_IMODE(install.stat().st_mode) == 0o700
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755


def test_rejects_windows_reparse_attribute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    original = Path.lstat

    def lstat(candidate: Path):
        identity = original(candidate)
        if candidate == path:
            return SimpleNamespace(
                **{
                    name: getattr(identity, name)
                    for name in (
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_dev",
                        "st_ino",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                },
                st_file_attributes=0x400,
            )
        return identity

    monkeypatch.setattr(Path, "lstat", lstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


def test_simulated_windows_parent_handles_reject_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    original = Path.lstat
    opened: list[int] = []
    closed: list[int] = []
    replaced = False

    def create_file(_path, access, sharing, security, disposition, flags, template):
        assert (access, sharing, security, disposition, flags, template) == (
            0x80,
            1,
            0,
            3,
            0x02200000,
            0,
        )
        handle = len(opened) + 1
        opened.append(handle)
        return handle

    def close_handle(handle):
        closed.append(handle)

    def lstat(candidate: Path):
        identity = original(candidate)
        if replaced and candidate == path.parent:
            return SimpleNamespace(
                **{
                    name: getattr(identity, name)
                    for name in (
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_dev",
                        "st_ino",
                        "st_mtime_ns",
                    )
                },
                st_file_attributes=0,
                st_ctime_ns=identity.st_ctime_ns + 1,
            )
        return identity

    monkeypatch.setitem(
        sys.modules,
        "_winapi",
        SimpleNamespace(CreateFile=create_file, CloseHandle=close_handle),
    )
    monkeypatch.setattr(Path, "lstat", lstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        with runtime_mode._pin_windows_parents(path):
            replaced = True

    assert len(opened) == len(path.parents)
    assert closed == list(reversed(opened))


def test_public_windows_read_write_does_not_treat_mode_bits_as_acl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    path.parent.chmod(0o755)
    path.chmod(0o644)
    store = RuntimeModeStore(home)
    fresh_store = RuntimeModeStore(home)
    opened: list[int] = []
    closed: list[int] = []
    lock_descriptors = {}
    lock_operations = []

    def create_file(_path, access, sharing, security, disposition, flags, template):
        if access == 0xC0000000:
            assert (sharing, security, disposition, flags, template) == (3, 0, 4, 0x00200000, 0)
            handle = len(opened) + 1
            opened.append(handle)
            lock_descriptors[handle] = os.open(str(_path), os.O_RDWR | os.O_CREAT, 0o600)
            return handle
        assert (access, sharing, security, disposition, flags, template) == (
            0x80,
            1,
            0,
            3,
            0x02200000,
            0,
        )
        handle = len(opened) + 1
        opened.append(handle)
        return handle

    def close_handle(handle):
        closed.append(handle)

    def transfer_handle(handle, flags):
        closed.append(handle)  # The returned fd now owns and closes this handle.
        return lock_descriptors.pop(handle)

    monkeypatch.setitem(
        sys.modules,
        "_winapi",
        SimpleNamespace(CreateFile=create_file, CloseHandle=close_handle),
    )
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(
        open_osfhandle=transfer_handle, LK_NBLCK=1, LK_UNLCK=0,
        locking=lambda fd, operation, size: lock_operations.append((operation, size)),
    ))
    monkeypatch.setattr(runtime_mode.os, "name", "nt")
    monkeypatch.setattr(runtime_mode.os, "chmod", lambda *_args, **_kwargs: None)

    before = store.read()
    after = store.write("docker")

    assert before.mode == "native"
    assert after.mode == "docker"
    assert after.installation_id == before.installation_id
    assert fresh_store.read() == after
    assert opened
    assert sorted(closed) == sorted(opened)
    assert lock_operations == [(1, 1), (0, 1)]


@pytest.mark.skipif(os.name != "posix", reason="Exercises POSIX retained directory descriptors")
def test_rejects_parent_replacement_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    install = path.parent
    moved = home / "moved-install"
    original = os.open
    attacked: list[bool] = []

    def swap_parent(candidate, flags, *args, **kwargs):
        if Path(candidate).name != path.name:
            return original(candidate, flags, *args, **kwargs)
        attacked.append(True)
        install.rename(moved)
        install.symlink_to(moved, target_is_directory=True)
        try:
            return original(candidate, flags, *args, **kwargs)
        finally:
            install.unlink()
            moved.rename(install)

    monkeypatch.setattr(os, "open", swap_parent)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        RuntimeModeStore(home).read()
    assert attacked == [True]


@pytest.mark.skipif(os.name != "posix", reason="Exercises POSIX atomic replacement")
def test_rejects_unsafe_destination_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    first = store.write("native")
    original = os.replace

    def replace_then_attack(source, destination, *args, **kwargs):
        original(source, destination, *args, **kwargs)
        destination_fd = kwargs["dst_dir_fd"]
        attacked = json.dumps(
            _payload(
                mode="docker",
                installation_id=("b" * 32 if first.installation_id != "b" * 32 else "c" * 32),
            )
        ).encode("utf-8")
        descriptor = os.open(destination, os.O_WRONLY | os.O_TRUNC, dir_fd=destination_fd)
        try:
            os.write(descriptor, attacked)
        finally:
            os.close(descriptor)

    monkeypatch.setattr(os, "replace", replace_then_attack)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        store.write("docker")


def test_failed_atomic_replace_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    def fail_replace(*_args, **_kwargs):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_io$") as caught:
        RuntimeModeStore(home).write("docker")

    assert [item.name for item in (home / "install").iterdir()] == ["runtime.lock"]
    assert stat.S_IMODE((home / "install/runtime.lock").stat().st_mode) == 0o600
    assert "private filesystem detail" not in "".join(traceback.format_exception(caught.value))


def test_failures_log_only_operation_and_code(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    home = tmp_path / "sensitive-home"
    _write_payload(home, {"secret-content": "do-not-log"})

    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeModeError) as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == "runtime_mode_keys"
    assert "operation=read" in caplog.text
    assert "code=runtime_mode_keys" in caplog.text
    assert "sensitive-home" not in caplog.text
    assert "secret-content" not in caplog.text


def test_module_import_is_stdlib_only() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "import research_workbench_entrypoint.runtime_mode; "
            "assert 'click' not in sys.modules; "
            "assert 'fastapi' not in sys.modules; "
            "assert 'structlog' not in sys.modules",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _interleaved_writer(home, expected, entered, release, started, finished, results, hold):
    original = os.replace
    original_load = RuntimeModeStore._load
    replaced = False

    def replace(*args, **kwargs):
        nonlocal replaced
        if hold == "replace":
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test release timeout")
        value = original(*args, **kwargs)
        replaced = True
        return value

    def load(store, *args, **kwargs):
        if hold == "readback" and replaced:
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test release timeout")
        return original_load(store, *args, **kwargs)

    os.replace = replace
    RuntimeModeStore._load = load
    started.set()
    try:
        record = RuntimeModeStore(Path(home)).write("docker", expected=expected)
        results.put(("ok", record.installation_id))
    except RuntimeModeError as error:
        results.put((error.code, None))
    finally:
        finished.set()


@pytest.mark.parametrize("existing", [False, True])
def test_cross_process_writes_are_serialized_through_readback(tmp_path, existing):
    home = tmp_path / "home"
    initial = RuntimeModeStore(home).write("native") if existing else None
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    started = [context.Event(), context.Event()]
    finished = [context.Event(), context.Event()]
    results = context.Queue()
    children = [context.Process(target=_interleaved_writer, args=(str(home), initial,
                entered, release, started[index], finished[index], results,
                "replace" if index == 0 else "none"))
                for index in range(2)]
    try:
        children[0].start()
        assert entered.wait(10)
        children[1].start()
        assert started[1].wait(10)
        assert not finished[1].wait(0.3), "second writer bypassed the critical section"
    finally:
        release.set()
        for child in children:
            if child.pid is not None:
                child.join(10)
                if child.is_alive():
                    child.terminate()
                    child.join(5)
    assert all(child.exitcode == 0 for child in children)
    values = [results.get(timeout=2), results.get(timeout=2)]
    if existing:
        assert sorted(value[0] for value in values) == ["ok", "runtime_mode_changed"]
    else:
        assert [value[0] for value in values] == ["ok", "ok"]
        assert values[0][1] == values[1][1] == RuntimeModeStore(home).read().installation_id


def test_cross_process_lock_covers_persisted_readback(tmp_path):
    home = tmp_path / "home"
    initial = RuntimeModeStore(home).write("native")
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    started = [context.Event(), context.Event()]
    finished = [context.Event(), context.Event()]
    results = context.Queue()
    children = [context.Process(target=_interleaved_writer, args=(str(home), initial,
                entered, release, started[index], finished[index], results,
                "readback" if index == 0 else "none")) for index in range(2)]
    try:
        children[0].start()
        assert entered.wait(10)
        children[1].start()
        assert started[1].wait(10)
        assert not finished[1].wait(0.3), "second writer entered before readback finished"
    finally:
        release.set()
        for child in children:
            if child.pid is not None:
                child.join(10)
                if child.is_alive():
                    child.terminate()
                    child.join(5)
    assert all(child.exitcode == 0 for child in children)
    assert sorted(results.get(timeout=2)[0] for _ in children) == ["ok", "runtime_mode_changed"]


def test_higher_ancestor_rename_restore_cannot_redirect_record(tmp_path, monkeypatch):
    home = tmp_path / "home"
    expected = RuntimeModeStore(home).write("native")
    decoy = tmp_path / "decoy"
    foreign = RuntimeModeStore(decoy).write("docker")
    moved = tmp_path / "moved"
    original = os.open
    attacked = []
    def swap(candidate, flags, *args, **kwargs):
        if Path(candidate).name != "runtime.json":
            return original(candidate, flags, *args, **kwargs)
        attacked.append(True)
        home.rename(moved)
        decoy.rename(home)
        try:
            return original(candidate, flags, *args, **kwargs)
        finally:
            home.rename(decoy)
            moved.rename(home)
    monkeypatch.setattr(os, "open", swap)
    assert RuntimeModeStore(home).read() == expected
    assert expected.installation_id != foreign.installation_id
    assert attacked == [True]


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public"])
def test_write_lock_rejects_unsafe_leaf(tmp_path, kind):
    home = tmp_path / "home"
    record = RuntimeModeStore(home).write("native")
    lock = home / "install/runtime.lock"
    lock.unlink(missing_ok=True)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"x")
    foreign.chmod(0o600)
    if kind == "symlink":
        lock.symlink_to(foreign)
    elif kind == "hardlink":
        os.link(foreign, lock)
    else:
        lock.write_bytes(b"x")
        lock.chmod(0o644)
    with pytest.raises(RuntimeModeError):
        RuntimeModeStore(home).write("docker")
    assert RuntimeModeStore(home).read() == record
