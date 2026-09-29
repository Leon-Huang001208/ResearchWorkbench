"""Strict, bounded shared runtime facts and bootstrap import boundaries."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import traceback
import zipfile
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research_web.runtime_contract import RuntimeContractError, load_runtime_contract

EXPECTED = {
    "schema_version": 1,
    "python": {"major": 3, "minor": 12, "docker_image": "python:3.12.13-slim-bookworm"},
    "node": {"major": 24, "minimum_minor": 0, "docker_image": "node:24.19.0-bookworm-slim"},
    "cjpy": {
        "version": "0.5.2",
        "sha256": "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94",
    },
    "dsh": {
        "remote": "https://github.com/Leon-Huang001208/deepseek-harness.git",
        "commit": "c919b2a460753859665db3f60143d525fb9140cf",
        "pnpm": "11.7.0",
        "closure_files": 11084,
    },
}


def write_contract(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_repository_contract_has_exact_reviewed_facts() -> None:
    path = Path(__file__).resolve().parents[2] / "runtimes/research_web.json"
    assert json.loads(path.read_text(encoding="utf-8")) == EXPECTED
    expected_fields = {
        f"{section}_{key}": value
        for section, fields in EXPECTED.items()
        if section != "schema_version"
        for key, value in fields.items()
    }
    contract = load_runtime_contract()
    assert asdict(contract) == expected_fields
    with pytest.raises(FrozenInstanceError):
        contract.python_major = 4
    assert not hasattr(contract, "__dict__")


@pytest.mark.parametrize("section", [None, "python", "node", "cjpy", "dsh"])
@pytest.mark.parametrize("change", ["extra", "missing", "non_object"])
def test_rejects_inexact_objects(tmp_path: Path, section: str | None, change: str) -> None:
    payload = copy.deepcopy(EXPECTED)
    target = payload if section is None else payload[section]
    if change == "extra":
        target["unexpected"] = 1
    elif change == "missing":
        target.pop(next(iter(target)))
    elif section is None:
        payload = []
    else:
        payload[section] = []
    with pytest.raises(RuntimeContractError, match="^runtime_contract_keys$"):
        load_runtime_contract(write_contract(tmp_path, payload))


@pytest.mark.parametrize(
    "section,key,value,code",
    [
        (None, "schema_version", True, "type"),
        (None, "schema_version", 2, "unsupported"),
        ("python", "major", "3", "type"),
        ("python", "major", 4, "unsupported"),
        ("python", "minor", 13, "unsupported"),
        ("python", "minor", 12.0, "type"),
        ("node", "major", 22, "unsupported"),
        ("node", "minimum_minor", 1, "unsupported"),
        ("node", "minimum_minor", False, "type"),
        ("python", "docker_image", "python:latest", "value"),
        ("python", "docker_image", "python:3.13.0-slim-bookworm", "value"),
        ("node", "docker_image", "node:22.19.0-bookworm-slim", "value"),
        ("node", "docker_image", "node:24.19.0-bookworm-slim\n", "value"),
        ("cjpy", "version", "0.5", "value"),
        ("cjpy", "sha256", "a" * 63, "value"),
        ("cjpy", "sha256", "A" * 64, "value"),
        ("dsh", "commit", "z" * 40, "value"),
        ("dsh", "commit", "a" * 39, "value"),
        ("dsh", "pnpm", "latest", "value"),
        ("dsh", "closure_files", 0, "value"),
        ("dsh", "closure_files", -1, "value"),
        ("dsh", "closure_files", True, "type"),
        ("dsh", "remote", "http://github.com/owner/repo.git", "value"),
        ("dsh", "remote", "https://user:secret@github.com/owner/repo.git", "value"),
        ("dsh", "remote", "https://github.com/owner/repo.git?token=secret", "value"),
        ("dsh", "remote", "https://github.com/owner/repo.git#fragment", "value"),
        ("dsh", "remote", "https://github.com/../repo.git", "value"),
        ("dsh", "remote", "git@github.com:owner/repo.git", "value"),
    ],
)
def test_rejects_invalid_fields(tmp_path, section, key, value, code):
    payload = copy.deepcopy(EXPECTED)
    (payload if section is None else payload[section])[key] = value
    with pytest.raises(RuntimeContractError, match=f"^runtime_contract_{code}$") as caught:
        load_runtime_contract(write_contract(tmp_path, payload))
    assert caught.value.code == f"runtime_contract_{code}"


@pytest.mark.parametrize(
    "section,key",
    [
        (section, key)
        for section, fields in EXPECTED.items()
        if isinstance(fields, dict)
        for key in fields
    ],
)
def test_rejects_null_for_every_field(tmp_path, section, key):
    payload = copy.deepcopy(EXPECTED)
    payload[section][key] = None
    with pytest.raises(RuntimeContractError, match="^runtime_contract_type$"):
        load_runtime_contract(write_contract(tmp_path, payload))


@pytest.mark.parametrize("alias", ["symlink", "parent_symlink", "hardlink", "directory", "fifo"])
def test_rejects_aliased_or_non_regular_paths(tmp_path, alias):
    source = write_contract(tmp_path, EXPECTED)
    path = tmp_path / "alias.json"
    if alias == "symlink":
        path.symlink_to(source)
    elif alias == "parent_symlink":
        directory = tmp_path / "alias-dir"
        directory.symlink_to(tmp_path, target_is_directory=True)
        path = directory / source.name
    elif alias == "hardlink":
        os.link(source, path)
    elif alias == "directory":
        path.mkdir()
    elif hasattr(os, "mkfifo"):
        os.mkfifo(path)
    else:
        pytest.skip("FIFO is a POSIX-only path type")
    with pytest.raises(RuntimeContractError, match="^runtime_contract_unsafe_path$"):
        load_runtime_contract(path)


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"{", "json"),
        (b"\xff", "encoding"),
        (b" " * 16385, "too_large"),
        (b'{"schema_version":1,"schema_version":1}', "json"),
        (b'{"schema_version":NaN}', "json"),
        (b"[" * 2000, "json"),
    ],
)
def test_rejects_invalid_or_unbounded_bytes(tmp_path, raw, code):
    path = tmp_path / "contract.json"
    path.write_bytes(raw)
    with pytest.raises(RuntimeContractError, match=f"^runtime_contract_{code}$"):
        load_runtime_contract(path)


def test_read_failure_has_stable_redacted_error(tmp_path, caplog):
    with pytest.raises(RuntimeContractError, match="^runtime_contract_io$") as caught:
        load_runtime_contract(tmp_path / "secret-path.json")
    assert "runtime_contract_io" in caplog.text
    assert "secret-path" not in caplog.text
    formatted = "".join(traceback.format_exception(caught.value))
    assert str(tmp_path / "secret-path.json") not in formatted


def test_rejects_ancestor_alias_swapped_and_restored_during_open(tmp_path, monkeypatch):
    parent = tmp_path / "trusted"
    parent.mkdir()
    path = write_contract(parent, EXPECTED)
    moved = tmp_path / "moved"
    original = os.open
    attacked = []

    def open_through_swapped_ancestor(candidate, flags, *args, **kwargs):
        if Path(candidate).name != path.name:
            return original(candidate, flags, *args, **kwargs)
        attacked.append(True)
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
        try:
            return original(candidate, flags, *args, **kwargs)
        finally:
            parent.unlink()
            moved.rename(parent)

    monkeypatch.setattr(os, "open", open_through_swapped_ancestor)
    code = "io" if os.name == "nt" else "changed"
    with pytest.raises(RuntimeContractError, match=f"^runtime_contract_{code}$"):
        load_runtime_contract(path)
    assert attacked == [True]


@pytest.mark.parametrize("failure", ["none", "open", "body", "close"])
def test_windows_parent_handles_pin_and_close_on_every_exit(tmp_path, monkeypatch, failure):
    from app.research_web import runtime_contract

    opened = []
    closed = []

    def create_file(path, access, sharing, security, disposition, flags, template):
        # CPython 3.12 parses the security-attributes pointer as an integer.
        # Match the native parser, rather than accepting a ctypes-style None.
        if type(security) is not int:
            raise TypeError("security_attributes must be an integer")
        assert access == 0x80  # FILE_READ_ATTRIBUTES
        assert sharing == 1  # FILE_SHARE_READ only: deny write/delete handles
        assert disposition == 3  # OPEN_EXISTING
        assert flags == 0x02200000  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        assert security == 0 and template == 0
        if failure == "open" and opened:
            raise OSError("sensitive Windows path")
        handle = len(opened) + 1
        opened.append((path, handle))
        return handle

    def close_handle(handle):
        closed.append(handle)
        if failure == "close" and len(closed) == 1:
            raise OSError("sensitive Windows path")

    monkeypatch.setitem(
        sys.modules,
        "_winapi",
        SimpleNamespace(CreateFile=create_file, CloseHandle=close_handle),
    )
    if failure != "none":
        with pytest.raises(RuntimeContractError, match="^runtime_contract_io$") as caught:
            with runtime_contract._pin_windows_parents(tmp_path / "contract.json"):
                assert failure != "open", "must fail before yielding"
                if failure == "body":
                    raise OSError("sensitive Windows path")
        assert "sensitive Windows path" not in "".join(traceback.format_exception(caught.value))
    else:
        with runtime_contract._pin_windows_parents(tmp_path / "contract.json"):
            assert len(opened) == len((tmp_path / "contract.json").parents)
            assert closed == []
    expected_handles = 1 if failure == "open" else len((tmp_path / "contract.json").parents)
    assert len(opened) == expected_handles
    assert closed == [handle for _, handle in reversed(opened)]


def test_windows_missing_api_fails_closed_without_raw_chain(tmp_path, monkeypatch):
    from app.research_web import runtime_contract

    monkeypatch.setitem(sys.modules, "_winapi", None)
    with pytest.raises(RuntimeContractError, match="^runtime_contract_io$") as caught:
        with runtime_contract._pin_windows_parents(tmp_path / "contract.json"):
            pytest.fail("missing API must not permit a path-only fallback")
    assert "ModuleNotFoundError" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("failure", ["none", "directory_open", "leaf_open", "read"])
@pytest.mark.skipif(os.name != "posix", reason="Tests POSIX directory descriptor lifetime")
def test_posix_retained_descriptors_close_on_every_exit(tmp_path, monkeypatch, failure):
    path = write_contract(tmp_path, EXPECTED)
    opened = []
    real_open = os.open
    real_fdopen = os.fdopen

    def checked_open(candidate, flags, *args, **kwargs):
        leaf = Path(candidate).name == path.name
        if (failure == "directory_open" and opened) or (failure == "leaf_open" and leaf):
            raise OSError("sensitive path")
        descriptor = real_open(candidate, flags, *args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def checked_fdopen(*args, **kwargs):
        if failure == "read":
            raise OSError("sensitive path")
        return real_fdopen(*args, **kwargs)

    monkeypatch.setattr(os, "open", checked_open)
    monkeypatch.setattr(os, "fdopen", checked_fdopen)
    if failure == "none":
        assert load_runtime_contract(path).dsh_commit == EXPECTED["dsh"]["commit"]
        assert len(opened) == len(path.parents) + 1
    else:
        with pytest.raises(RuntimeContractError, match="^runtime_contract_io$"):
            load_runtime_contract(path)
    assert opened
    for descriptor in opened:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_rejects_windows_reparse_attribute(tmp_path, monkeypatch):
    path = write_contract(tmp_path, EXPECTED)
    original = Path.lstat

    def lstat(candidate):
        identity = original(candidate)
        if candidate == path:
            return SimpleNamespace(st_mode=identity.st_mode, st_file_attributes=0x400)
        return identity

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(RuntimeContractError, match="^runtime_contract_unsafe_path$"):
        load_runtime_contract(path)


@pytest.mark.parametrize("phase", ["before_open", "after_open"])
def test_rejects_file_replacement_and_closes_descriptor(tmp_path, monkeypatch, phase):
    path = write_contract(tmp_path, EXPECTED)
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(EXPECTED), encoding="utf-8")
    original = os.open
    descriptors = []

    def open_replaced(candidate, flags, *args, **kwargs):
        if Path(candidate).name != path.name:
            return original(candidate, flags, *args, **kwargs)
        if phase == "before_open":
            replacement.replace(path)
        descriptor = original(candidate, flags, *args, **kwargs)
        descriptors.append(descriptor)
        if phase == "after_open":
            replacement.replace(path)
        return descriptor

    monkeypatch.setattr(os, "open", open_replaced)
    with pytest.raises(RuntimeContractError, match="^runtime_contract_changed$"):
        load_runtime_contract(path)
    with pytest.raises(OSError):
        os.fstat(descriptors[0])


def test_permission_failure_is_stable(tmp_path, monkeypatch):
    path = write_contract(tmp_path, EXPECTED)

    def deny_open(*_args, **_kwargs):
        raise PermissionError("private filesystem information")

    monkeypatch.setattr(os, "open", deny_open)
    with pytest.raises(RuntimeContractError, match="^runtime_contract_io$"):
        load_runtime_contract(path)


def test_service_manager_import_stays_lightweight():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.research_web.service_manager; "
            "assert 'app.research_web.launch_runtime' not in sys.modules; "
            "assert 'app.research_web.capabilities.catalog' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_bootstrap_help_needs_only_stdlib_from_another_directory(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/setup_web.py"
    completed = subprocess.run(
        [sys.executable, "-S", str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--check-only" in completed.stdout


def test_built_wheel_contains_and_loads_the_machine_contract(tmp_path):
    project = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from hatchling.build import build_wheel; "
            "print(build_wheel(sys.argv[1]))",
            str(tmp_path),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    wheel_path = tmp_path / completed.stdout.strip()
    extracted = tmp_path / "installed"
    with zipfile.ZipFile(wheel_path) as wheel:
        assert "runtimes/research_web.json" in wheel.namelist()
        assert json.loads(wheel.read("runtimes/research_web.json")) == EXPECTED
        # Extract just the real stdlib import closure, without installing a package.
        for name in (
            "app/__init__.py",
            "app/research_web/__init__.py",
            "app/research_web/runtime_contract.py",
            "runtimes/__init__.py",
            "runtimes/research_web.json",
        ):
            wheel.extract(name, extracted)
    imported = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from app.research_web import RUNTIME_CONTRACT; "
            "from importlib.resources import files; "
            "import json; "
            "facts=json.loads(files('runtimes').joinpath('research_web.json').read_text()); "
            "assert RUNTIME_CONTRACT.dsh_commit == facts['dsh']['commit']",
            str(extracted),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr
